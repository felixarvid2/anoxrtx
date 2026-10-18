#!/usr/bin/env -S sh -c 'exec "${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}" "$0" "$@"'
"""Automatic in-game check of the Remix mod: run maps with a layer on and off, collect evidence, write a report.

usage: anoxcheck.py OUTDIR MAP [MAP...] [--ab LAYER | --ab-cfg "CVAR LINE"] [--views FILE] [--wait S] [--settle S]
       anoxcheck.py OUTDIR --report-only

For every map (started with "+map MAP" through tools/rigsession.sh, which restores Steam afterwards):
  - starts the game, waits until the map is shown, takes --settle seconds then two screenshots 2 s apart
  - collects: Remix crash, Remix log warnings/errors that name mod files (missing/broken DDS, USD errors),
    QindieGL map-light load/create/draw results, event-light state, ProcTex lines
With --ab LAYER (e.g. emissive, pbr): the same maps are run twice, once with LAYER in mod.usda's subLayers and
once without it (mod.usda is restored afterwards, also on failure); the report shows both views side by side
with the per-pixel difference, mean brightness change and the share of changed pixels.
With --ab-cfg "set r_novis 1": the A/B switch is that line appended to anoxdata/CONFIGS/Default.cfg (restored
afterwards), e.g. to compare culling settings; the report adds frame times from QindieGL's "Perf:" log lines.
With --views FILE (lines "MAP NAME X Y Z PITCH YAW", e.g. from tools/find_views.py) each listed view of a map is
shot by writing rtx-remix/rigcam.txt (QindieGL renders world views from there); maps without views use the
player's view.
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
out=$1; tag=$2; map=$3; wait=$4; settle=$5; views=$6
RIGCAM="$GAME/rtx-remix/rigcam.txt"; rm -f "$RIGCAM"
size_before=$(stat -c %s "$QLOG" 2>/dev/null || echo 0)
$RIG start > "$out/$tag-$map.start.txt" 2>&1
end=$((SECONDS + wait))
while [ $SECONDS -lt $end ]; do
  grep -aq "MapLights: $map CreateLight" "$QLOG" 2>/dev/null && break
  sleep 2
done
sleep "$settle"
if [ -s "$views" ]; then
  while read -r vname x y z p yw; do
    echo "$x $y $z $p $yw 0" > "$RIGCAM"; sleep 5
    $RIG shot "anoxcheck_$tag-${map}@${vname}_a" > /dev/null 2>&1; sleep 2
    $RIG shot "anoxcheck_$tag-${map}@${vname}_b" > /dev/null 2>&1
  done < "$views"
  rm -f "$RIGCAM"; sleep 2
else
  $RIG shot "anoxcheck_$tag-${map}_a" > /dev/null 2>&1
  sleep 2
  $RIG shot "anoxcheck_$tag-${map}_b" > /dev/null 2>&1
fi
# QindieGL.log may be rewritten at game start: take only this run's part
if [ "$(stat -c %s "$QLOG" 2>/dev/null || echo 0)" -lt "$size_before" ]; then cp "$QLOG" "$out/$tag-$map.qindiegl.log"
else tail -c +$((size_before + 1)) "$QLOG" > "$out/$tag-$map.qindiegl.log"; fi
cp "$LOGS/remix-dxvk.log" "$out/$tag-$map.remix.log" 2>/dev/null
cp "$LOGS/bridge32.log" "$out/$tag-$map.bridge32.log" 2>/dev/null
echo done > "$out/$tag-$map.done"
'''


def keys_for(mp, views):
    return ['%s@%s' % (mp, v[0]) for v in views.get(mp, [])] or [mp]


def run_session(out, tag, mp, wait, settle, views):
    script = out / 'session.sh'
    script.write_text(SESSION_SCRIPT)
    vf = out / ('views-%s.txt' % mp)
    vf.write_text(''.join(' '.join(v) + '\n' for v in views.get(mp, [])))
    log = out / ('%s-%s.session.txt' % (tag, mp))
    with open(log, 'w') as f:
        subprocess.run([str(HERE / 'rigsession.sh'), '--map', mp, str(script), str(out), tag, mp, str(wait), str(settle),
                        str(vf)], stdout=f, stderr=subprocess.STDOUT, cwd=str(HERE.parent))
    for key in keys_for(mp, views):
        for s in ('a', 'b'):
            src = SHOTS / ('anoxcheck_%s-%s_%s.png' % (tag, key, s))
            if src.exists():
                shutil.move(str(src), str(out / ('%s-%s_%s.png' % (tag, key, s))))
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
    r = {'frame_ms': None, 'remix_crash': False, 'mod_errors': [], 'lights_loaded': None, 'lights_created': None,
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
        perf = [float(x) for x in re.findall(r"Perf: ([0-9.]+) ms/frame .*map '%s'" % re.escape(mp), q)]
        r['frame_ms'] = round(sum(perf[1:]) / len(perf[1:]), 2) if len(perf) > 1 else None
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


def report(out, maps, label, views):
    runs = ['on', 'off'] if label else ['run']
    res = {}
    for mp in maps:
        logs = {tag: analyse_logs(out, tag, mp) for tag in runs}
        for key in keys_for(mp, views):
            r = {}
            for tag in runs:
                a = img(out / ('%s-%s_a.png' % (tag, key))); b = img(out / ('%s-%s_b.png' % (tag, key)))
                r[tag] = dict(logs[tag], **frame_checks(a, b))
            if label:
                r['ab'] = ab_compare(img(out / ('on-%s_a.png' % key)), img(out / ('off-%s_a.png' % key)),
                                     out / ('compare_%s.png' % key.replace('@', '_')), key, label)
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
                if label and x['settle_diff'] is not None and x['settle_diff'] > 5:
                    fails.append('%s: scene not settled (%.1f%% changed between two shots)' % (tag, x['settle_diff']))
            r['fails'] = fails
            res[key] = r
    (out / 'report.json').write_text(json.dumps(res, indent=1))
    lines = ['# anoxcheck report', '', 'A/B switch: %s' % (label or '(none, single run)'), '',
             '| view | result | brightness | ' + ('A/B changed px | A/B brightness | ms/frame on | ms/frame off |' if label else 'ms/frame |') + ' lights | event styles |',
             '| --- | --- | --- | ' + ('--- | --- | --- | --- |' if label else '--- |') + ' --- | --- |']
    for key, r in res.items():
        x = r[runs[0]]
        row = '| %s | %s | %s | ' % (key, 'FAIL' if r['fails'] else 'ok', x['mean'])
        if label:
            ab = r.get('ab') or {}
            row += ('%s%% | %+.2f |' % (ab['changed_pct'], ab['brightness_change'])) if ab else '- | - |'
            row += ' %s | %s |' % (r['on']['frame_ms'], r['off']['frame_ms'])
        else:
            row += '%s |' % x['frame_ms']
        lines.append(row + ' %s/%s | %s |' % (x['lights_created'], x['lights_loaded'], x['event_styles']))
    for key, r in res.items():
        if r['fails'] or any(r[t]['mod_errors'] for t in runs):
            lines += ['', '## %s' % key] + ['- %s' % f for f in r['fails']]
            for t in runs:
                lines += ['  - %s' % e for e in r[t]['mod_errors'][:8]]
    if label:
        lines += ['', 'Side-by-side images: compare_<view>.png']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return not any(r['fails'] for r in res.values())


class Switch:
    """A/B switch: a USD layer in mod.usda, or a line appended to Default.cfg. Always restored."""
    def __init__(self, out, layer, cfg_line):
        self.layer, self.cfg_line = layer, cfg_line
        self.path = MOD if layer else GAME / 'anoxdata' / 'CONFIGS' / 'Default.cfg'
        if layer and '@./%s.usda@' % layer not in self.path.read_text():
            sys.exit('layer %s is not in %s' % (layer, self.path))
        self.backup = out / (self.path.name + '.orig')
        shutil.copy2(self.path, self.backup)
        self.label = layer or cfg_line

    def set(self, on):
        s = self.backup.read_text(errors='replace')
        if self.layer and not on:
            s = re.sub(r',?\s*@\./%s\.usda@' % re.escape(self.layer), '', s, count=1).replace('[, ', '[')
        if self.cfg_line and on:
            s = s.rstrip('\n') + '\n' + self.cfg_line + '\n'
        self.path.write_text(s)

    def restore(self):
        shutil.copy2(self.backup, self.path)
        print('[anoxcheck] %s restored' % self.path.name, flush=True)


def read_views(path):
    views = {}
    for line in open(path):
        t = line.split()
        if len(t) >= 7 and not line.startswith('#'):
            views.setdefault(t[0].lower(), []).append(t[1:7])
    return views


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    layer = opt('--ab', ''); cfg_line = opt('--ab-cfg', ''); views_file = opt('--views', '')
    wait = int(opt('--wait', '120')); settle = int(opt('--settle', '20'))
    report_only = '--report-only' in args
    args = [a for a in args if a != '--report-only']
    if len(args) < 1 or (not report_only and len(args) < 2) or (layer and cfg_line):
        print(__doc__); sys.exit(2)
    out = Path(args[0]).resolve(); out.mkdir(parents=True, exist_ok=True)
    if report_only:
        meta = json.loads((out / 'meta.json').read_text())
        sys.exit(0 if report(out, meta['maps'], meta['label'], meta['views']) else 1)
    maps = [m.lower() for m in args[1:]]
    views = read_views(views_file) if views_file else {}
    label = layer or cfg_line
    (out / 'meta.json').write_text(json.dumps({'maps': maps, 'label': label, 'views': views, 'started': time.ctime()}))
    if label:
        sw = Switch(out, layer, cfg_line)
        try:
            for tag, on in (('on', True), ('off', False)):
                sw.set(on)
                for mp in maps:
                    print('[anoxcheck] %s %s' % (tag, mp), flush=True)
                    if not run_session(out, tag, mp, wait, settle, views):
                        print('[anoxcheck] WARNING: session for %s did not restore cleanly' % mp, flush=True)
        finally:
            sw.restore()
    else:
        for mp in maps:
            print('[anoxcheck] %s' % mp, flush=True)
            run_session(out, 'run', mp, wait, settle, views)
    sys.exit(0 if report(out, maps, label, views) else 1)


if __name__ == '__main__':
    main()
