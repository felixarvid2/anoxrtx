#!/usr/bin/env python3
"""Approximate PBR materials for the level textures: normal maps, roughness/metallic, glass.

usage: pbr_layer.py MODDIR GAMEDIR MAP.bsp... [--max 512] [--strength 2.0] [--only NAME,NAME]

For every texture the maps use (BSP texinfo) that exists in the loose texture pack in GAMEDIR/anoxdata/textures
(e.g. Chuncki's 4x pack; hashes via remixhash.py, so the pack must be what the game loads):
- normal map: the texture's luminance as a height field (blurred, Sobel, wraps around since textures tile),
  encoded the way Remix reads `normalmap_texture` (unorm hemi-octahedral in R/G: t = n.xy / (|x|+|y|+|z|),
  p = (t.x + t.y, t.x - t.y)), DirectX tangent space, written as DXT1 with mips, longest side <= --max;
- reflection_roughness_constant / metallic_constant from keywords in the texture name (see CLASSES), or with
  --classes CLASSES.json from tools/jev_classify.py (Gemini looks, Jev decides): roughness = Jev's score
  (clamped 0.05..1), metallic = Jev's metal probability when it is at least 0.5, otherwise 0; textures missing
  from the file fall back to the keywords;
- glass: SURF_TRANS33/66 textures named glass/win/clear become thin-walled AperturePBR_Translucent with
  the texture as transmittance (not HAZE_GLASS: haze sheets keep Remix' blended look).
Sky (SURF_SKY) and liquid (SURF_WARP) surfaces are skipped (liquids.usda handles those), and so are HAZE_GLASS.
Writes MODDIR/pbr.usda and MODDIR/hd/pbr/. Add @./pbr.usda@ to mod.usda's subLayers; overrides in mod.usda,
emissive.usda and liquids.usda keep their own values where they set the same inputs.
Needs: pillow, numpy, xxhash.
"""
import glob, importlib.util, os, sys
import numpy as np
from PIL import Image, ImageFilter

here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
bspinfo, rh, layers = _load('bspinfo'), _load('remixhash'), _load('make_layers')

SURF_SKY, SURF_WARP, SURF_TRANS33, SURF_TRANS66 = 0x4, 0x8, 0x10, 0x20

# (keywords in the texture path, roughness, metallic); first match wins, DEFAULT otherwise
CLASSES = [
    (('glass', 'window', 'win', 'clear', 'mirror', 'chrome'), 0.25, 0.0),   # mostly opaque facades with windows
    (('monitor', 'screen', 'scrn', 'monitext', 'comp', 'ssmon'), 0.2, 0.0),
    (('metl', 'mtl', 'metal', 'steel', 'iron', 'pipe', 'grate', 'girder', 'vent', 'panel', 'rail', 'tank'), 0.45, 0.6),
    (('door', 'trim', 'tech', 'electro', 'power'), 0.5, 0.3),
    (('marble', 'tile', 'polish'), 0.3, 0.0),
    (('wood', 'parquet', 'crate', 'plank', 'cabinet', 'bar'), 0.6, 0.0),
    (('rock', 'stone', 'brick', 'concrete', 'cement', 'dirt', 'sand', 'ground', 'cave', 'plaster'), 0.85, 0.0),
    (('carpet', 'curtain', 'cloth', 'fabric', 'bed'), 0.95, 0.0),
]
DEFAULT = (0.7, 0.0)
GLASS_WORDS = ('glass', 'win', 'clear')
# translucent haze sheets, not clear glass: the original blends their light texture at 33 % over the view (the haze
# over the city in labbuilding); as clear AperturePBR_Translucent glass the haze is gone and the room reflects in it
HAZE_GLASS = ('sunder/sun_glass3',)


def classify(name):
    base = name.split('/')[-1]
    for words, rough, metal in CLASSES:
        if any(w in base for w in words):
            return rough, metal
    return DEFAULT


