#!/usr/bin/env python3
"""Build Remix mod layers for Anachronox: HD skyboxes and liquid materials.

usage: make_layers.py MODDIR --sky-src DIR --sky-hd DIR --liq-src DIR --liq-hd DIR

  --sky-src  original sky faces (sky\\*.tga from GRAPHICS.dat), used for the texture hashes
  --sky-hd   upscaled faces (same base names, .png), e.g. from realesrgan-ncnn-vulkan -s 4
  --liq-src  original liquid textures, as <dir>/<name>.tga (from TEXTURES.dat)
  --liq-hd   upscaled liquids, as <dir>__<name>.png

Writes MODDIR/hd/{sky,liquids}/*.dds, MODDIR/hd_sky.usda and MODDIR/liquids.usda, and prints the sky
hashes (for rtx.skyBoxTextures) and the water hashes (for rtx.animatedWaterTextures).
Add the layers to mod.usda: subLayers = [@./hd_sky.usda@, @./liquids.usda@]
Material hashes are computed with remixhash.py (Remix = XXH3 of the BGRA mip 0 as QindieGL uploads it).
Game textures are copyrighted: keep the generated DDS files local, do not commit them.
"""
import argparse, glob, importlib.util, os
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('remixhash', os.path.join(here, 'remixhash.py'))
rh = importlib.util.module_from_spec(spec); spec.loader.exec_module(rh)

# liquid classes (by looking at the textures); anything else is left alone
# clear water: translucent with a tint from the texture's mean colour, a normal map from the texture (animated by
# Remix through rtx.animatedWaterTextures) and some emission, since the game draws warp surfaces fullbright.
# value: emissive intensity; SOFT_WATER use a nearly flat mask (the high-contrast pattern as emission looked
# like marble and hid the floor). Tuned against the original on sunstrip, starport, limbus, senderss, hovel.
WATER = {'limbus/water3b': 0.6, 'limbus/water3b1': 0.6, 'limbus/water3c': 0.6, 'senderloung/water1': 0.6,
         'tensil/h2002_sm': 0.15, 'tensil/poo': 0.15, 'bricks2/brownwater': 0.5}
SOFT_WATER = {'tensil/h2002_sm', 'tensil/poo'}
# murky water: fixed tint and short distance instead of the texture's mean colour
MURKY_WATER = {'bricks2/brownwater': (0.55, 0.42, 0.25)}
# translucent with the texture as transmittance (the glowing sewage keeps its look)
WATER_TEXTURED = {'baseanox/sewagesolid'}
# water the maps draw opaque (warp without SURF_TRANS33/66): as translucent water the deep greattree lake turned
# black; an opaque glossy surface looks like the original
WATER_OPAQUE = {'waukees/h2002'}
SLUDGE = {'ballotine/slime01a', 'bricks/shitplain2', 'bricks2/dpoo3', 'sexmachine/trash1',
          'warshipbay/plain3', 'krapton/p6'}
LAVA = {'levant/lava': 12.0, 'levant/levant3a': 6.0}
GLOW = {'detta/fluid': 3.0, 'krapton/purglow': 3.0, 'hive/cryspurp1': 2.0, 'hive/ycrystl': 2.0,
        'limbus/crysblu': 2.0, 'warshipbay/flshnlit': 3.0}


