#!/usr/bin/env python3
"""PBR material classes for the level textures from reviewable rules, BSP flags and usage, with an uncertainty report.

usage: pbr_classify.py OUTDIR MAP.bsp... [--rules RULES.json] [--classes JEV.json] [--ai CACHE.json]
                       [--deepseek [--review N] [--max-usd 1.0]]
                       [--deepseek-vision GAMEDIR [--pick SETS] [--max-usd 1.0]] [--vision CACHE.json]

Every texture the maps use gets a class from tools/pbr_rules.json (roughness/metallic per class), in this order:
  exception   exact texture path in "exceptions" (reviewed, so never a conflict); when it names Jev's material, Jev's
              roughness/metal are kept (the exception only settles the rule-vs-Jev conflict)
  flags       SURF_SKY/SURF_WARP faces: no PBR material (hd_sky/liquids layers own them); "haze_glass" likewise
  jev         --classes (tools/jev_classify.py): Jev's roughness/metal, as pbr_layer.py has used them; when a strong
              name rule and the DeepSeek suggestion both disagree with Jev's material, the name rule wins (vote);
              likewise when a strong name rule and a high-confidence --vision answer (what DeepSeek saw in the
              thumbnail) agree against Jev ("rule+vision")
  rule        first rule whose keyword is in the base name (a weak match, see pbr_rules.json, only in legacy rules)
  light       mostly SURF_LIGHT faces (share >= flag_rules.light_share) and no name rule: the "light" class
  vision      a --vision CACHE.json answer (thumbnail; class validated, confidence at most medium)
  deepseek    a suggestion from --ai CACHE.json (class validated against the classes, confidence at most medium)
  default     unclassified
Usage per texture (faces, maps, SURF_LIGHT/TRANS faces, brush contents water/slime/lava/window, animation frames
counted with their first frame) goes into the report, which lists unclassified, weak, conflicting and model-sourced
classes, largest face count first. Writes OUTDIR/pbr_classes.json and OUTDIR/pbr_report.md.

--deepseek asks DeepSeek (text only: texture paths, flag/usage numbers, the class list) for the textures the rules
leave unclassified and for N (--review, default 150) rule-classified ones as a calibration sample, 120 per request.
Answers are cached in --ai (default ~/.cache/anoxrtx/deepseek_pbr.json), so reruns are free. Stops on any API error
(no retries) and when the estimated cost of this run reaches --max-usd. The key is read from
~/.config/anoxrtx/deepseek.key and only sent as a header. Model: deepseek-flash (DeepSeek V4.1 Flash) for text
and images.

--deepseek-vision GAMEDIR shows deepseek-flash the textures (loose pack GAMEDIR/anoxdata/textures) as 5x5 contact
sheets of numbered 128 px thumbnails (jev_classify.contact_sheet) with each texture's path and usage numbers as
text, and asks for one class per texture with confidence and what it sees. --pick chooses the textures,
comma-separated sets NAME[:N] (default calib:50,conflicts,unclassified:300,jev:150, see vision_pick). Answers are
cached in --vision (default ~/.cache/anoxrtx/deepseek_vision.json, token counts in deepseek_vision.log), same
stop rules and --max-usd guard as --deepseek; the run costs ~0.005 USD per sheet. Only these thumbnails are sent
(approved by Felix on 2026-10-28). Without --deepseek-vision, --vision CACHE.json only applies cached answers.
"""
import importlib.util, json, os, re, struct, sys, urllib.error, urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, 'pbr_rules.json')
AI_CACHE = os.path.expanduser('~/.cache/anoxrtx/deepseek_pbr.json')
SURF = {'LIGHT': 0x1, 'SKY': 0x4, 'WARP': 0x8, 'TRANS33': 0x10, 'TRANS66': 0x20, 'NODRAW': 0x80}
CONTENTS = {'window': 0x2, 'lava': 0x8, 'slime': 0x10, 'water': 0x20, 'mist': 0x40}
CONF = {'high': 3, 'medium': 2, 'low': 1, 'none': 0}
# Jev material -> class, for comparing Jev with the rules
JEV_CLASS = {'metal': 'metal', 'wood': 'wood', 'stone': 'stone', 'concrete': 'stone', 'tile': 'polished',
             'glass': 'glass', 'fabric': 'fabric', 'organic': 'organic', 'screen': 'screen'}
