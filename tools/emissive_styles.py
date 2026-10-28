#!/usr/bin/env python3
"""Light-emitting surfaces that follow the game's light styles (dynamic emission, QindieGL `styledemission`).

usage: emissive_styles.py MODDIR GAMEDIR OUTDIR MAP.bsp... [--dry-run]

A SURF_LIGHT face whose lightmap has a light style other than 0 (dface_t styles[]: a styled or switchable light
reaches it, e.g. fortress1's pulsing lamps, style 11) should dim with that style; under Remix its emission is a
constant material. QindieGL recognises such a face per draw (texture hash + polygon centre) and draws it with a
variant of its texture whose mip 0 differs in one byte, so Remix sees another hash: level 0, 1, 2 for style
factor 0, 1/3, 2/3 (level 3 = the normal texture). The variant of level L has byte 0 of mip 0 (B of texel 0,
D3D BGRA) XORed with L + 1.

Faces that use an emissive texture without being lights in the map (no SURF_LIGHT or light value 0: a texture is
emissive in Remix if any face of any map is a light, e.g. bricks/empty is a light on 16 faces and a wall on 21692) are
listed with style 0 and always drawn with the level 0 variant (emission off), as the original only lights them
through the lightmap.

Writes
  OUTDIR/<map>.estyles      "0xHASH x y z style" per face (HASH: the texture's hash in MODDIR's emissive.usda,
                            i.e. what Remix sees, centre = average of the face's vertices), for QindieGL;
  MODDIR/emissive_styles.usda  for every texture and level it needs (level 0 only for textures without styled faces), a copy of the texture's material blocks from MODDIR's
                            layers (mod.usda subLayers) under the variant hash, emission scaled by L / 3 (off at 0).
Add @./emissive_styles.usda@ to mod.usda's subLayers. The texture image that gives the variant hash is the one
whose Remix hash matches emissive.usda: GAMEDIR/anoxdata/textures (texture pack) or TEXTURES.dat. Textures
without a match are skipped with a warning. Faces with several styles use the first.
"""
import glob, importlib.util, io, os, re, struct, sys

here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
fv, rh, adat, layers = _load('find_views'), _load('remixhash'), _load('adat'), _load('make_layers')

SURF_LIGHT, SURF_SKY, SURF_WARP, SURF_NODRAW = 0x1, 0x4, 0x8, 0x80
LEVELS = 3


def styled_faces(path, emissive=()):
    """[(texture, centre, style)] of SURF_LIGHT faces with a non-zero lightmap style, and (style 0) of the other
    drawn faces whose texture is in emissive"""
    d = open(path, 'rb').read(); L = fv.lumps(d)
    voff = L[2][0]; eoff = L[11][0]; seoff = L[12][0]; toff, tn = L[5][0], L[5][1] // 76; foff, fn = L[6][0], L[6][1] // 20
    tex = []
    for i in range(tn):
        flags, value = struct.unpack_from('<ii', d, toff + i * 76 + 32)
        tex.append((flags, value, d[toff + i * 76 + 40:toff + i * 76 + 72].split(b'\0', 1)[0].decode('latin-1')
                    .replace('\\', '/').lower()))
    out = []
    for i in range(fn):
        _, _, first, num, ti = struct.unpack_from('<HHiHH', d, foff + i * 20)
        flags, value, name = tex[ti]
        styles = [s for s in d[foff + i * 20 + 12:foff + i * 20 + 16] if s not in (0, 255)]
        if flags & (SURF_SKY | SURF_WARP | SURF_NODRAW):
            continue
        if flags & SURF_LIGHT and value > 0:
            if not styles:
                continue
        elif name in emissive:
            styles = [0]
        else:
            continue
        pts = []
        for k in range(num):
            se = struct.unpack_from('<i', d, seoff + (first + k) * 4)[0]
            v0, v1 = struct.unpack_from('<HH', d, eoff + abs(se) * 4)
            pts.append(struct.unpack_from('<fff', d, voff + (v0 if se >= 0 else v1) * 12))
        out.append((name, [sum(p[j] for p in pts) / len(pts) for j in range(3)], styles[0]))
    return out


def blocks(text):
    """{hash: [block text]} of the top-level 'over "mat_HASH"' blocks inside Looks"""
    out = {}
    for m in re.finditer(r'^( *)over "mat_([0-9A-Fa-f]{16})"\s*\n\1\{', text, re.M):
        i, depth = m.end(), 1
        while depth:
            c = text[i]; depth += (c == '{') - (c == '}'); i += 1
        out.setdefault(m.group(2).upper(), []).append(text[m.start():i])
    return out


def shader_attrs(block):
    """[(name, statement)] of the attributes in a block's 'over "Shader"' (statements may span lines: asset (...))"""
    i = block.index('over "Shader"'); i = block.index('{', i) + 1
    depth, j = 1, i
    while depth:
        depth += (block[j] == '{') - (block[j] == '}'); j += 1
    out, cur, paren = [], [], 0
    for line in block[i:j - 1].split('\n'):
        t = line.strip()
        if not t:
            continue
        cur.append(t); paren += t.count('(') - t.count(')')
        if paren == 0:
            stmt = '\n'.join(cur); cur = []
            out.append((stmt.split('=')[0].split()[-1], stmt))
    return out


