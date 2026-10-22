#!/usr/bin/env python3
"""Make light-emitting map surfaces (Quake 2 SURF_LIGHT texinfo) emissive Remix materials.

usage: emissive_layer.py MODDIR GAMEDIR MAP.bsp... [--pack] [--classes CLASSES.json [--glow-min 0.7]] [--models TSV]

Collects every texture used with SURF_LIGHT (0x1) in the given maps and its highest light value, and writes
MODDIR/emissive.usda (+ MODDIR/hd/emissive/*.dds): enable_emission, emissive_mask_texture = the texture,
emissive_intensity = clamp(value / 100, 1, 15).
Texture source / hash: with --pack the loose files in GAMEDIR/anoxdata/textures (e.g. Chuncki's 4x pack),
otherwise GAMEDIR/anoxdata/TEXTURES.dat (or TEXTURES.dat.orig). Add @./emissive.usda@ to mod.usda's subLayers.
Material overrides in mod.usda itself are stronger than this layer, so hand-made materials win.
--classes (tools/jev_classify.py output, needs --pack): textures Jev rates as glowing (emissive >= --glow-min)
that are not SURF_LIGHT also emit. Their mask keeps only the bright parts (luminance above the texture's 60th
percentile and at least 0.3, softened), so a lamp's frame stays dark; intensity 1.5..4 by Jev's probability.
They go to a separate layer, MODDIR/emissive_jev.usda (add @./emissive_jev.usda@ to mod.usda's subLayers), so
they can be switched off on their own.
--models TSV (maps/model_emission.tsv): model textures that emit, one per line "PATH<TAB>INTENSITY<TAB>note" with
PATH as in MODELS.dat (e.g. background/sml_wall2.tga). For props the original lights with the model light
(entity.dat lighting 1) that path tracing leaves nearly black, e.g. background buildings. The whole texture is the
mask (from MODELS.dat, so it does not depend on the HD model pack); they go into emissive.usda.
"""
import glob, importlib.util, io, os, sys

here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
bspinfo, rh, adat, layers = _load('bspinfo'), _load('remixhash'), _load('adat'), _load('make_layers')

SURF_LIGHT, SURF_SKY, SURF_WARP = 0x1, 0x4, 0x8


def main():
    argv = sys.argv[1:]
    def opt(n, default):
        if n in argv:
            i = argv.index(n); v = argv[i + 1]; del argv[i:i + 2]; return v
        return default
    classes = opt('--classes', ''); glow_min = float(opt('--glow-min', '0.7')); models = opt('--models', '')
    args = [a for a in argv if not a.startswith('--')]
    pack = '--pack' in argv
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
    nmodel = 0
    if models:
        from PIL import Image
        mdat = os.path.join(gamedir, 'anoxdata', 'MODELS.dat')
        mfiles = {name.replace('\\', '/').lower(): (o, n, c) for name, o, n, c in adat.entries(mdat)}
        for line in open(models):
            t = line.rstrip('\n').split('\t')
            if not t[0] or t[0].startswith('#') or len(t) < 2:
                continue
            k = t[0].lower()
            if k not in mfiles:
                missing.append(k); continue
            with open(mdat, 'rb') as f:
                img = io.BytesIO(adat.read(f, *mfiles[k]))
            h, _ = rh.remix_hash(img)
            if h in done:
                continue
            done.add(h); img.seek(0)
            base = 'model__' + os.path.splitext(k)[0].replace('/', '__').replace(' ', '_')
            png = os.path.join(tmp, base + '.png')
            Image.open(img).convert('RGBA').save(png)
            dds = os.path.join(tmp, base + '.dds')
            layers.dds(png, dds); os.remove(png)
            rel = os.path.relpath(dds, moddir).replace(os.sep, '/')
            out += ['        # %s (model%s)' % (k, ', ' + t[2] if len(t) > 2 and t[2] else ''), '        over "mat_%016X"' % h,
                    '        {', '            over "Shader"', '            {',
                    '                bool inputs:enable_emission = 1',
                    '                asset inputs:emissive_mask_texture = @./%s@ (' % rel,
                    '                    colorSpace = "auto"', '                )',
                    '                float inputs:emissive_intensity = %g' % float(t[1]),
                    '            }', '        }', '']
            nmodel += 1
    njev = 0
    jout = layers.header()
    if classes:
        import json
        import numpy as np
        from PIL import Image, ImageFilter
        jev = {k: v for k, v in json.load(open(classes)).items() if not k.startswith('_')}
        skip = set()
        for m in maps:
            _, _, tex = bspinfo.load(m)
            for name, flags, value in tex:
                if flags & (SURF_SKY | SURF_WARP):
                    skip.add(name.replace('\\', '/').lower())
        for k, c in sorted(jev.items()):
            if c['emissive'] < glow_min or k in want or k in skip or k not in files or files[k][0] != 'file':
                continue
            path = files[k][1]
            try:
                h, _ = rh.remix_hash(path)
            except Exception:
                continue
            if h in done:
                continue
            done.add(h)
            rgb = Image.open(path).convert('RGB')
            a = np.asarray(rgb, dtype=np.float32) / 255.0
            lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
            t = max(0.3, float(np.percentile(lum, 60)))
            w = np.clip((lum - t) / max(1e-3, 1.0 - t) * 3.0, 0.0, 1.0)
            wim = Image.fromarray((w * 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(1.0))
            w = np.asarray(wim, dtype=np.float32)[..., None] / 255.0
            base = k.replace('/', '__') + '.jev'
            png = os.path.join(tmp, base + '.png')
            Image.fromarray((a * w * 255).astype(np.uint8), 'RGB').save(png)
            dds = os.path.join(tmp, base + '.dds')
            layers.dds(png, dds); os.remove(png)
            rel = os.path.relpath(dds, moddir).replace(os.sep, '/')
            inten = round(1.5 + 2.5 * (c['emissive'] - glow_min) / max(1e-3, 1.0 - glow_min), 2)
            jout += ['        # %s (Jev glow %.2f, %s)' % (k, c['emissive'], c['material']), '        over "mat_%016X"' % h,
                    '        {', '            over "Shader"', '            {',
                    '                bool inputs:enable_emission = 1',
                    '                asset inputs:emissive_mask_texture = @./%s@ (' % rel,
                    '                    colorSpace = "auto"', '                )',
                    '                float inputs:emissive_intensity = %g' % inten,
                    '            }', '        }', '']
            njev += 1
    open(os.path.join(moddir, 'emissive.usda'), 'w').write('\n'.join(out + layers.footer()))
    if classes:
        open(os.path.join(moddir, 'emissive_jev.usda'), 'w').write('\n'.join(jout + layers.footer()))
    print('%d light textures, %d emissive materials (%d from Jev glow >= %g, %d model textures), %d not found%s' % (
          len(want), len(done), njev, glow_min, nmodel, len(missing), (': ' + ', '.join(missing[:10])) if missing else ''))


if __name__ == '__main__':
    main()