def dds(src_png, dst, alpha=False):
    """DXT1/DXT5 DDS with a full mip chain (Pillow writes one level; encode each level, then join)."""
    import io, struct
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.open(src_png).convert('RGBA')
    fmt = 'DXT5' if alpha else 'DXT1'
    w, h = im.size
    levels, lw, lh = [], w, h
    while True:
        buf = io.BytesIO()
        im.resize((lw, lh), Image.LANCZOS).save(buf, format='DDS', pixel_format=fmt)
        levels.append(buf.getvalue()[128:])            # strip the 128-byte DX9 header
        if lw == 1 and lh == 1:
            break
        lw, lh = max(1, lw // 2), max(1, lh // 2)
    hdr = bytearray(buf.getvalue()[:128]) if False else bytearray(128)
    first = io.BytesIO(); im.save(first, format='DDS', pixel_format=fmt); hdr[:] = first.getvalue()[:128]
    DDSD_MIPMAPCOUNT, DDSCAPS_COMPLEX, DDSCAPS_MIPMAP = 0x20000, 0x8, 0x400000
    flags = struct.unpack_from('<I', hdr, 8)[0] | DDSD_MIPMAPCOUNT
    struct.pack_into('<I', hdr, 8, flags)
    struct.pack_into('<I', hdr, 28, len(levels))           # dwMipMapCount
    caps = struct.unpack_from('<I', hdr, 108)[0] | DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    struct.pack_into('<I', hdr, 108, caps)
    with open(dst, 'wb') as f:
        f.write(bytes(hdr)); f.write(b''.join(levels))


def is_dark(path, limit=24):
    """star fields: upscalers wipe out the stars, keep the original there"""
    from PIL import ImageStat
    return sum(ImageStat.Stat(Image.open(path).convert('RGB')).mean) / 3 < limit


def water_body(moddir, tex, hd, key):
    """AperturePBR_Translucent shader inputs for WATER; writes the normal map (and soft emission mask) next to tex"""
    import numpy as np
    from PIL import ImageFilter
    spec = importlib.util.spec_from_file_location('pbr_layer', os.path.join(here, 'pbr_layer.py'))
    pl = importlib.util.module_from_spec(spec); spec.loader.exec_module(pl)
    im = Image.open(hd).convert('RGB')
    a = np.asarray(im, dtype=float) / 255
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).mean((0, 1))
    if key in MURKY_WATER:
        tint, dist = MURKY_WATER[key], 24
    else:   # pale version of the mean colour; the softly glowing water keeps less of it so the floor shows
        k = 0.4 if key in SOFT_WATER else 0.6
        tint, dist = 0.95 * (1 - k * (1 - lin / lin.max())), 256 if key in SOFT_WATER else 128
    base = os.path.join(moddir, tex[:-4])
    tmp = base + '.tmp.png'
    pl.normal_map(hd, 512, 2.0).save(tmp); dds(tmp, base + '.n.dds')
    mask = tex
    if key in SOFT_WATER:
        flat = 0.8 * np.asarray(im, dtype=float).mean((0, 1)) + 0.2 * np.asarray(im.filter(ImageFilter.GaussianBlur(im.width / 32)), dtype=float)
        Image.fromarray(np.clip(flat, 0, 255).astype(np.uint8)).save(tmp); dds(tmp, base + '.e.dds'); mask = tex[:-4] + '.e.dds'
    elif os.path.exists(os.path.join(moddir, 'hd/emissive', os.path.basename(tex))):
        mask = 'hd/emissive/' + os.path.basename(tex)   # same mask as emissive.usda
    os.remove(tmp)
    return ['                uniform asset info:mdl:sourceAsset = @AperturePBR_Translucent.mdl@',
            '                uniform token info:mdl:sourceAsset:subIdentifier = "AperturePBR_Translucent"',
            '                uniform token info:implementationSource = "sourceAsset"',
            '                float inputs:ior_constant = 1.33',
            '                color3f inputs:transmittance_color = (%.3f, %.3f, %.3f)' % tuple(tint),
            '                float inputs:transmittance_measurement_distance = %g' % dist,
            '                asset inputs:normalmap_texture = @./%s.n.dds@ (' % tex[:-4], '                    colorSpace = "raw"', '                )',
            '                bool inputs:thin_walled = 0',
            '                bool inputs:enable_emission = 1',
            '                asset inputs:emissive_mask_texture = @./%s@ (' % mask, '                    colorSpace = "auto"', '                )',
            '                float inputs:emissive_intensity = %g' % WATER[key]]


def header():
    return ['#usda 1.0', '(', '    upAxis = "Y"', ')', '', 'over "RootNode"', '{', '    over "Looks"', '    {']


