#!/usr/bin/env python3
"""Approximate PBR materials for the level textures: normal maps, roughness/metallic, glass.

usage: pbr_layer.py MODDIR GAMEDIR MAP.bsp... [--max 512] [--strength 2.0] [--only NAME,NAME] [--classes JEV.json]
                    [--rules RULES.json] [--ai CACHE.json] [--vision CACHE.json] [--report DIR]

For every texture the maps use (BSP texinfo) that exists in the loose texture pack in GAMEDIR/anoxdata/textures
(e.g. Chuncki's 4x pack; hashes via remixhash.py, so the pack must be what the game loads):
- normal map: the texture's luminance as a height field (blurred, Sobel, wraps around since textures tile),
  encoded the way Remix reads `normalmap_texture` (unorm hemi-octahedral in R/G: t = n.xy / (|x|+|y|+|z|),
  p = (t.x + t.y, t.x - t.y)), DirectX tangent space, written as DXT1 with mips, longest side <= --max;
- reflection_roughness_constant / metallic_constant per material class (tools/pbr_classify.py with the reviewable
  rules in tools/pbr_rules.json: exceptions, BSP flags, name keywords); with --classes CLASSES.json from
  tools/jev_classify.py (Gemini looks, Jev decides): roughness = Jev's score (clamped 0.05..1), metallic = Jev's metal
  probability when it is at least 0.5, otherwise 0, unless an exception says otherwise; --ai CACHE.json adds the
  DeepSeek suggestions cached by pbr_classify.py --deepseek, --vision CACHE.json what DeepSeek saw in the thumbnails
  (pbr_classify.py --deepseek-vision: settles rule-vs-Jev conflicts, see there); --report DIR writes the uncertainty report;
- glass: SURF_TRANS33/66 textures named glass/win/clear (glass_words) become thin-walled AperturePBR_Translucent with
  the texture as transmittance (not haze_glass: haze sheets keep Remix' blended look).
Sky (SURF_SKY) and liquid (SURF_WARP) surfaces are skipped (liquids.usda handles those), and so is haze_glass.
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
rh, layers, pc = _load('remixhash'), _load('make_layers'), _load('pbr_classify')


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
    classes_file = opt('--classes', ''); ai_file = opt('--ai', ''); report_dir = opt('--report', '')
    vision_file = opt('--vision', '')
    rules = pc.load_rules(opt('--rules', pc.RULES))
    jev = {}
    if classes_file:
        import json
        jev = {k: v for k, v in json.load(open(classes_file)).items() if not k.startswith('_')}
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    moddir, gamedir, maps = args[0], args[1], args[2:]

    results, _ = pc.classify_all(maps, rules, jev, pc.load_ai(ai_file), pc.load_ai(vision_file))
    if report_dir:
        import json
        os.makedirs(report_dir, exist_ok=True)
        json.dump(results, open(os.path.join(report_dir, 'pbr_classes.json'), 'w'), indent=1, sort_keys=True)
        open(os.path.join(report_dir, 'pbr_report.md'), 'w').write(pc.report(results))
    root = os.path.join(gamedir, 'anoxdata', 'textures')
    files = {}
    for p in glob.glob(os.path.join(root, '**', '*.*'), recursive=True):
        files.setdefault(os.path.splitext(os.path.relpath(p, root).replace('\\', '/').lower())[0], p)

    outdir = os.path.join(moddir, 'hd', 'pbr'); os.makedirs(outdir, exist_ok=True)
    tmp = os.path.join(outdir, '_tmp.png')
    out = layers.header(); done = set(); n = nglass = nskip = njev = 0
    for k in sorted(results):
        r = results[k]
        if (only and k not in only) or r['class'] == 'skip' or k not in files:
            nskip += 1; continue
        try:
            h, _ = rh.remix_hash(files[k])
        except Exception:
            nskip += 1; continue
        if h in done:
            continue
        done.add(h)
        hx = '%016X' % h
        rough, metal = r['roughness'], r['metallic']
        njev += r['source'] == 'jev'
        lines = ['        # %s' % k, '        over "mat_%s"' % hx, '        {', '            over "Shader"', '            {']
        if r['translucent']:
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
    print('%d materials (%d glass, %d from Jev classes), %d skipped (sky/liquid/haze/not in pack) -> %s' % (n, nglass, njev, nskip,
          os.path.join(moddir, 'pbr.usda')))


if __name__ == '__main__':
    main()
