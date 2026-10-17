#!/usr/bin/env python3
"""Remix materials for procedural textures frozen by QindieGL's `proctex` option (e.g. the Levant lava).

usage: proctex_layer.py MODDIR GAMEDIR [NAME=IMAGE:INTENSITY ...]

Anachronox regenerates "interform" textures (ATD files, e.g. textures/levant/proc_lava) every frame, so Remix
sees a new texture hash every frame. With `proctex = 1` (and `proctex_names`, default "proc_lava") in
QindieGL.ini, QindieGL freezes them: level 0 becomes one flat colour, (fnv1a32(name) & 0xFFFFFF) as RGB, alpha
255, so the Remix hash is XXH3_64 over w*h pixels of bytes (B, G, R, 255). QindieGL.log prints the actual hash
("ProcTex: ... frozen ..., Remix texture hash ..."); it must match the one printed here.

Default materials: the two lava textures get the HD lava image from the texture pack as diffuse and emissive.
Writes MODDIR/proctex.usda and MODDIR/hd/proctex/*.dds; add @./proctex.usda@ to mod.usda's subLayers.
"""
import glob, importlib.util, os, re, sys
import xxhash
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('make_layers', os.path.join(here, 'make_layers.py'))
layers = importlib.util.module_from_spec(spec); spec.loader.exec_module(layers)

DEFAULT = {
    'textures/levant/proc_lava': ('levant/lava', 8.0),
    'textures/levant/proc_lavafloe': ('levant/lavaflow', 8.0),
}


def fnv1a32(s):
    h = 0x811C9DC5
    for c in s.encode():
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


def atd_size(gamedir, name):
    """width/height from the ATD file (default 256x256)"""
    rel = name[len('textures/'):] if name.startswith('textures/') else name
    for p in glob.glob(os.path.join(gamedir, 'anoxdata', 'textures', rel + '.atd')):
        txt = open(p, errors='replace').read()
        w = re.search(r'^\s*width\s*=\s*(\d+)', txt, re.M); h = re.search(r'^\s*height\s*=\s*(\d+)', txt, re.M)
        if w and h:
            return int(w.group(1)), int(h.group(1))
    return 256, 256


def proxy_hash(name, w, h):
    c = fnv1a32(name.lower()) & 0xFFFFFF
    px = bytes(((c) & 255, (c >> 8) & 255, (c >> 16) & 255, 255))   # B, G, R, A
    return xxhash.xxh3_64_intdigest(px * (w * h)), c


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    moddir, gamedir = sys.argv[1], sys.argv[2]
    mats = dict(DEFAULT)
    for a in sys.argv[3:]:
        name, rest = a.split('=', 1)
        img, inten = rest.rsplit(':', 1)
        mats[name.lower()] = (img, float(inten))
    root = os.path.join(gamedir, 'anoxdata', 'textures')
    outdir = os.path.join(moddir, 'hd', 'proctex'); os.makedirs(outdir, exist_ok=True)
    out = layers.header()
    for name, (img, inten) in sorted(mats.items()):
        w, h = atd_size(gamedir, name)
        hsh, col = proxy_hash(name, w, h)
        src = (glob.glob(os.path.join(root, img + '.*')) or [None])[0]
        if not src:
            print('%s: no image %s, skipped' % (name, img)); continue
        tmp = os.path.join(outdir, '_tmp.png')
        Image.open(src).convert('RGB').save(tmp)
        dds = os.path.join(outdir, '%016X.dds' % hsh)
        layers.dds(tmp, dds); os.remove(tmp)
        rel = os.path.relpath(dds, moddir).replace(os.sep, '/')
        out += ['        # %s (frozen %dx%d, colour %06X) <- %s' % (name, w, h, col, img),
                '        over "mat_%016X"' % hsh, '        {', '            over "Shader"', '            {',
                '                asset inputs:diffuse_texture = @./%s@ (' % rel, '                    colorSpace = "auto"',
                '                )',
                '                bool inputs:enable_emission = 1',
                '                asset inputs:emissive_mask_texture = @./%s@ (' % rel, '                    colorSpace = "auto"',
                '                )',
                '                float inputs:emissive_intensity = %g' % inten,
                '                float inputs:reflection_roughness_constant = 0.6',
                '            }', '        }', '']
        print('%s  %dx%d  colour %06X  hash 0x%016X' % (name, w, h, col, hsh))
    open(os.path.join(moddir, 'proctex.usda'), 'w').write('\n'.join(out + layers.footer()))


if __name__ == '__main__':
    main()
