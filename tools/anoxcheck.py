#!/usr/bin/env -S sh -c 'exec "${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}" "$0" "$@"'
"""Automatic in-game check of the Remix mod: run maps with a layer on and off, collect evidence, write a report.

usage: anoxcheck.py OUTDIR MAP [MAP...] [--ab LAYER] [--wait SECS] [--settle SECS]
       anoxcheck.py OUTDIR --report-only

For every map (started with "+map MAP" through tools/rigsession.sh, which restores Steam afterwards):
  - starts the game, waits until the map is shown, takes --settle seconds then two screenshots 2 s apart
  - collects: Remix crash, Remix log warnings/errors that name mod files (missing/broken DDS, USD errors),
    QindieGL map-light load/create/draw results, event-light state, ProcTex lines
With --ab LAYER (e.g. emissive, pbr): the same maps are run twice, once with LAYER in mod.usda's subLayers and
once without it (mod.usda is restored afterwards, also on failure); the report shows both views side by side
with the per-pixel difference, mean brightness change and the share of changed pixels.
Checks that fail a map: Remix crash, black or white frame, mod-file errors in the Remix log, map lights
created < loaded (minus START_OFF), draw failures, or (A/B) the two shots of one run differing a lot
(unsettled scene, so the A/B difference is not meaningful).
OUTDIR gets report.md, report.json, compare_<map>.png. Exit status 1 when any check fails.
Run time: about 2 minutes per map and run.
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
GAME = Path(os.environ.get('ANOX_GAME', '~/.steam/debian-installation/steamapps/common/Anachronox')).expanduser()
MOD = GAME / 'rtx-remix' / 'mods' / 'anoxrt' / 'mod.usda'
SHOTS = HERE / 'shots'

SESSION_SCRIPT = r'''
out=$1; tag=$2; map=$3; wait=$4; settle=$5
size_before=$(stat -c %s "$QLOG" 2>/dev/null || echo 0)
$RIG start > "$out/$tag-$map.start.txt" 2>&1
end=$((SECONDS + wait))
while [ $SECONDS -lt $end ]; do
  grep -aq "MapLights: $map CreateLight" "$QLOG" 2>/dev/null && break
  sleep 2
done
sleep "$settle"
$RIG shot "anoxcheck_$tag-${map}_a" > /dev/null 2>&1
sleep 2
$RIG shot "anoxcheck_$tag-${map}_b" > /dev/null 2>&1
# QindieGL.log may be rewritten at game start: take only this run's part
if [ "$(stat -c %s "$QLOG" 2>/dev/null || echo 0)" -lt "$size_before" ]; then cp "$QLOG" "$out/$tag-$map.qindiegl.log"
else tail -c +$((size_before + 1)) "$QLOG" > "$out/$tag-$map.qindiegl.log"; fi
cp "$LOGS/remix-dxvk.log" "$out/$tag-$map.remix.log" 2>/dev/null
cp "$LOGS/bridge32.log" "$out/$tag-$map.bridge32.log" 2>/dev/null
echo done > "$out/$tag-$map.done"
'''


def run_session(out, tag, mp, wait, settle):
    script = out / 'session.sh'
    script.write_text(SESSION_SCRIPT)
    log = out / ('%s-%s.session.txt' % (tag, mp))
    with open(log, 'w') as f:
        subprocess.run([str(HERE / 'rigsession.sh'), '--map', mp, str(script), str(out), tag, mp, str(wait), str(settle)],
                       stdout=f, stderr=subprocess.STDOUT, cwd=str(HERE.parent))
    for s in ('a', 'b'):
        src = SHOTS / ('anoxcheck_%s-%s_%s.png' % (tag, mp, s))
        if src.exists():
            shutil.move(str(src), str(out / ('%s-%s_%s.png' % (tag, mp, s))))
    txt = log.read_text(errors='replace')
    return 'rigsession: restored' in txt and 'WARNING' not in txt


def set_layer(layer, enabled, backup):
    s = backup.read_text()
    if not enabled:
        s = re.sub(r',?\s*@\./%s\.usda@' % re.escape(layer), '', s, count=1)
        s = s.replace('[, ', '[')
    MOD.write_text(s)


def img(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=np.float32) if path.exists() else None


def analyse_logs(out, tag, mp):
    r = {'remix_crash': False, 'mod_errors': [], 'lights_loaded': None, 'lights_created': None,
         'startoff': 0, 'draw_failed': 0, 'event_styles': None, 'proctex': []}
    b = out / ('%s-%s.bridge32.log' % (tag, mp))
    if b.exists() and 'The RTX Remix Runtime has encountered an unexpected issue' in b.read_text(errors='replace'):
        r['remix_crash'] = True
    rl = out / ('%s-%s.remix.log' % (tag, mp))
    if rl.exists():
        for line in rl.read_text(errors='replace').splitlines():
            low = line.lower()
            if ('err:' in low or 'warn:' in low) and 'anoxrt' in low and 'secretreplacement' not in low:
                r['mod_errors'].append(line.strip()[:220])
    ql = out / ('%s-%s.qindiegl.log' % (tag, mp))
    if ql.exists():
        q = ql.read_text(errors='replace')
        m = re.findall(r'MapLights: loaded (\d+) lights .*?maplights\\%s\.lights' % re.escape(mp), q)
        if m: r['lights_loaded'] = int(m[-1])
        m = re.findall(r'MapLights: %s CreateLight attempted \d+ success (\d+)' % re.escape(mp), q)
        if m: r['lights_created'] = int(m[-1])
        m = re.findall(r'MapLights: %s static draw frame \d+ attempted \d+ success \d+ failed (\d+)' % re.escape(mp), q)
        if m: r['draw_failed'] = max(int(x) for x in m)
        if 'EventLights: game light styles valid' in q: r['event_styles'] = 'valid'
        elif 'EventLights: game light styles unavailable' in q: r['event_styles'] = 'unavailable'
        r['proctex'] = re.findall(r'ProcTex: .*frozen.*', q)[:4]
    lf = GAME / 'rtx-remix' / 'maplights' / (mp + '.lights')
    if lf.exists():
        r['startoff'] = sum(1 for l in lf.read_text(errors='replace').splitlines() if l.rstrip().endswith('startoff'))
    return r


def frame_checks(a, b):
    res = {'mean': None, 'black': None, 'white': None, 'settle_diff': None}
    if a is None:
        return res
    lum = a.mean(axis=2)
    res['mean'] = round(float(lum.mean()), 1)
    res['black'] = bool(lum.mean() < 4)
    res['white'] = bool(lum.mean() > 245)
    if b is not None and b.shape == a.shape:
        res['settle_diff'] = round(float((np.abs(a - b).max(axis=2) > 24).mean() * 100), 2)
    return res


def ab_compare(on, off, path, mp, layer):
    if on is None or off is None or on.shape != off.shape:
        return None
    d = np.abs(on - off).max(axis=2)
    changed = round(float((d > 24).mean() * 100), 2)
    dmean = round(float(on.mean() - off.mean()), 2)
    h = min(360, on.shape[0]); w = int(on.shape[1] * h / on.shape[0])
    tiles = [Image.fromarray(on.astype(np.uint8)).resize((w, h)), Image.fromarray(off.astype(np.uint8)).resize((w, h)),
             Image.fromarray(np.clip(d * 3, 0, 255).astype(np.uint8)).convert('RGB').resize((w, h))]
    sheet = Image.new('RGB', (3 * w + 20, h + 22), 'white')
    dr = ImageDraw.Draw(sheet)
    for i, (t, lbl) in enumerate(zip(tiles, ('%s on' % layer, '%s off' % layer, 'difference x3'))):
        sheet.paste(t, (i * (w + 10), 22)); dr.text((i * (w + 10) + 4, 4), '%s: %s' % (mp, lbl), fill='black')
    sheet.save(path)
    return {'changed_pct': changed, 'brightness_change': dmean}


def report(out, maps, layer):
    runs = ['on', 'off'] if layer else ['run']
    res = {}
    for mp in maps:
        r = {}
        for tag in runs:
            a = img(out / ('%s-%s_a.png' % (tag, mp))); b = img(out / ('%s-%s_b.png' % (tag, mp)))
            r[tag] = dict(analyse_logs(out, tag, mp), **frame_checks(a, b))
        if layer:
            r['ab'] = ab_compare(img(out / ('on-%s_a.png' % mp)), img(out / ('off-%s_a.png' % mp)),
                                 out / ('compare_%s.png' % mp), mp, layer)
        fails = []
        for tag in runs:
            x = r[tag]
            if x['remix_crash']: fails.append('%s: Remix crashed' % tag)
            if x['mean'] is None: fails.append('%s: no screenshot' % tag)
            elif x['black']: fails.append('%s: black frame' % tag)
            elif x['white']: fails.append('%s: white frame' % tag)
            if x['mod_errors']: fails.append('%s: %d mod-file errors in the Remix log' % (tag, len(x['mod_errors'])))
            if x['lights_loaded'] is not None and x['lights_created'] is not None and \
                    x['lights_created'] < x['lights_loaded'] - x['startoff']:
                fails.append('%s: map lights created %d < loaded %d' % (tag, x['lights_created'], x['lights_loaded']))
            if x['draw_failed']: fails.append('%s: %d light draw failures' % (tag, x['draw_failed']))
            if layer and x['settle_diff'] is not None and x['settle_diff'] > 5:
                fails.append('%s: scene not settled (%.1f%% changed between two shots)' % (tag, x['settle_diff']))
        r['fails'] = fails
        res[mp] = r
    (out / 'report.json').write_text(json.dumps(res, indent=1))
    lines = ['# anoxcheck report', '', 'Layer under test: %s' % (layer or '(none, single run)'), '',
             '| map | result | brightness | ' + ('A/B changed px | A/B brightness |' if layer else '') + ' lights | event styles |',
             '| --- | --- | --- | ' + ('--- | --- |' if layer else '') + ' --- | --- |']
    for mp, r in res.items():
        x = r[runs[0]]
        lights = '%s/%s' % (x['lights_created'], x['lights_loaded'])
        row = '| %s | %s | %s | ' % (mp, 'FAIL' if r['fails'] else 'ok', x['mean'])
        if layer:
            ab = r.get('ab') or {}
            row += '%s%% | %+.2f |' % (ab.get('changed_pct', '-'), ab.get('brightness_change', 0)) if ab else '- | - |'
        lines.append(row + ' %s | %s |' % (lights, x['event_styles']))
    for mp, r in res.items():
        if r['fails'] or any(r[t]['mod_errors'] for t in runs):
            lines += ['', '## %s' % mp] + ['- %s' % f for f in r['fails']]
            for t in runs:
                lines += ['  - %s' % e for e in r[t]['mod_errors'][:8]]
    if layer:
        lines += ['', 'Side-by-side images: ' + ', '.join('compare_%s.png' % m for m in maps)]
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return not any(r['fails'] for r in res.values())


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    layer = opt('--ab', ''); wait = int(opt('--wait', '120')); settle = int(opt('--settle', '20'))
    report_only = '--report-only' in args
    args = [a for a in args if a != '--report-only']
    if len(args) < 1 or (not report_only and len(args) < 2):
        print(__doc__); sys.exit(2)
    out = Path(args[0]).resolve(); out.mkdir(parents=True, exist_ok=True)
    if report_only:
        maps = sorted({p.name.split('-', 1)[1].rsplit('_', 1)[0] for p in out.glob('*-*_a.png')})
        layer = json.loads((out / 'meta.json').read_text()).get('layer', '') if (out / 'meta.json').exists() else ''
        sys.exit(0 if report(out, maps, layer) else 1)
    maps = args[1:]
    (out / 'meta.json').write_text(json.dumps({'maps': maps, 'layer': layer, 'started': time.ctime()}))
    if layer:
        if '@./%s.usda@' % layer not in MOD.read_text():
            sys.exit('layer %s is not in %s' % (layer, MOD))
        backup = out / 'mod.usda.orig'
        shutil.copy2(MOD, backup)
        try:
            for tag, on in (('on', True), ('off', False)):
                set_layer(layer, on, backup)
                for mp in maps:
                    print('[anoxcheck] %s %s' % (tag, mp), flush=True)
                    if not run_session(out, tag, mp, wait, settle):
                        print('[anoxcheck] WARNING: session for %s did not restore cleanly' % mp, flush=True)
        finally:
            shutil.copy2(backup, MOD)
            print('[anoxcheck] mod.usda restored', flush=True)
    else:
        for mp in maps:
            print('[anoxcheck] %s' % mp, flush=True)
            run_session(out, 'run', mp, wait, settle)
    sys.exit(0 if report(out, maps, layer) else 1)


if __name__ == '__main__':
    main()
