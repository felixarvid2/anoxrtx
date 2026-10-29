#!/usr/bin/env -S sh -c 'exec "${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}" "$0" "$@"'
"""Ask DeepSeek how a Remix shot differs from the original renderer's shot of the same view.

usage: deepseek_compare.py ORIG.png REMIX.png [--note TEXT] [--gamma 1.4] [--size 512]

Both shots lose the top 40 rows (Remix welcome overlay); the original gets the same gamma correction as
ab_ev.py (v' = v^(1/gamma)). Each is shrunk to at most --size px on the long side, sent as JPEG to
deepseek-flash, and the answer (JSON: overall verdict plus a list of differences by image region) is printed.
--note adds context (map, what changed) to the prompt. Only these two thumbnails are sent (approved by Felix
on 2026-10-28); the key is read from ~/.config/anoxrtx/deepseek.key and only sent as a header. Stops on any
API error without retrying. Token counts go to stderr.
"""
import base64, io, json, os, sys, urllib.error, urllib.request
import numpy as np
from PIL import Image

DS_URL = 'https://api.deepseek.com/chat/completions'
DS_MODEL = 'deepseek-flash'

PROMPT = ('Two screenshots of the same view in Anachronox (2001, Quake 2 engine). Image 1 is the original '
          'renderer (baked lightmaps, the reference). Image 2 is the NVIDIA RTX Remix path-traced version, whose '
          'lights come from the map\'s light entities and emissive textures. Compare lighting only: overall '
          'exposure, light/dark regions, missing or extra light sources, colour tint, sky, fog, glass, shadows. '
          'Ignore resolution, sharpness, noise and texture detail. %s'
          'Answer only JSON: {"overall": "remix darker|remix brighter|similar", "ev_guess": <float, + = remix '
          'darker>, "differences": [{"region": "e.g. upper left, ceiling, far wall", "orig": "...", '
          '"remix": "...", "severity": "high|medium|low"}], "likely_cause": "<= 20 words"}')


def thumb(path, size, gamma=1.0):
    a = np.asarray(Image.open(path).convert('RGB'), dtype=np.float32)[40:] / 255.0
    if gamma != 1.0:
        a = a ** (1 / gamma)
    im = Image.fromarray((a * 255 + 0.5).astype(np.uint8))
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


def ask(images, prompt):
    key = open(os.path.expanduser('~/.config/anoxrtx/deepseek.key')).read().strip()
    content = [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(b).decode()}}
               for b in images] + [{'type': 'text', 'text': prompt}]
    body = json.dumps({'model': DS_MODEL, 'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
                       'response_format': {'type': 'json_object'}, 'max_tokens': 8000,
                       'reasoning_effort': 'low'}).encode()
    req = urllib.request.Request(DS_URL, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit('DeepSeek HTTP %d (stopping, no retry): %s' % (e.code, e.read()[:300].decode(errors='replace')))
    u = d.get('usage', {})
    print('usage', u.get('prompt_tokens'), u.get('completion_tokens'), file=sys.stderr)
    text = d['choices'][0]['message']['content']
    try:
        return json.loads(text[text.find('{'):text.rfind('}') + 1])
    except ValueError:
        sys.exit('DeepSeek answer is not JSON: ' + text[:2000])


def main():
    args = sys.argv[1:]
    opts = {'--note': '', '--gamma': '1.4', '--size': '512'}
    for k in opts:
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    orig, remix = args
    size = int(opts['--size'])
    images = [thumb(orig, size, float(opts['--gamma'])), thumb(remix, size)]
    note = opts['--note'] + ' ' if opts['--note'] else ''
    print(json.dumps(ask(images, PROMPT % note), indent=1))


if __name__ == '__main__':
    main()
