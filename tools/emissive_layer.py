#!/usr/bin/env python3
"""Make light-emitting map surfaces (Quake 2 SURF_LIGHT texinfo) emissive Remix materials.

usage: emissive_layer.py MODDIR GAMEDIR MAP.bsp... [--pack]

Collects every texture used with SURF_LIGHT (0x1) in the given maps and its highest light value, and writes
MODDIR/emissive.usda (+ MODDIR/hd/emissive/*.dds): enable_emission, emissive_mask_texture = the texture,
emissive_intensity = clamp(value / 100, 1, 15).
Texture source / hash: with --pack the loose files in GAMEDIR/anoxdata/textures (e.g. Chuncki's 4x pack),
otherwise GAMEDIR/anoxdata/TEXTURES.dat (or TEXTURES.dat.orig). Add @./emissive.usda@ to mod.usda's subLayers.
Material overrides in mod.usda itself are stronger than this layer, so hand-made materials win.
"""
import glob, importlib.util, io, os, sys

here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
bspinfo, rh, adat, layers = _load('bspinfo'), _load('remixhash'), _load('adat'), _load('make_layers')

SURF_LIGHT, SURF_SKY, SURF_WARP = 0x1, 0x4, 0x8


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    pack = '--pack' in sys.argv
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    moddir, gamedir, maps = args[0], args[1], args[2:]
    want = {}
    for m in maps:
        _, _, tex = bspinfo.load(m)
        for name, flags, value in tex:
            if flags & SURF_LIGHT and not flags & (SURF_SKY | SURF_WARP) and value > 0:
                k = name.replace('\\', '/').lower()
                want[k] = max(want.get(k, 0), value)

    files = {}
    if pack:
        root = os.path.join(gamedir, 'anoxdata', 'textures')
        for p in glob.glob(os.path.join(root, '**', '*.*'), recursive=True):
            files[os.path.splitext(os.path.relpath(p, root).replace('\\', '/').lower())[0]] = ('file', p)
    else:
        dat = os.path.join(gamedir, 'anoxdata', 'TEXTURES.dat')
        dat = dat if os.path.exists(dat) else dat + '.orig'
        for name, o, n, c in adat.entries(dat):
            files[os.path.splitext(name.replace('\\', '/').lower())[0]] = ('dat', (dat, o, n, c))

    out = layers.header(); done = set(); missing = []
    tmp = os.path.join(moddir, 'hd', 'emissive'); os.makedirs(tmp, exist_ok=True)
    for k, value in sorted(want.items()):
        src = files.get(k)
        if not src:
            missing.append(k); continue
        if src[0] == 'file':
            img = src[1]
        else:
            dat, o, n, c = src[1]
            with open(dat, 'rb') as f:
                img = io.BytesIO(adat.read(f, o, n, c))
        try:
            h, _ = rh.remix_hash(img)
        except Exception:
            missing.append(k); continue
        if h in done:
            continue
        done.add(h)
        png = os.path.join(tmp, k.replace('/', '__') + '.png')
        from PIL import Image
        if hasattr(img, 'seek'):
            img.seek(0)
        Image.open(img).convert('RGBA').save(png)
        dds = os.path.join(tmp, k.replace('/', '__') + '.dds')
        layers.dds(png, dds); os.remove(png)
        rel = os.path.relpath(dds, moddir).replace(os.sep, '/')
        inten = min(15.0, max(1.0, value / 100.0))
        out += ['        # %s (light %d)' % (k, value), '        over "mat_%016X"' % h, '        {',
                '            over "Shader"', '            {',
                '                bool inputs:enable_emission = 1',
                '                asset inputs:emissive_mask_texture = @./%s@ (' % rel,
                '                    colorSpace = "auto"', '                )',
                '                float inputs:emissive_intensity = %g' % inten,
                '            }', '        }', '']
    open(os.path.join(moddir, 'emissive.usda'), 'w').write('\n'.join(out + layers.footer()))
    print('%d light textures, %d emissive materials, %d not found%s' % (len(want), len(done), len(missing),
          (': ' + ', '.join(missing[:10])) if missing else ''))


if __name__ == '__main__':
    main()