def footer():
    return ['    }', '}', '']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('moddir')
    ap.add_argument('--sky-src', required=True); ap.add_argument('--sky-hd', required=True)
    ap.add_argument('--liq-src', required=True); ap.add_argument('--liq-hd', required=True)
    a = ap.parse_args()

    out = header(); sky_hashes = []
    for f in sorted(glob.glob(os.path.join(a.sky_src, '*.tga'))):
        name = os.path.splitext(os.path.basename(f))[0]
        hd = os.path.join(a.sky_hd, name + '.png')
        if not os.path.exists(hd) or ' ' in name or is_dark(f):
            continue
        h, _ = rh.remix_hash(f)
        if h in sky_hashes:
            continue  # identical image (e.g. all-black faces)
        sky_hashes.append(h)
        dds(hd, os.path.join(a.moddir, 'hd', 'sky', name + '.dds'))
        out += ['        over "mat_%016X"' % h, '        {', '            over "Shader"', '            {',
                '                asset inputs:diffuse_texture = @./hd/sky/%s.dds@ (' % name,
                '                    colorSpace = "auto"', '                )',
                '            }', '        }', '']
    open(os.path.join(a.moddir, 'hd_sky.usda'), 'w').write('\n'.join(out + footer()))

    out = header(); n = 0; seen = set(); water_hashes = []
    for f in sorted(glob.glob(os.path.join(a.liq_src, '*', '*.tga'))):
        d, base = f.split(os.sep)[-2:]
        key = '%s/%s' % (d.lower(), os.path.splitext(base)[0].lower())
        hd = os.path.join(a.liq_hd, '%s__%s.png' % (d, os.path.splitext(base)[0]))
        if not os.path.exists(hd):
            continue
        h, _ = rh.remix_hash(f)
        if h in seen:
            continue
        seen.add(h)
        tex = 'hd/liquids/%s__%s.dds' % (d.lower(), os.path.splitext(base)[0].lower())
        dds(hd, os.path.join(a.moddir, tex))
        body = []
        if key in WATER:
            body = water_body(a.moddir, tex, hd, key)
            water_hashes.append(h)
        elif key in WATER_TEXTURED:
            body = ['                uniform asset info:mdl:sourceAsset = @AperturePBR_Translucent.mdl@',
                    '                uniform token info:mdl:sourceAsset:subIdentifier = "AperturePBR_Translucent"',
                    '                uniform token info:implementationSource = "sourceAsset"',
                    '                float inputs:ior_constant = 1.33',
                    '                asset inputs:transmittance_texture = @./%s@ (' % tex,
                    '                    colorSpace = "auto"', '                )',
                    '                float inputs:transmittance_measurement_distance = 64',
                    '                bool inputs:thin_walled = 0']
        elif key in SLUDGE or key in WATER_OPAQUE:
            body = ['                asset inputs:diffuse_texture = @./%s@ (' % tex, '                    colorSpace = "auto"',
                    '                )', '                float inputs:reflection_roughness_constant = %g' % (0.1 if key in WATER_OPAQUE else 0.15),
                    '                float inputs:metallic_constant = 0']
        elif key in LAVA or key in GLOW:
            inten = LAVA.get(key, GLOW.get(key))
            body = ['                asset inputs:diffuse_texture = @./%s@ (' % tex, '                    colorSpace = "auto"',
                    '                )', '                bool inputs:enable_emission = 1',
                    '                asset inputs:emissive_mask_texture = @./%s@ (' % tex, '                    colorSpace = "auto"',
                    '                )', '                float inputs:emissive_intensity = %g' % inten,
                    '                float inputs:reflection_roughness_constant = 0.6']
        if not body:
            continue
        out += ['        # %s' % key, '        over "mat_%016X"' % h, '        {', '            over "Shader"', '            {']
        out += body + ['            }', '        }', '']
        n += 1
    open(os.path.join(a.moddir, 'liquids.usda'), 'w').write('\n'.join(out + footer()))
    print('sky faces: %d, liquid materials: %d' % (len(sky_hashes), n))
    print('SKYHASHES ' + ', '.join('0x%016X' % h for h in sky_hashes))
    print('WATERHASHES ' + ', '.join('0x%016X' % h for h in water_hashes))


if __name__ == '__main__':
    main()
