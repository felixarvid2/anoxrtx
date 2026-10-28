#!/usr/bin/env python3
"""Classify level textures with TypeSafe Jev (decision model) for the PBR/emissive layers.

usage: jev_classify.py GAMEDIR OUT.json MAP.bsp... [--gemini] [--limit N] [--max-tokens N] [--only NAME,NAME]
                       [--workers N]

For every texture the maps use that exists in the loose texture pack (GAMEDIR/anoxdata/textures), this
describes the image in words from local statistics (colour, saturation, brightness, contrast, edge density,
straight-line structure) and asks Jev, together with the texture path:
  material   choice: metal, wood, stone, concrete, tile, glass, fabric, organic, screen
  roughness  score 0..4 (mirror polished .. completely matte)
  metal      yes/no probability
  emissive   yes/no probability that the surface is a light source/screen/sign that glows
With --gemini, Gemini (free tier, gemini-3.1-flash-lite) first looks at the textures: 16 at a time on a numbered
contact sheet of 128 px thumbnails, it writes a short visual description of each (material, finish, glowing
parts). Jev then decides from that description, the statistics and the path. Gemini descriptions are cached
in the same file; at most one Gemini request every 4 s, and a quota/API error stops the run (no retries).
Sending the thumbnails was approved by the owner (Felix) on 2026-10-18 for this classification only.

Results are cached in OUT.json (rerunning only asks for textures not in it), so a rerun costs nothing.
`tools/pbr_layer.py --classes OUT.json` uses them instead of its name keywords.

Cost guard: stops when the tokens used in this run reach --max-tokens (default 3,000,000; one texture is about
500 tokens). The API key is read from ~/Documents/jev-api.md (or $TYPESAFE_API_KEY) and sent only as a header.
Jev only receives texture paths and text descriptions; with --gemini, Gemini receives the thumbnails.
"""
import concurrent.futures, glob, importlib.util, json, os, sys, threading, urllib.error, urllib.request
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-1.13.0'   # pinned so cached answers stay comparable
MATERIALS = {
    'metal': 'metal: steel, iron, pipes, grates, machinery, metal panels',
    'wood': 'wood: planks, crates, furniture, bark',
    'stone': 'stone or brick: rock, cave walls, bricks, cobbles',
    'concrete': 'concrete or plaster: smooth or stained walls, cement, ceilings',
    'tile': 'tiles or polished floor: ceramic, marble, polished stone',
    'glass': 'glass: windows, glass panels',
    'fabric': 'fabric: cloth, carpet, curtains, upholstery',
    'organic': 'organic: dirt, grass, plants, flesh, slime, lava',
    'screen': 'screen, sign or light: monitors, displays, neon, lamps, posters',
}
ROUGHNESS = ['mirror polished', 'glossy', 'satin', 'rough', 'completely matte']
QUESTIONS = {
    'material': {'type': 'choice', 'instructions': 'Which material is this game texture most likely depicting?',
                 'criteria': MATERIALS},
    'roughness': {'type': 'score', 'instructions': 'How rough or matte would this surface be in reality?',
                  'criteria': ROUGHNESS},
    'metal': {'type': 'noul', 'instructions': 'Is the surface bare metal (conductive, metallic reflections)?'},
    'emissive': {'type': 'noul', 'instructions': 'Is this surface a light source, glowing sign, lit screen or '
                                                 'lamp that would emit light?'},
}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def colour_name(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 40: return 'near black'
    if mx - mn < 20: return 'grey' if mx < 200 else 'white'
    h = {r: 'red', g: 'green', b: 'blue'}[mx]
    if r > 150 and g > 110 and b < 90: h = 'yellow/orange'
    elif r > 120 and g < 90 and b > 120: h = 'purple'
    elif g > 100 and b > 100 and r < 90: h = 'cyan/teal'
    elif r > 90 and g > 60 and b < 60 and r > g: h = 'brown' if mx < 170 else 'orange'
    return h


def describe(path):
    im = Image.open(path).convert('RGB')
    im.thumbnail((256, 256))
    a = np.asarray(im, dtype=np.float32)
    r, g, b = a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean()
    lum = a.mean(axis=2)
    sat = (a.max(axis=2) - a.min(axis=2)).mean()
    gx = np.abs(np.diff(lum, axis=1)).mean(); gy = np.abs(np.diff(lum, axis=0)).mean()
    edges = (gx + gy) / 2
    # straight structure: strong edges concentrated in whole rows/columns (panels, grids, bricks)
    col = np.abs(np.diff(lum, axis=1)).mean(axis=0); row = np.abs(np.diff(lum, axis=0)).mean(axis=1)
    straight = (np.percentile(col, 95) + np.percentile(row, 95)) / (2 * edges + 1e-3)
    bright_spots = (lum > 220).mean() * 100
    def lvl(v, cuts, words):
        for c, w in zip(cuts, words):
            if v < c: return w
        return words[-1]
    return ('Average colour %s (RGB %d %d %d); %s saturation; %s brightness; %s contrast; %s fine detail; '
            '%s straight-line structure (panels, grids, bricks); %.1f%% very bright pixels; %dx%d pixels.' % (
                colour_name(r, g, b), r, g, b,
                lvl(sat, [15, 40, 80], ['very low', 'low', 'medium', 'high']),
                lvl(lum.mean(), [50, 100, 160], ['very dark', 'dark', 'medium', 'bright']),
                lvl(lum.std(), [15, 35, 60], ['very low', 'low', 'medium', 'high']),
                lvl(edges, [3, 8, 16], ['very little', 'little', 'some', 'a lot of']),
                lvl(straight, [1.6, 2.4, 3.5], ['no', 'weak', 'clear', 'strong']),
                bright_spots, Image.open(path).size[0], Image.open(path).size[1]))


GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent'
SHEET = 16


def texture_files(gamedir):
    """{texture name: image path} in the loose texture pack GAMEDIR/anoxdata/textures"""
    root = os.path.join(gamedir, 'anoxdata', 'textures')
    files = {}
    for p in sorted(glob.glob(os.path.join(root, '**', '*.*'), recursive=True)):
        if os.path.splitext(p)[1].lower() not in ('.png', '.tga', '.jpg', '.jpeg', '.pcx', '.bmp'):
            continue   # .atd animation/procedural definitions are not images
        files.setdefault(os.path.splitext(os.path.relpath(p, root).replace('\\', '/').lower())[0], p)
    return files


def contact_sheet(paths, cols=4):
    """grid of 128 px thumbnails (cols x cols), each numbered in its top-left corner"""
    from PIL import ImageDraw
    rows = max(1, (len(paths) + cols - 1) // cols)
    sheet = Image.new('RGB', (cols * 136, rows * 136), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        im = Image.open(p).convert('RGB').resize((128, 128), Image.LANCZOS)
        x, y = (i % cols) * 136 + 4, (i // cols) * 136 + 4
        sheet.paste(im, (x, y))
        dr.rectangle((x, y, x + 22, y + 16), fill=(255, 255, 0))
        dr.text((x + 3, y + 2), str(i + 1), fill=(0, 0, 0))
    return sheet


def gemini_describe(gkey, names, paths):
    """one request: numbered contact sheet -> {name: description}"""
    import base64, io
    buf = io.BytesIO(); contact_sheet(paths).save(buf, 'PNG')
    listing = '\n'.join('%d: %s' % (i + 1, n) for i, n in enumerate(names))
    prompt = ('The image shows %d numbered game textures (yellow labels) from the 2001 PC game Anachronox. '
              'File paths:\n%s\nFor each number, describe in at most 25 words what real-world material the '
              'surface depicts (metal, wood, stone, concrete, tiles, glass, fabric, organic, screen/sign/light), '
              'its finish (polished, glossy, rough, rusty, dirty) and whether any part glows or is a light, screen '
              'or sign. Answer only with JSON: {"1": "...", "2": "..."}' % (len(names), listing))
    body = json.dumps({'contents': [{'parts': [{'inline_data': {'mime_type': 'image/png',
                                                                  'data': base64.b64encode(buf.getvalue()).decode()}},
                                               {'text': prompt}]}],
                       'generationConfig': {'temperature': 0.1, 'responseMimeType': 'application/json',
                                            'maxOutputTokens': 4096}}).encode()
    req = urllib.request.Request(GEMINI_URL, body, {'Content-Type': 'application/json', 'x-goog-api-key': gkey})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        raise RuntimeError('Gemini HTTP %d (stopping, no retry): %s' % (e.code, e.read()[:300].decode(errors='replace')))
    text = ''.join(p.get('text', '') for p in d['candidates'][0]['content']['parts'])
    got = json.loads(text[text.find('{'):text.rfind('}') + 1])
    return {n: str(got.get(str(i + 1), '')).strip() for i, n in enumerate(names)}


def ask(key, name, desc, visual=''):
    state = ('Texture from the 2001 science-fiction game Anachronox. File path: %s. %s'
             'Image statistics: %s' % (name, ('What the texture shows: %s. ' % visual) if visual else '', desc))
    body = json.dumps({'model': MODEL, 'state': state, 'questions': QUESTIONS}).encode()
    req = urllib.request.Request(URL, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise RuntimeError('Jev HTTP %d: %s' % (e.code, e.read()[:300].decode(errors='replace')))
    a = d['answers']
    return {
        'material': a['material']['choice'], 'material_conf': a['material']['confidence'],
        'roughness': round(a['roughness']['score'] / 4.0, 3),   # 0 = mirror .. 1 = matte
        'metal': a['metal']['noul'], 'emissive': a['emissive']['noul'],
        'tokens': d['usage']['input_tokens'] + d['usage']['output_tokens'], 'model': d['model'],
        'description': desc, 'visual': visual,
    }


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    limit = int(opt('--limit', '0')); max_tokens = int(opt('--max-tokens', '3000000'))
    workers = int(opt('--workers', '8')); only = set(opt('--only', '').split(',')) - {''}
    use_gemini = '--gemini' in args
    if use_gemini:
        args.remove('--gemini')
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    gamedir, out, maps = args[0], args[1], args[2:]
    key = os.environ.get('TYPESAFE_API_KEY') or open(os.path.expanduser('~/Documents/jev-api.md')).read().strip()
    bsp = _load('bspinfo')
    names = set()
    for m in maps:
        _, _, tex = bsp.load(m)
        for name, f, v in tex:
            if not f & 0xC:   # skip sky and liquids
                names.add(name.replace('\\', '/').lower())
    files = texture_files(gamedir)
    cache = json.load(open(out)) if os.path.exists(out) else {}
    todo = sorted(n for n in names if n in files and n not in cache and (not only or n in only))
    if limit:
        todo = todo[:limit]
    print('%d textures, %d cached, %d to ask' % (len(names & set(files)), len(cache), len(todo)), flush=True)
    visuals = {}
    if use_gemini:
        import time
        gkey = open(os.path.expanduser('~/Documents/gemini-api.md')).read().strip()
        vcache = cache.setdefault('_gemini', {})
        need = [n for n in todo if n not in vcache]
        for i in range(0, len(need), SHEET):
            chunk = need[i:i + SHEET]
            t0 = time.time()
            vcache.update(gemini_describe(gkey, chunk, [files[n] for n in chunk]))
            json.dump(cache, open(out, 'w'), indent=1, sort_keys=True)
            print('gemini: %d/%d described' % (min(i + SHEET, len(need)), len(need)), flush=True)
            time.sleep(max(0.0, 4.0 - (time.time() - t0)))
        visuals = vcache
    used = [0]; lock = threading.Lock(); stop = threading.Event()

    def work(n):
        if stop.is_set():
            return
        r = ask(key, n, describe(files[n]), visuals.get(n, ''))
        with lock:
            cache[n] = r; used[0] += r['tokens']
            if used[0] >= max_tokens:
                stop.set()
    try:
        with concurrent.futures.ThreadPoolExecutor(workers) as ex:
            for i, f in enumerate(concurrent.futures.as_completed([ex.submit(work, n) for n in todo])):
                f.result()
                if (i + 1) % 200 == 0:
                    print('%d/%d, %d tokens' % (i + 1, len(todo), used[0]), flush=True)
                    json.dump(cache, open(out, 'w'), indent=1, sort_keys=True)
    finally:
        json.dump(cache, open(out, 'w'), indent=1, sort_keys=True)
    print('done: %d textures classified, %d tokens this run%s -> %s' % (
        len(cache), used[0], ' (stopped at --max-tokens)' if stop.is_set() else '', out))


if __name__ == '__main__':
    main()
