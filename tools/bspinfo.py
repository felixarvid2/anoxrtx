#!/usr/bin/env python3
"""Read Anachronox (Quake 2 IBSP v38) maps: lights, sky and water surfaces.

usage: bspinfo.py summary MAP.bsp...        classname counts, worldspawn keys, sky, water textures
       bspinfo.py lights MAP.bsp            light entities as tab-separated origin/colour/intensity
       bspinfo.py json MAP.bsp              everything above as JSON

Quake 2 BSP: header "IBSP", int version 38, 19 lumps (offset, length). Lump 0 = entity text,
lump 5 = texinfo (76 bytes: vecs[8] float, int flags, int value, char texture[32], int next).
Surface flags: SURF_LIGHT 0x1, SURF_SKY 0x4, SURF_WARP 0x8 (water/lava/slime), SURF_TRANS33 0x10,
SURF_TRANS66 0x20.
"""
import json, re, struct, sys
from collections import Counter

SURF_LIGHT, SURF_SKY, SURF_WARP = 0x1, 0x4, 0x8


def load(path):
    data = open(path, 'rb').read()
    magic, ver = struct.unpack_from('<4si', data, 0)
    if magic != b'IBSP':
        raise SystemExit('%s: not IBSP' % path)
    lumps = [struct.unpack_from('<ii', data, 8 + 8 * i) for i in range(19)]
    off, ln = lumps[0]
    text = data[off:off + ln].split(b'\0', 1)[0].decode('latin-1')
    ents = []
    for block in re.findall(r'\{([^{}]*)\}', text):
        ents.append(dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', block)))
    off, ln = lumps[5]
    texinfo = []
    for i in range(off, off + ln - 75, 76):
        flags, value = struct.unpack_from('<ii', data, i + 32)
        name = data[i + 40:i + 72].split(b'\0', 1)[0].decode('latin-1')
        texinfo.append((name, flags, value))
    return ver, ents, texinfo


def vec(s, default=(0.0, 0.0, 0.0)):
    try:
        v = [float(x) for x in s.split()]
        return v if len(v) == 3 else list(default)
    except (AttributeError, ValueError):
        return list(default)


def lights(ents):
    out = []
    for e in ents:
        if e.get('classname', '').startswith('light'):
            out.append({'classname': e['classname'], 'origin': vec(e.get('origin')),
                        'color': vec(e.get('_color') or e.get('color'), (1, 1, 1)),
                        'light': float(e.get('light', e.get('_light', 300)) or 300),
                        'style': e.get('style', ''), 'target': e.get('target', ''),
                        'targetname': e.get('targetname', ''), 'keys': e})
    return out


def info(path):
    ver, ents, tex = load(path)
    world = ents[0] if ents else {}
    return {'map': path.rsplit('/', 1)[-1], 'version': ver,
            'classnames': Counter(e.get('classname', '?') for e in ents).most_common(),
            'worldspawn': world,
            'sky': world.get('sky', ''),
            'sky_textures': sorted({n for n, f, v in tex if f & SURF_SKY}),
            'water_textures': sorted({n for n, f, v in tex if f & SURF_WARP}),
            'light_textures': sorted({'%s(%d)' % (n, v) for n, f, v in tex if f & SURF_LIGHT}),
            'lights': lights(ents)}


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'summary':
        for p in sys.argv[2:]:
            i = info(p)
            print('%-22s v%d ents=%d lights=%d sky=%r skytex=%s water=%s' % (
                i['map'], i['version'], sum(c for _, c in i['classnames']), len(i['lights']), i['sky'],
                ','.join(i['sky_textures'][:3]), ','.join(i['water_textures'][:4])))
    elif cmd == 'lights':
        for l in info(sys.argv[2])['lights']:
            print('%s\t%.1f %.1f %.1f\t%.2f %.2f %.2f\t%g\t%s' % (l['classname'], *l['origin'], *l['color'], l['light'], l['style']))
    elif cmd == 'json':
        i = info(sys.argv[2]); i['classnames'] = dict(i['classnames'])
        print(json.dumps(i, indent=1))
    else:
        print(__doc__); sys.exit(1)


if __name__ == '__main__':
    main()