def normal_map(path, maxside, strength):
    im = Image.open(path).convert('L')
    if max(im.size) > maxside:
        s = maxside / max(im.size)
        im = im.resize((max(4, int(im.width * s)), max(4, int(im.height * s))), Image.LANCZOS)
    h = np.asarray(im.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
    # Sobel with wrap-around (tiling textures); x = +u (right), y = +v (down): DirectX tangent space
    def sh(a, dy, dx): return np.roll(np.roll(a, dy, 0), dx, 1)
    gx = (sh(h, 1, -1) + 2 * sh(h, 0, -1) + sh(h, -1, -1)) - (sh(h, 1, 1) + 2 * sh(h, 0, 1) + sh(h, -1, 1))
    gy = (sh(h, -1, 1) + 2 * sh(h, -1, 0) + sh(h, -1, -1)) - (sh(h, 1, 1) + 2 * sh(h, 1, 0) + sh(h, 1, -1))
    scale = strength * max(im.size) / 512.0      # same bump per texel area whatever the resolution
    nx, ny, nz = -gx * scale, -gy * scale, np.ones_like(h)
    l1 = np.abs(nx) + np.abs(ny) + nz
    tx, ty = nx / l1, ny / l1
    px, py = tx + ty, tx - ty                     # hemi-octahedral, decoded by Remix as t = ((px+py)/2, (px-py)/2)
    rgb = np.zeros(h.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = np.clip((px * 0.5 + 0.5) * 255 + 0.5, 0, 255)
    rgb[..., 1] = np.clip((py * 0.5 + 0.5) * 255 + 0.5, 0, 255)
    return Image.fromarray(rgb, 'RGB')


def main():
    args = sys.argv[1:]
    def opt(name, default):
        if name in args:
            i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    maxside = int(opt('--max', '512')); strength = float(opt('--strength', '2.0'))
    only = set(opt('--only', '').split(',')) - {''}
    classes_file = opt('--classes', '')
    jev = {}
    if classes_file:
        import json
        jev = {k: v for k, v in json.load(open(classes_file)).items() if not k.startswith('_')}
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    moddir, gamedir, maps = args[0], args[1], args[2:]

    flags = {}
    for m in maps:
        _, _, tex = bspinfo.load(m)
        for name, f, v in tex:
            k = name.replace('\\', '/').lower()
            flags[k] = flags.get(k, 0) | f
    root = os.path.join(gamedir, 'anoxdata', 'textures')
    files = {}
    for p in glob.glob(os.path.join(root, '**', '*.*'), recursive=True):
        files.setdefault(os.path.splitext(os.path.relpath(p, root).replace('\\', '/').lower())[0], p)

    outdir = os.path.join(moddir, 'hd', 'pbr'); os.makedirs(outdir, exist_ok=True)
    tmp = os.path.join(outdir, '_tmp.png')
    out = layers.header(); done = set(); n = nglass = nskip = njev = 0
    for k in sorted(flags):
        f = flags[k]
        if (only and k not in only) or f & (SURF_SKY | SURF_WARP) or k not in files or k in HAZE_GLASS:
            nskip += 1; continue
        try:
            h, _ = rh.remix_hash(files[k])
        except Exception:
            nskip += 1; continue
        if h in done:
            continue
        done.add(h)
        hx = '%016X' % h
        if k in jev:
            rough = round(min(1.0, max(0.05, jev[k]['roughness'])), 3)
            metal = round(jev[k]['metal'], 3) if jev[k]['metal'] >= 0.5 else 0.0
            njev += 1
        else:
            rough, metal = classify(k)
        lines = ['        # %s' % k, '        over "mat_%s"' % hx, '        {', '            over "Shader"', '            {']
        if f & (SURF_TRANS33 | SURF_TRANS66) and any(w in k.split('/')[-1] for w in GLASS_WORDS):
            Image.open(files[k]).convert('RGB').save(tmp)
            layers.dds(tmp, os.path.join(outdir, hx + '.t.dds'))
            lines += ['                uniform asset info:mdl:sourceAsset = @AperturePBR_Translucent.mdl@',
                      '                uniform token info:mdl:sourceAsset:subIdentifier = "AperturePBR_Translucent"',
                      '                uniform token info:implementationSource = "sourceAsset"',
                      '                float inputs:ior_constant = 1.5',
                      '                asset inputs:transmittance_texture = @./hd/pbr/%s.t.dds@ (' % hx,
                      '                    colorSpace = "auto"', '                )',
                      '                float inputs:transmittance_measurement_distance = 4',
                      '                bool inputs:thin_walled = 1']
            nglass += 1
        else:
            normal_map(files[k], maxside, strength).save(tmp)
            layers.dds(tmp, os.path.join(outdir, hx + '.n.dds'))
            lines += ['                asset inputs:normalmap_texture = @./hd/pbr/%s.n.dds@ (' % hx,
                      '                    colorSpace = "raw"', '                )',
                      '                float inputs:reflection_roughness_constant = %g' % rough,
                      '                float inputs:metallic_constant = %g' % metal]
        out += lines + ['            }', '        }', '']
        n += 1
        if n % 250 == 0:
            print(n, 'materials ...', flush=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    open(os.path.join(moddir, 'pbr.usda'), 'w').write('\n'.join(out + layers.footer()))
    print('%d materials (%d glass, %d from Jev classes), %d skipped (sky/liquid/not in pack) -> %s' % (n, nglass, njev, nskip,
          os.path.join(moddir, 'pbr.usda')))


if __name__ == '__main__':
    main()
