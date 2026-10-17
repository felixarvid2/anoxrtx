#!/usr/bin/env python3
"""Build a Remix texture replacement layer from upscaled images named by their Remix texture hash.

usage: hd_layer.py MODDIR NAME HD_DIR [ALPHA_DIR] [--max 2048]

  HD_DIR     upscaled RGB images named <HASH>.png (16 hex digits, the Remix hash of the ORIGINAL texture,
             e.g. from remixhash.py), for example the output of realesrgan-ncnn-vulkan
  ALPHA_DIR  optional original alpha channels named <HASH>.png (grayscale); they are resized (Lanczos) to
             the HD size and merged, and those textures are written as DXT5 instead of DXT1
Writes MODDIR/hd/NAME/<HASH>.dds (with mipmaps, longest side capped at --max) and MODDIR/NAME.usda with one
material override per hash (inputs:diffuse_texture). Add @./NAME.usda@ to mod.usda's subLayers.
"""
import glob, importlib.util, os, sys
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('make_layers', os.path.join(here, 'make_layers.py'))
layers = importlib.util.module_from_spec(spec); spec.loader.exec_module(layers)


def main():
    args = [a for a in sys.argv[1:]]
    maxside = 2048
    if '--max' in args:
        i = args.index('--max'); maxside = int(args[i + 1]); del args[i:i + 2]
    if len(args) < 3:
        print(__doc__); sys.exit(1)
    moddir, name, hd_dir = args[:3]
    alpha_dir = args[3] if len(args) > 3 else None
    outdir = os.path.join(moddir, 'hd', name); os.makedirs(outdir, exist_ok=True)
    out = layers.header(); n = na = 0
    for f in sorted(glob.glob(os.path.join(hd_dir, '*.png'))):
        h = os.path.splitext(os.path.basename(f))[0].upper().replace('0X', '')
        if len(h) != 16:
            continue
        im = Image.open(f).convert('RGB')
        if max(im.size) > maxside:
            s = maxside / max(im.size)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        alpha = None
        if alpha_dir and os.path.exists(os.path.join(alpha_dir, os.path.basename(f))):
            alpha = Image.open(os.path.join(alpha_dir, os.path.basename(f))).convert('L').resize(im.size, Image.LANCZOS)
        rgba = im.convert('RGBA')
        if alpha is not None:
            rgba.putalpha(alpha); na += 1
        tmp = os.path.join(outdir, h + '.png'); rgba.save(tmp)
        layers.dds(tmp, os.path.join(outdir, h + '.dds'), alpha=alpha is not None); os.remove(tmp)
        out += ['        over "mat_%s"' % h, '        {', '            over "Shader"', '            {',
                '                asset inputs:diffuse_texture = @./hd/%s/%s.dds@ (' % (name, h),
                '                    colorSpace = "auto"', '                )', '            }', '        }', '']
        n += 1
    open(os.path.join(moddir, name + '.usda'), 'w').write('\n'.join(out + layers.footer()))
    print('%s: %d textures (%d with alpha) -> %s' % (name, n, na, os.path.join(moddir, name + '.usda')))


if __name__ == '__main__':
    main()