# classes that are close enough not to count as a conflict
NEAR = {frozenset(p) for p in (('metal', 'tech'), ('screen', 'sign'), ('stone', 'polished'), ('organic', 'stone'),
                               ('screen', 'tech'))}


def load_rules(path=RULES):
    r = json.load(open(path))
    for i, rule in enumerate(r['rules']):
        if rule['class'] not in r['classes']:
            raise ValueError('rule %d: unknown class %r' % (i, rule['class']))
    for k, e in r['exceptions'].items():
        if e['class'] not in r['classes'] and e['class'] != 'skip':
            raise ValueError('exception %s: unknown class %r' % (k, e['class']))
    return r


def usage(paths):
    """{texture: {'faces', 'maps', 'flags' (OR), 'light', 'trans', 'contents' (OR), 'frame_of'}} over all maps"""
    out = {}
    for path in paths:
        d = open(path, 'rb').read()
        L = [struct.unpack_from('<ii', d, 8 + 8 * i) for i in range(19)]
        toff, tn = L[5][0], L[5][1] // 76
        tex = []
        for i in range(tn):
            flags, value = struct.unpack_from('<ii', d, toff + i * 76 + 32)
            name = d[toff + i * 76 + 40:toff + i * 76 + 72].split(b'\0', 1)[0].decode('latin-1').replace('\\', '/').lower()
            nxt = struct.unpack_from('<i', d, toff + i * 76 + 72)[0]
            tex.append((name, flags, nxt))
        def chain(i):
            seen = [i]
            while 0 <= tex[seen[-1]][2] < tn and tex[seen[-1]][2] not in seen:
                seen.append(tex[seen[-1]][2])
            return seen
        per = Counter()
        for i in range(L[6][1] // 20):
            per[struct.unpack_from('<H', d, L[6][0] + i * 20 + 10)[0]] += 1
        contents = {}
        sides = [struct.unpack_from('<Hh', d, L[15][0] + i * 4)[1] for i in range(L[15][1] // 4)]
        for i in range(L[14][1] // 12):
            first, num, cont = struct.unpack_from('<iii', d, L[14][0] + i * 12)
            for ti in sides[first:first + num]:
                if 0 <= ti < tn:
                    contents[ti] = contents.get(ti, 0) | cont
        mapname = os.path.splitext(os.path.basename(path))[0].lower()
        for i, (name, flags, _) in enumerate(tex):
            for j in chain(i):
                u = out.setdefault(tex[j][0], {'faces': 0, 'maps': set(), 'flags': 0, 'light': 0, 'trans': 0,
                                                'contents': 0, 'frame_of': ''})
                u['flags'] |= flags
                u['contents'] |= contents.get(i, 0)
                n = per.get(i, 0)
                if n and j != i and not u['frame_of'] and tex[j][0] != name:
                    u['frame_of'] = name
                if n:
                    u['faces'] += n; u['maps'].add(mapname)
                    u['light'] += n if flags & SURF['LIGHT'] else 0
                    u['trans'] += n if flags & (SURF['TRANS33'] | SURF['TRANS66']) else 0
    for u in out.values():
        u['maps'] = len(u['maps'])
    return out


def match(base, word):
    """confidence of keyword `word` in the base name: at the start of an alphabetic run = high, at its end or
    inside it = medium, inside it and at most 3 letters long = low (weak); None if absent"""
    best = None
    for m in re.finditer('[a-z]+', base):
        run = m.group(0); i = run.find(word)
        while i >= 0:
            if i == 0:
                c = 'high'
            elif i + len(word) == len(run) or len(word) > 3:
                c = 'medium'
            else:
                c = 'low'
            if best is None or CONF[c] > CONF[best]:
                best = c
            i = run.find(word, i + 1)
    return best


def rule_matches(name, rules):
    """[(rule index, class, keyword, confidence)] of every rule that matches the base name"""
    base = name.split('/')[-1]
    out = []
    for i, r in enumerate(rules['rules']):
        best = None
        for w in r['words']:
            c = match(base, w)
            if c and (best is None or CONF[c] > CONF[best[1]]):
                best = (w, c)
        if best and (best[1] != 'low' or r.get('legacy')):
            out.append((i, r['class'], best[0], best[1]))
        elif best:
            out.append((i, r['class'], best[0], 'weak'))
    return out


def near(a, b):
    """same or similar class; "light" (mostly emissive surfaces, where the base material hardly shows) is near any"""
    return a == b or 'light' in (a, b) or frozenset((a, b)) in NEAR


def flagnames(flags, table):
    return [k for k, v in table.items() if flags & v]


def jev_values(j):
    """(roughness, metallic) from a Jev entry: roughness clamped to 0.05..1, metal only when at least 0.5"""
    return round(min(1.0, max(0.05, j['roughness'])), 3), (round(j['metal'], 3) if j['metal'] >= 0.5 else 0.0)


def classify(name, use, rules, jev=None, ai=None, vision=None):
    """{'class', 'roughness', 'metallic', 'source', 'confidence', 'rule', 'notes': [...], 'conflict': bool, ...}"""
    use = use or {'faces': 0, 'maps': 0, 'flags': 0, 'light': 0, 'trans': 0, 'contents': 0, 'frame_of': ''}
    classes = rules['classes']
    base = name.split('/')[-1]
    notes = []
    res = {'texture': name, 'faces': use['faces'], 'maps': use['maps'], 'flags': flagnames(use['flags'], SURF),
           'contents': flagnames(use['contents'], CONTENTS), 'conflict': False, 'translucent': False}
    def done(cls, source, conf, rule='', rough=None, metal=None):
        res.update({'class': cls, 'source': source, 'confidence': conf, 'rule': rule, 'notes': notes})
        if cls != 'skip':
            res['roughness'] = classes[cls]['roughness'] if rough is None else rough
            res['metallic'] = classes[cls]['metallic'] if metal is None else metal
        return res

    matches = rule_matches(name, rules)
    strong = [m for m in matches if m[3] != 'weak']
    for m in matches:
        if m[3] == 'weak':
            notes.append('weak match "%s" (%s) ignored' % (m[2], m[1]))
    top = strong[0] if strong else None
    res['rule_class'] = top[1] if top else None
    for m in strong[1:]:
        if not near(m[1], top[1]):
            notes.append('also matches "%s" (%s)' % (m[2], m[1]))
            if m[3] == 'high' and top[3] == 'high':
                res['conflict'] = True
    if use['flags'] & (SURF['TRANS33'] | SURF['TRANS66']):
        if any(w in base for w in rules['glass_words']):
            res['translucent'] = name not in rules['haze_glass']
        elif use['trans']:
            notes.append('translucent faces, not named glass (stays opaque)')
    if use['contents'] & (CONTENTS['water'] | CONTENTS['slime'] | CONTENTS['lava']) and not use['flags'] & SURF['WARP']:
        notes.append('on liquid brushes without SURF_WARP')
    if use['contents'] & CONTENTS['window'] and not (top and top[1] == 'glass'):
        notes.append('on window brushes')
    light_share = use['light'] / use['faces'] if use['faces'] else 0.0
    if use['light'] and light_share < 1:
        notes.append('light on %d of %d faces' % (use['light'], use['faces']))
    if use['frame_of']:
        notes.append('animation frame of %s' % use['frame_of'])
    if not use['faces'] and not use['frame_of']:
        notes.append('no drawn faces')
    sug = (ai or {}).get(name)
    if sug and sug.get('class') not in classes:
        notes.append('model suggestion %r is not a class, ignored' % sug.get('class'))
        sug = None
    if sug and sug['class'] == 'default':
        notes.append('model: no evidence')
        sug = None
    if sug:
        res['model'] = {'class': sug['class'], 'confidence': sug['confidence'], 'why': sug.get('why', '')}
    vis = (vision or {}).get(name)
    if vis and vis.get('class') in classes and vis['class'] != 'default':
        res['vision'] = vis = {'class': vis['class'], 'confidence': vis['confidence'], 'why': vis.get('why', '')}
    else:
        vis = None

    if name in rules['exceptions']:
        e = rules['exceptions'][name]
        notes.append('exception: %s' % e.get('why', ''))
        res['conflict'] = False         # reviewed: the exception settles rule-vs-rule (and rule-vs-Jev) conflicts
        j = (jev or {}).get(name)
        if j and JEV_CLASS.get(j.get('material')) == e['class']:
            # the exception confirms Jev's material: keep Jev's finer per-texture roughness/metal
            notes.append('confirms Jev')
            return done(e['class'], 'exception', 'high', '', *jev_values(j))
        return done(e['class'], 'exception', 'high')
    skip = [f for f in rules['flag_rules']['skip_flags'] if use['flags'] & SURF[f]]
    if skip:
        return done('skip', 'flags', 'high', 'SURF_' + '/'.join(skip))
    if name in rules['haze_glass']:
        return done('skip', 'haze_glass', 'high')
    j = (jev or {}).get(name)
    if j:
        jc = JEV_CLASS.get(j.get('material'), 'default')
        res['jev'] = {'class': jc, 'confidence': round(j.get('material_conf', 0), 2)}
        if top and not near(top[1], jc):
            if top[3] == 'high' and sug and near(sug['class'], top[1]) and not near(sug['class'], jc):
                notes.append('Jev says %s; rule and model agree on %s' % (jc, top[1]))
                return done(top[1], 'rule+model', 'medium', top[2])
            if top[3] == 'high' and vis and vis['confidence'] == 'high' and near(vis['class'], top[1]) \
                    and not near(vis['class'], jc):
                notes.append('Jev says %s; rule and image agree on %s' % (jc, top[1]))
                return done(top[1], 'rule+vision', 'medium', top[2])
            notes.append('Jev says %s, rule "%s" says %s' % (jc, top[2], top[1]))
            if top[3] == 'high':
                res['conflict'] = True
        conf = 'high' if top and near(top[1], jc) else 'medium' if j.get('material_conf', 0) >= 0.8 else 'low'
        if res['conflict']:
            conf = 'low'
        return done(jc, 'jev', conf, '', *jev_values(j))
    if top:
        conf = top[3]
        if res['conflict']:
            conf = 'low'
        elif sug and not near(sug['class'], top[1]):
            notes.append('model says %s' % sug['class'])
            conf = min(conf, 'medium', key=CONF.get)
        return done(top[1], 'rule', conf, top[2])
    if use['faces'] and light_share >= rules['flag_rules']['light_share']:
        return done('light', 'flags', 'medium', 'SURF_LIGHT %.0f%%' % (100 * light_share))
    if vis:
        return done(vis['class'], 'vision', min(vis['confidence'], 'medium', key=CONF.get))
    if sug:
        return done(sug['class'], 'deepseek', min(sug['confidence'], 'medium', key=CONF.get))
    return done('default', 'default', 'none')


def classify_all(maps, rules, jev=None, ai=None, vision=None):
    use = usage(maps)
    return {n: classify(n, u, rules, jev, ai, vision) for n, u in sorted(use.items()) if n}, use


def uncertain(r):
    return r['class'] != 'skip' and (r['conflict'] or r['confidence'] in ('low', 'none') or r['source'] in ('deepseek', 'vision'))


def report(results, title='PBR classification'):
    rs = list(results.values())
    lines = ['# %s' % title, '', '%d textures. Classes:' % len(rs), '']
    by = Counter(r['class'] for r in rs)
    faces = Counter()
    for r in rs:
        faces[r['class']] += r['faces']
    lines += ['| class | textures | faces |', '| --- | --- | --- |']
    lines += ['| %s | %d | %d |' % (c, n, faces[c]) for c, n in by.most_common()]
    lines += ['', 'Sources: ' + ', '.join('%s %d' % kv for kv in Counter(r['source'] for r in rs).most_common()),
              'Confidence: ' + ', '.join('%s %d' % kv for kv in Counter(r['confidence'] for r in rs).most_common()), '']
    def table(title, rows, limit=60):
        rows = sorted(rows, key=lambda r: (-r['faces'], r['texture']))
        out = ['## %s (%d)' % (title, len(rows)), '', '| texture | class | source | conf | faces | maps | model | notes |',
               '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for r in rows[:limit]:
            m = ', '.join('%s%s/%s' % (k, r[f]['class'], r[f]['confidence'])
                          for k, f in (('', 'model'), ('image: ', 'vision')) if r.get(f))
            out.append('| %s | %s | %s | %s | %d | %d | %s | %s |' % (
                r['texture'], r['class'], r['source'] + (' "%s"' % r['rule'] if r['rule'] else ''), r['confidence'],
                r['faces'], r['maps'], m, '; '.join(r['notes'])))
        if len(rows) > limit:
            out.append('| ... %d more in pbr_classes.json | | | | | | | |' % (len(rows) - limit))
        return out + ['']
    live = [r for r in rs if r['class'] != 'skip']
    lines += table('Conflicts', [r for r in live if r['conflict']])
    lines += table('Unclassified', [r for r in live if r['class'] == 'default'])
    lines += table('Low confidence', [r for r in live if r['confidence'] == 'low' and not r['conflict']])
    lines += table('Classes from DeepSeek', [r for r in live if r['source'] in ('deepseek', 'rule+model', 'vision', 'rule+vision')])
    lines += table('Weak keyword matches ignored', [r for r in live if any(n.startswith('weak') for n in r['notes'])])
    mod = [r for r in live if r.get('model') and r['source'] in ('rule', 'jev')]
    agree = sum(1 for r in mod if near(r['model']['class'], r['class']))
    if mod:
        lines += ['DeepSeek agrees with %d of %d rule/Jev classes it was shown.' % (agree, len(mod)), '']
        lines += table('DeepSeek disagrees', [r for r in mod if not near(r['model']['class'], r['class'])])
    vis = [r for r in live if r.get('vision') and r['source'] in ('rule', 'jev')]
    if vis:
        lines += ['DeepSeek vision (thumbnails) agrees with %d of %d rule/Jev classes it was shown.' % (
            sum(1 for r in vis if near(r['vision']['class'], r['class'])), len(vis)), '']
        lines += table('DeepSeek vision disagrees', [r for r in vis if not near(r['vision']['class'], r['class'])])
    return '\n'.join(lines)


# DeepSeek (OpenAI-compatible chat completions); text only
DS_URL = 'https://api.deepseek.com/chat/completions'
DS_MODEL = 'deepseek-flash'
DS_PRICE = (0.30, 1.20)     # assumed USD per million input/output tokens, for the --max-usd guard (pessimistic)
DS_BATCH = 120


def ds_prompt(rules, rows):
    cls = '\n'.join('- %s: %s' % (c, v['about']) for c, v in rules['classes'].items())
    tex = '\n'.join(rows)
    return ('Anachronox (2001, Quake 2 engine, sci-fi noir) level textures need a PBR material class for RTX '
            'path tracing. The first folder is the area/map set (bricks = the city of Sender Station streets, '
            'sexmachine = a nightclub, sunder = a lab tower, ...), the base name is the artist\'s abbreviation '
            '(e.g. "conc" concrete, "flr" floor, "wl" wall, "pilr" pillar, "_sm" small variant, "+0" animation frame).\n'
            'Classes:\n%s\n'
            'For each texture line "path | faces | maps | light%% | trans%% | contents" give the most likely class. '
            'Use "default" when the name gives no real evidence (generic walls/floors, numbers, codes); do not guess '
            'from the area alone. Confidence: high only for an unambiguous material word.\n'
            'Answer only JSON: {"path": {"class": "...", "confidence": "high|medium|low", "why": "<= 8 words"}, ...}\n'
            'Textures:\n%s' % (cls, tex))


def ds_row(name, u):
    pct = lambda n: int(round(100.0 * n / u['faces'])) if u['faces'] else 0
    return '%s | %d | %d | %d | %d | %s' % (name, u['faces'], u['maps'], pct(u['light']), pct(u['trans']),
                                            ','.join(flagnames(u['contents'], CONTENTS)) or '-')


def ds_ask(key, prompt, log, image=None):
    content = prompt
    if image is not None:   # PNG bytes as a data URL; deepseek-flash reads images, deepseek-v4-pro ignores them
        import base64
        content = [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image).decode()}},
                   {'type': 'text', 'text': prompt}]
    body = json.dumps({'model': DS_MODEL, 'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
                       'response_format': {'type': 'json_object'}, 'max_tokens': 32000,
                       'reasoning_effort': 'low'}).encode()
    req = urllib.request.Request(DS_URL, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        raise RuntimeError('DeepSeek HTTP %d (stopping, no retry): %s' % (e.code, e.read()[:300].decode(errors='replace')))
    u = d.get('usage', {})
    log(u)
    text = d['choices'][0]['message']['content']
    try:
        return json.loads(text[text.find('{'):text.rfind('}') + 1]), u
    except ValueError as e:
        raise RuntimeError('DeepSeek answer is not JSON (%s), stopping: %s' % (e, text[:2000]))


def validate(got, names, classes):
    """{name: {'class', 'confidence', 'why'}} for answers with an allowed class and a requested name"""
    out = {}
    for n in names:
        a = got.get(n)
        if not isinstance(a, dict):
            continue
        c, conf = str(a.get('class', '')).strip().lower(), str(a.get('confidence', 'low')).strip().lower()
        if c not in classes:
            continue
        out[n] = {'class': c, 'confidence': conf if conf in CONF else 'low', 'why': str(a.get('why', ''))[:80]}
    return out


def run_deepseek(results, use, rules, cache_path, review=150, max_usd=1.0):
    import random
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    live = {n: r for n, r in results.items() if r['class'] != 'skip'}
    want = [n for n, r in live.items() if not r['rule_class'] or r['conflict'] or r['confidence'] == 'low']
    sample = sorted(n for n, r in live.items() if r['source'] == 'rule' and r['confidence'] == 'high')
    random.Random(6).shuffle(sample)
    want += sample[:review]
    return ds_run(sorted(set(want)), cache, cache_path, DS_BATCH, max_usd, 'deepseek',
                  lambda key, chunk, log: validate(ds_ask(key, ds_prompt(rules, [ds_row(n, use[n]) for n in chunk]), log)[0],
                                                   chunk, rules['classes']))


def ds_run(want, cache, cache_path, batch, max_usd, tag, ask):
    """ask(key, chunk, log) -> {name: answer} for the uncached names in `want`, `batch` per request; cached
    after every request (failed answers as class None), token counts logged next to the cache"""
    todo = [n for n in want if n not in cache]
    print('%s: %d textures wanted, %d cached, %d to ask' % (tag, len(want), len(want) - len(todo), len(todo)))
    if not todo:
        return cache
    key = open(os.path.expanduser('~/.config/anoxrtx/deepseek.key')).read().strip()
    spent = [0, 0, 0]; logf = os.path.splitext(cache_path)[0] + '.log'
    def log(u):
        spent[0] += u.get('prompt_tokens', 0); spent[1] += u.get('completion_tokens', 0); spent[2] += 1
        with open(logf, 'a') as f:
            f.write('%s prompt=%d completion=%d\n' % (DS_MODEL, u.get('prompt_tokens', 0), u.get('completion_tokens', 0)))
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        ok = ask(key, chunk, log)
        for n in chunk:
            cache[n] = dict(ok[n], model=DS_MODEL) if n in ok else {'class': None, 'model': DS_MODEL}
        json.dump(cache, open(cache_path, 'w'), indent=1, sort_keys=True)
        cost = (spent[0] * DS_PRICE[0] + spent[1] * DS_PRICE[1]) / 1e6
        print('%s: %d/%d, %d valid; %d requests, tokens in %d out %d, est. %.4f USD' % (
            tag, min(i + batch, len(todo)), len(todo), len(ok), spent[2], spent[0], spent[1], cost), flush=True)
        if cost >= max_usd:
            print('%s: --max-usd reached, stopping' % tag); break
    return cache


# DeepSeek vision: deepseek-flash looks at contact sheets of 128 px thumbnails (approved by Felix on 2026-10-28,
# thumbnails of the level textures only)
VISION_CACHE = os.path.expanduser('~/.cache/anoxrtx/deepseek_vision.json')
VS_COLS = 5
PICKS = 'calib:50,conflicts,unclassified:300,jev:150'


def dsv_prompt(rules, rows):
    cls = '\n'.join('- %s: %s' % (c, v['about']) for c, v in rules['classes'].items())
    tex = '\n'.join('%d: %s' % (i + 1, r) for i, r in enumerate(rows))
    return ('The image is a contact sheet of %d level textures from Anachronox (2001, Quake 2 engine, sci-fi noir), '
            '128 px each, numbered by yellow labels left to right, top to bottom. Each needs a PBR material class '
            'for RTX path tracing. Classes:\n%s\n'
            'Below, per number: texture path | faces | maps | light%% (faces flagged as light sources) | trans%% | '
            'brush contents. Decide from what the thumbnail shows; the path is only a hint (first folder = area, '
            'base name = the artist\'s abbreviation). Use "default" only when the image shows no recognisable '
            'material (flat colour, noise). Confidence: high only when the image is unambiguous.\n'
            'Answer only JSON: {"1": {"class": "...", "confidence": "high|medium|low", "why": "<= 8 words, what you '
            'see"}, ...}\nTextures:\n%s' % (len(rows), cls, tex))


def vision_validate(got, chunk, classes):
    return validate({n: got.get(str(i + 1)) for i, n in enumerate(chunk)}, chunk, classes)


def vision_pick(results, use, rules, files, picks=PICKS, seed=6):
    """texture names to show, in order, from comma-separated sets (NAME[:N]): calib = a high-confidence name rule
    and Jev give the same class (spread over the classes), conflicts = rule vs Jev, unclassified = no name rule
    (most faces first), jev = random Jev-classified textures, top = most faces; only textures with an image"""
    import random
    live = {n: r for n, r in results.items() if r['class'] != 'skip' and n in files}
    bare = {n: classify(n, use.get(n), rules) for n in live}
    out = []
    for p in picks.split(','):
        what, _, num = p.partition(':')
        num = int(num) if num else None
        if what == 'calib':
            by = {}
            for n in sorted(live):
                j = live[n].get('jev')
                if j and bare[n]['source'] == 'rule' and bare[n]['confidence'] == 'high' and j['class'] == bare[n]['class']:
                    by.setdefault(j['class'], []).append(n)
            for v in by.values():
                random.Random(seed).shuffle(v)
            got = [n for k in range(max(map(len, by.values()), default=0)) for c in sorted(by) for n in by[c][k:k + 1]]
        elif what == 'conflicts':
            got = sorted((n for n, r in live.items() if r['conflict']), key=lambda n: (-live[n]['faces'], n))
        elif what == 'unclassified':
            got = sorted((n for n in live if bare[n]['class'] == 'default'), key=lambda n: (-live[n]['faces'], n))
        elif what == 'jev':
            got = sorted(n for n, r in live.items() if r['source'] == 'jev')
            random.Random(seed).shuffle(got)
        elif what == 'top':
            got = sorted(live, key=lambda n: (-live[n]['faces'], n))
        else:
            raise ValueError('unknown pick %r' % what)
        out += [n for n in got if n not in out][:num]
    return out


def run_vision(names, use, rules, files, cache_path=VISION_CACHE, max_usd=1.0):
    import io
    jc = _load('jev_classify')
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    def ask(key, chunk, log):
        buf = io.BytesIO(); jc.contact_sheet([files[n] for n in chunk], VS_COLS).save(buf, 'PNG')
        got, _ = ds_ask(key, dsv_prompt(rules, [ds_row(n, use[n]) for n in chunk]), log, buf.getvalue())
        return vision_validate(got, chunk, rules['classes'])
    return ds_run(names, cache, cache_path, VS_COLS * VS_COLS, max_usd, 'deepseek vision', ask)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def load_ai(path):
    if not path or not os.path.exists(path):
        return {}
    return {n: v for n, v in json.load(open(path)).items() if v.get('class')}


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    rules = load_rules(opt('--rules', RULES))
    jev_path = opt('--classes', ''); ai_path = opt('--ai', AI_CACHE)
    review = int(opt('--review', '150')); max_usd = float(opt('--max-usd', '1.0'))
    vgame = opt('--deepseek-vision', ''); picks = opt('--pick', PICKS)
    vision_path = opt('--vision', VISION_CACHE if vgame else '')
    use_ds = '--deepseek' in args
    if use_ds:
        args.remove('--deepseek')
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    outdir, maps = args[0], args[1:]
    jev = {k: v for k, v in json.load(open(jev_path)).items() if not k.startswith('_')} if jev_path else {}
    results, use = classify_all(maps, rules, jev, load_ai(ai_path), load_ai(vision_path))
    if use_ds:
        run_deepseek(results, use, rules, ai_path, review, max_usd)
    if vgame:
        files = _load('jev_classify').texture_files(vgame)
        run_vision(vision_pick(results, use, rules, files, picks), use, rules, files, vision_path, max_usd)
    if use_ds or vgame:
        results, use = classify_all(maps, rules, jev, load_ai(ai_path), load_ai(vision_path))
    os.makedirs(outdir, exist_ok=True)
    json.dump(results, open(os.path.join(outdir, 'pbr_classes.json'), 'w'), indent=1, sort_keys=True)
    open(os.path.join(outdir, 'pbr_report.md'), 'w').write(report(results))
    print(', '.join('%s %d' % kv for kv in Counter(r['class'] for r in results.values()).most_common()))
    print('%d uncertain, %d conflicts -> %s' % (sum(1 for r in results.values() if uncertain(r)),
                                                 sum(1 for r in results.values() if r['conflict']),
                                                 os.path.join(outdir, 'pbr_report.md')))


if __name__ == '__main__':
    main()