def bgra(img):
    from PIL import Image
    im = Image.open(img)
    has_alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
    im = im.convert('RGBA')
    if not has_alpha:
        im.putalpha(255)
    r, g, b, a = im.split()
    return bytearray(Image.merge('RGBA', (b, g, r, a)).tobytes())


def main():
    argv = sys.argv[1:]
    dry = '--dry-run' in argv
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 4:
        print(__doc__); sys.exit(1)
    moddir, gamedir, outdir, maps = args[0], args[1], args[2], args[3:]
    import xxhash

    # texture name -> hash as installed (the "# name (light ...)" comment above each emissive block)
    em = open(os.path.join(moddir, 'emissive.usda')).read()
    installed = {m.group(1).lower(): m.group(2).upper()
                 for m in re.finditer(r'# (\S+) \(light[^\n]*\n\s*over "mat_([0-9A-Fa-f]{16})"', em)}
    # the other layers, strongest first: mod.usda's subLayers, or the installer's order before mod.usda exists
    modfile = os.path.join(moddir, 'mod.usda')
    sub = re.search(r'subLayers = \[([^\]]*)\]', open(modfile).read()) if os.path.exists(modfile) else None
    order = re.findall(r'@\./([^@]+)@', sub.group(1)) if sub else \
        [l + '.usda' for l in ('hd_sky', 'liquids', 'emissive', 'emissive_jev', 'models_hd', 'pbr', 'proctex')]
    mats = {}
    for lay in order:
        if lay != 'emissive_styles.usda' and os.path.exists(os.path.join(moddir, lay)):
            for h, bl in blocks(open(os.path.join(moddir, lay)).read()).items():
                mats.setdefault(h, []).extend(bl)

    sources = {}
    root = os.path.join(gamedir, 'anoxdata', 'textures')
    for p in glob.glob(os.path.join(root, '**', '*.*'), recursive=True):
        sources.setdefault(os.path.splitext(os.path.relpath(p, root).replace('\\', '/').lower())[0], []).append(p)
    dat = os.path.join(gamedir, 'anoxdata', 'TEXTURES.dat')
    dat = dat if os.path.exists(dat) else dat + '.orig'
    dentries = {os.path.splitext(n.replace('\\', '/').lower())[0]: (o, n2, c) for n, o, n2, c in adat.entries(dat)}

    variants = {}     # texture -> (base hash, [variant hashes])
    need = {}         # texture -> levels that get a material (0 only when all its faces are style 0)
    os.makedirs(outdir, exist_ok=True)
    for mp in maps:
        name = os.path.splitext(os.path.basename(mp))[0].lower()
        rows = []
        for tex, c, style in styled_faces(mp, installed):
            if tex not in variants:
                base = installed.get(tex)
                found = None
                cands = list(sources.get(tex, []))
                if tex in dentries:
                    with open(dat, 'rb') as f:
                        cands.append(io.BytesIO(adat.read(f, *dentries[tex])))
                for img in cands:
                    try:
                        px = bgra(img)
                    except Exception:
                        continue
                    if base and '%016X' % xxhash.xxh3_64_intdigest(bytes(px)) == base:
                        found = px; break
                if not found:
                    print('%s: %s not in emissive.usda or no image with its hash, skipped' % (name, tex))
                    variants[tex] = None; continue
                vh = []
                for lv in range(LEVELS):
                    v = bytearray(found); v[0] ^= lv + 1
                    vh.append('%016X' % xxhash.xxh3_64_intdigest(bytes(v)))
                variants[tex] = (base, vh)
            if variants[tex]:
                need.setdefault(tex, {0}).update(range(LEVELS) if style else ())
                rows.append('0x%s %.1f %.1f %.1f %d' % (variants[tex][0], c[0], c[1], c[2], style))
        out = os.path.join(outdir, name + '.estyles')
        if rows:
            st = sum(1 for r in rows if not r.endswith(' 0'))
            print('%s: %d styled light faces, %d non-light faces with an emissive texture' % (name, st, len(rows) - st))
            if not dry:
                open(out, 'w').write('# %s: generated by tools/emissive_styles.py\n# hash x y z style\n' % name +
                                     '\n'.join(rows) + '\n')
        elif os.path.exists(out) and not dry:
            os.remove(out)

    lay = layers.header()
    for tex, v in sorted((t, v) for t, v in variants.items() if v):
        base, vh = v
        attrs = {}    # attribute name -> statement; the first (strongest) layer wins
        for b in mats.get(base, []):
            for name, stmt in shader_attrs(b):
                attrs.setdefault(name, stmt)
        for lv, h in enumerate(vh):
            if lv not in need.get(tex, ()):
                continue
            body = []
            for name, stmt in attrs.items():
                if name == 'inputs:enable_emission' and lv == 0:
                    stmt = stmt.replace('= 1', '= 0')
                if name == 'inputs:emissive_intensity':
                    stmt = re.sub(r'= *([0-9.eE+-]+)', lambda m: '= %g' % (float(m.group(1)) * lv / LEVELS), stmt)
                body += ['                ' + l for l in stmt.split('\n')]
            lay += ['        # %s level %d/%d' % (tex, lv, LEVELS), '        over "mat_%s"' % h, '        {',
                    '            over "Shader"', '            {'] + body + ['            }', '        }', '']
    lay += layers.footer()
    print('%d textures with variants' % sum(1 for v in variants.values() if v))
    if not dry:
        open(os.path.join(moddir, 'emissive_styles.usda'), 'w').write('\n'.join(lay))


if __name__ == '__main__':
    main()
