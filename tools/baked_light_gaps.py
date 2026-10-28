#!/usr/bin/env python3
"""Find surfaces the original's baked lighting makes clearly brighter than RTX Remix can, from a map's BSP.

usage: baked_light_gaps.py MAP.bsp... [--lights FILE | --lights-dir DIR] [--ini anox_customise.ini]
                           [--ratio 4] [--top 8] [--overrides OUTDIR] [--json FILE] [--styled]

Baked: the BSP lightmaps (Quake 2 lighting lump; per face `lightofs`, one w*h RGB block per style in
dface_t.styles, w/h = luxel extents of the texinfo s/t vectors on a 16-unit grid). Anachronox faces usually carry
two style-0 blocks; the renderer adds all of a face's blocks, so style-0 blocks are summed. Styled blocks (switched
or animated lights) are left out, unless --styled.
Remix estimate (direct light only, irradiance at the luxel, traced through the BSP for visibility):
  .lights point/spot lights: sphere radiance = scale * ref * (light / ref) ^ exponent * colour (QindieGL
    rmx_maplights.cpp, `format raw`; [maplights.global] / [maplights.<map>] of --ini, default 1, 2, 300, radius 4),
    E = radiance * pi * r^2 * cos / d^2; the <map>.override next to the .lights file is applied (off, scale, color,
    move, radius, add); startoff rows are off; styled rows only with --styled;
  sun line: radiance * sun_scale * disc solid angle * cos, where the luxel sees a SURF_SKY face along it;
  SURF_LIGHT faces with value > 0 (the only faces that emit since the static-off emissive styles): emissive
    intensity clamp(highest value of the texture over the maps in the BSP's directory / 100, 1, 15) or
    maps/emissive_intensity.tsv, times EMIT_ALBEDO for the unknown texture colour, as area lights
    E = Le * A * cos_e * cos / d^2 per <= 64-unit patch.
Remix also adds bounce light, which this leaves out; the map's calibration K (weighted median of baked / E over
bright luxels that get direct light) absorbs a uniform share of it and the map's exposure bias.
A luxel is a gap when baked >= the map's bright level and baked > --ratio * K * E. Gap luxels are clustered (64-unit
cells, touching cells joined) and ranked by excess = sum(area * (baked - K * E)) / 255 (the original's light in
luxel units * area that the estimate does not explain).
Per cluster: centre, size, normal, colour, nearby .lights rows, the likely source (point lights with Quake linear
falloff (light - d) * cos -> "falloff" when they explain the baked level, SURF_LIGHT faces -> "surface light",
sky in view and worldspawn _sun_ambient/_ambient/_minlight -> "ambient", else "bounce"), a camera view
(MAP NAME X Y Z PITCH YAW) and a suggested override line: add X Y Z R G B LIGHT 0 at the surface source or off
the bright surface, LIGHT from the missing irradiance. These are candidates to test in game, not fixes.
"""
import argparse, json, math, os, re, struct, sys
from collections import defaultdict

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import find_views as fv  # noqa: E402

SURF_LIGHT, SURF_SKY, SURF_WARP, SURF_TRANS33, SURF_TRANS66, SURF_NODRAW = 0x1, 0x4, 0x8, 0x10, 0x20, 0x80
CONTENTS_SOLID = 1
EMIT_ALBEDO = 0.5
CELL = 64.0
PATCH = 64.0


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


class Bsp:
    """Quake 2 IBSP v38: faces with their lightmaps"""
    def __init__(self, path=None, data=None):
        d = data if data is not None else open(path, 'rb').read()
        self.d = d
        self.L = L = [struct.unpack_from('<ii', d, 8 + 8 * i) for i in range(19)]
        def arr(i, fmt):
            sz = struct.calcsize(fmt); o, n = L[i]
            return [struct.unpack_from(fmt, d, o + k * sz) for k in range(n // sz)]
        self.planes = arr(1, '<4fi')
        self.verts = arr(2, '<3f')
        self.nodes = arr(4, '<3i6h2H')
        self.texinfo = [(t[0:4], t[4:8], t[8], t[9], t[10].split(b'\0', 1)[0].decode('latin-1').replace('\\', '/').lower())
                        for t in arr(5, '<8f2i32si')]
        self.raw_faces = arr(6, '<HHiHH4Bi')
        self.leaves = arr(8, '<i2h6h4H')
        self.edges = arr(11, '<2H')
        self.surfedges = [x[0] for x in arr(12, '<i')]
        o, n = L[7]
        self.lighting = d[o:o + n]
        o, n = L[0]
        self.entities = [dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', b))
                         for b in re.findall(r'\{([^{}]*)\}', d[o:o + n].split(b'\0', 1)[0].decode('latin-1'))]
        self.faces = [self.face(i) for i in range(len(self.raw_faces))]

    def face(self, i):
        pn, side, fe, ne, ti, s0, s1, s2, s3, lofs = self.raw_faces[i]
        S, T, flags, value, name = self.texinfo[ti]
        p = self.planes[pn]
        n, dist = (p[0], p[1], p[2]), p[3]
        if side:
            n, dist = (-n[0], -n[1], -n[2]), -dist
        pts = []
        for k in range(ne):
            se = self.surfedges[fe + k]
            pts.append(self.verts[self.edges[se][0]] if se >= 0 else self.verts[self.edges[-se][1]])
        ss = [dot(v, S) + S[3] for v in pts]; tt = [dot(v, T) + T[3] for v in pts]
        ms, mt = math.floor(min(ss) / 16), math.floor(min(tt) / 16)
        w, h = math.ceil(max(ss) / 16) - ms + 1, math.ceil(max(tt) / 16) - mt + 1
        area = 0.0
        for k in range(1, len(pts) - 1):
            area += 0.5 * math.sqrt(sum(c * c for c in cross([pts[k][j] - pts[0][j] for j in range(3)],
                                                            [pts[k + 1][j] - pts[0][j] for j in range(3)])))
        c = tuple(sum(v[j] for v in pts) / len(pts) for j in range(3))
        styles = [s for s in (s0, s1, s2, s3) if s != 255]
        return dict(index=i, normal=n, dist=dist, pts=pts, centre=c, area=area, S=S, T=T, flags=flags, value=value,
                    tex=name, styles=styles, lofs=lofs, mins=(ms, mt), size=(w, h))

    def lightmaps(self, f):
        """[(style, [(r, g, b)] * w*h)] of face f, [] without a lightmap"""
        w, h = f['size']; n = w * h * 3
        if f['lofs'] < 0 or not f['styles']:
            return []
        out = []
        for k, st in enumerate(f['styles']):
            o = f['lofs'] + k * n
            if o + n > len(self.lighting):
                break
            b = self.lighting[o:o + n]
            out.append((st, [(b[i], b[i + 1], b[i + 2]) for i in range(0, n, 3)]))
        return out

    def luxel_pos(self, f, i, j):
        """world position of luxel (i, j): s = (mins_s + i) * 16, t = (mins_t + j) * 16 on the face plane"""
        S, T, n = f['S'], f['T'], f['normal']
        s = (f['mins'][0] + i) * 16 - S[3]; t = (f['mins'][1] + j) * 16 - T[3]
        a, b, c = S[:3], T[:3], n
        det = dot(a, cross(b, c))
        if abs(det) < 1e-9:
            return None
        cbc, cca, cab = cross(b, c), cross(c, a), cross(a, b)
        return tuple((s * cbc[k] + t * cca[k] + f['dist'] * cab[k]) / det for k in range(3))

    def baked(self, f, styled=False):
        """[(pos, rgb)] per luxel: the sum of the face's style-0 blocks (all blocks with styled)"""
        maps = [m for st, m in self.lightmaps(f) if styled or st == 0]
        if not maps:
            return []
        w, h = f['size']; out = []
        for j in range(h):
            for i in range(w):
                k = j * w + i
                p = self.luxel_pos(f, i, j)
                if p is None:
                    return []
                out.append((p, tuple(sum(m[k][c] for m in maps) for c in range(3))))
        return out

    def solid(self, p):
        n = 0
        while n >= 0:
            nd = self.nodes[n]; pl = self.planes[nd[0]]
            n = nd[1] if pl[0] * p[0] + pl[1] * p[1] + pl[2] * p[2] - pl[3] >= 0 else nd[2]
        return self.leaves[-1 - n][0] & CONTENTS_SOLID

    def clear(self, a, b):
        """no CONTENTS_SOLID leaf between a and b"""
        stack = [(0, a, b)]
        planes, nodes, leaves = self.planes, self.nodes, self.leaves
        while stack:
            n, p1, p2 = stack.pop()
            if n < 0:
                if leaves[-1 - n][0] & CONTENTS_SOLID:
                    return False
                continue
            nd = nodes[n]; pl = planes[nd[0]]
            d1 = pl[0] * p1[0] + pl[1] * p1[1] + pl[2] * p1[2] - pl[3]
            d2 = pl[0] * p2[0] + pl[1] * p2[1] + pl[2] * p2[2] - pl[3]
            if d1 >= 0 and d2 >= 0:
                stack.append((nd[1], p1, p2))
            elif d1 < 0 and d2 < 0:
                stack.append((nd[2], p1, p2))
            else:
                t = d1 / (d1 - d2)
                m = (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t, p1[2] + (p2[2] - p1[2]) * t)
                near, far = (nd[1], nd[2]) if d1 >= 0 else (nd[2], nd[1])
                stack.append((far, m, p2)); stack.append((near, p1, m))
        return True

    def first_hit(self, a, b):
        """first point on a..b inside a solid leaf, or None"""
        stack = [(0, a, b)]
        planes, nodes, leaves = self.planes, self.nodes, self.leaves
        while stack:
            n, p1, p2 = stack.pop()
            if n < 0:
                if leaves[-1 - n][0] & CONTENTS_SOLID:
                    return p1
                continue
            nd = nodes[n]; pl = planes[nd[0]]
            d1 = dot(pl, p1) - pl[3]; d2 = dot(pl, p2) - pl[3]
            if d1 >= 0 and d2 >= 0:
                stack.append((nd[1], p1, p2))
            elif d1 < 0 and d2 < 0:
                stack.append((nd[2], p1, p2))
            else:
                t = d1 / (d1 - d2)
                m = tuple(p1[k] + (p2[k] - p1[k]) * t for k in range(3))
                near, far = (nd[1], nd[2]) if d1 >= 0 else (nd[2], nd[1])
                stack.append((far, m, p2)); stack.append((near, p1, m))
        return None


def read_ini(path, mapname):
    """[maplights.global] then [maplights.<map>] keys of anox_customise.ini"""
    prm = dict(scale=1.0, exponent=2.0, ref=300.0, radius=4.0, sun_scale=12.0)
    if not path or not os.path.exists(path):
        return prm
    sec = None; got = {}
    for line in open(path, encoding='latin-1'):
        line = line.split(';', 1)[0].strip()
        m = re.match(r'\[(.+)\]$', line)
        if m:
            sec = m.group(1).lower(); continue
        if '=' in line and sec in ('maplights.global', 'maplights.' + mapname):
            k, v = [x.strip() for x in line.split('=', 1)]
            try:
                got.setdefault(sec, {})[k.lower()] = float(v)
            except ValueError:
                pass
    for sec in ('maplights.global', 'maplights.' + mapname):
        for k in prm:
            if k in got.get(sec, {}):
                prm[k] = got[sec][k]
    return prm


def parse_row(t):
    """a .lights / override `add` row -> dict, or None"""
    try:
        v = [float(x) for x in t[:8]]
    except ValueError:
        return None
    if len(v) < 8:
        return None
    row = dict(pos=v[:3], color=v[3:6], light=v[6], radius=v[7], dir=None, cone=0.0, style=0, startoff=False)
    rest = t[8:]
    if len(rest) >= 4:
        try:
            row['dir'] = [float(x) for x in rest[:3]]; row['cone'] = float(rest[3]); rest = rest[4:]
        except ValueError:
            pass
    if 'style' in rest:
        try:
            row['style'] = int(rest[rest.index('style') + 1])
        except (ValueError, IndexError):
            pass
    row['startoff'] = 'startoff' in rest
    return row


def read_lights(path):
    """(rows, sun, raw) of a .lights file with its .override applied; rows keep their file index"""
    rows, sun, raw = [], None, False
    if not path or not os.path.exists(path):
        return rows, sun, raw
    with open(path) as fh:
        lines = fh.read().splitlines()
    for line in lines:
        t = line.split()
        if not t or t[0].startswith('#'):
            continue
        if t[0] == 'format':
            raw = len(t) > 1 and t[1] == 'raw'; continue
        if t[0] == 'sun':
            try:
                v = [float(x) for x in t[1:9]]
                sun = dict(dir=v[0:3], color=v[3:6], light=v[6], angle=v[7], scale=1.0)
            except (ValueError, IndexError):
                pass
            continue
        r = parse_row(t)
        if r:
            r['index'] = len(rows); r['scale'] = 1.0
            rows.append(r)
    ovr = os.path.splitext(path)[0] + '.override'
    if os.path.exists(ovr):
        with open(ovr) as fh:
            lines = fh.read().splitlines()
        for line in lines:
            t = line.split()
            if not t or t[0].startswith('#'):
                continue
            if t[0] == 'add':
                r = parse_row(t[1:])
                if r:
                    r['index'] = 'add'; r['scale'] = 1.0; rows.append(r)
                continue
            if t[0] == 'sun' and sun and len(t) >= 2:
                if t[1] == 'off':
                    sun['scale'] = 0.0
                elif t[1] == 'scale' and len(t) == 3:
                    sun['scale'] *= float(t[2])
                continue
            try:
                i = int(t[0]); r = rows[i]
            except (ValueError, IndexError):
                continue
            if r['index'] != i or len(t) < 2:
                continue
            a = [float(x) for x in t[2:5] if re.match(r'^-?[\d.]+$', x)]
            if t[1] == 'off':
                r['scale'] = 0.0
            elif t[1] == 'scale' and a:
                r['scale'] *= a[0]
            elif t[1] == 'color' and len(a) == 3:
                r['color'] = a
            elif t[1] == 'move' and len(a) == 3:
                r['pos'] = [r['pos'][k] + a[k] for k in range(3)]
            elif t[1] == 'radius' and a:
                r['radius'] = a[0]
    return rows, sun, raw


def remix_intensity(light, prm, raw=True):
    if not raw:
        return light * prm['scale']
    return prm['scale'] * prm['ref'] * (max(light, 0.0) / prm['ref']) ** prm['exponent']


def raw_light(intensity, prm):
    """inverse of remix_intensity for a raw `add` row"""
    return prm['ref'] * (max(intensity, 0.0) / (prm['scale'] * prm['ref'])) ** (1.0 / prm['exponent'])


def emissive_table(bsp_dir, tsv):
    """texture -> Remix emissive intensity as tools/emissive_layer.py writes it"""
    best = {}
    for fn in sorted(os.listdir(bsp_dir)) if bsp_dir and os.path.isdir(bsp_dir) else []:
        if not fn.lower().endswith('.bsp'):
            continue
        d = open(os.path.join(bsp_dir, fn), 'rb').read()
        o, n = struct.unpack_from('<ii', d, 8 + 8 * 5)
        for i in range(o, o + n - 75, 76):
            flags, value = struct.unpack_from('<ii', d, i + 32)
            if flags & SURF_LIGHT and not flags & (SURF_SKY | SURF_WARP) and value > 0:
                k = d[i + 40:i + 72].split(b'\0', 1)[0].decode('latin-1').replace('\\', '/').lower()
                best[k] = max(best.get(k, 0), value)
    out = {k: min(max(v / 100.0, 1.0), 15.0) for k, v in best.items()}
    if tsv and os.path.exists(tsv):
        for line in open(tsv):
            t = line.rstrip('\n').split('\t')
            if t[0] and not t[0].startswith('#') and len(t) >= 2:
                out[t[0].lower()] = float(t[1])
    return out


def texture_colors(texdir, names):
    """texture -> mean linear luminance of TEXDIR/<name>.png (the emissive mask), needs PIL"""
    try:
        from PIL import Image
    except ImportError:
        return {}
    lin = [(c / 255.0) / 12.92 if c <= 10 else ((c / 255.0 + 0.055) / 1.055) ** 2.4 for c in range(256)]
    out = {}
    for n in names:
        p = os.path.join(texdir, n + '.png')
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGB'); im.thumbnail((64, 64))
        h = im.histogram()
        cs = [sum(lin[v] * h[k * 256 + v] for v in range(256)) / max(sum(h[k * 256:(k + 1) * 256]), 1) for k in range(3)]
        out[n] = lum(cs)
    return out


def masked_emitters(bsp, emissive, tol=2.05):
    """indices of unstyled light faces that QindieGL's styledemission draws with emission off: a plain face with the
    same texture is listed in <map>.estyles with style 0 (tools/emissive_styles.py) and its centre is within 2 units
    per axis of the light face's (qdx_estyles_match, ESTYLES_TOL)"""
    plain = defaultdict(list)
    for f in bsp.faces:
        if f['tex'] in emissive and not (f['flags'] & SURF_LIGHT and f['value'] > 0) and \
                not f['flags'] & (SURF_SKY | SURF_WARP | SURF_NODRAW):
            plain[f['tex']].append(f['centre'])
    out = set()
    for f in bsp.faces:
        if f['flags'] & SURF_LIGHT and f['value'] > 0 and not f['flags'] & (SURF_SKY | SURF_WARP | SURF_NODRAW) and \
                not any(s for s in f['styles']):
            c = f['centre']
            if any(all(abs(c[j] - q[j]) <= tol for j in range(3)) for q in plain.get(f['tex'], ())):
                out.add(f['index'])
    return out


def patches(bsp, f):
    """[(pos, area)]: face f split on a PATCH grid of its luxels"""
    w, h = f['size']; step = max(1, int(PATCH / 16))
    cells = []
    for j in range(0, h, step):
        for i in range(0, w, step):
            p = bsp.luxel_pos(f, min(i + step / 2.0, w - 1), min(j + step / 2.0, h - 1))
            if p and inside(f, p, 8.0):
                cells.append(p)
    if not cells:
        return [(f['centre'], f['area'])]
    return [(p, f['area'] / len(cells)) for p in cells]


def inside(f, p, margin):
    """p (on the plane of f) within margin units of the face polygon (convex)"""
    pts, n = f['pts'], f['normal']
    for k in range(len(pts)):
        a, b = pts[k], pts[(k + 1) % len(pts)]
        e = [b[j] - a[j] for j in range(3)]
        out = cross(e, n); ln = math.sqrt(dot(out, out)) or 1.0
        if dot(out, [f['centre'][j] - a[j] for j in range(3)]) > 0:
            ln = -ln
        if dot(out, [p[j] - a[j] for j in range(3)]) / ln > margin:
            return False
    return True


def sky_faces(bsp):
    return [(f['normal'], f['dist'], [min(q[j] for q in f['pts']) - 12 for j in range(3)],
             [max(q[j] for q in f['pts']) + 12 for j in range(3)], f['value'] if f['flags'] & SURF_LIGHT else 0)
            for f in bsp.faces if f['flags'] & SURF_SKY]


def sees_sky(bsp, sky, p, d):
    """-1 when the ray p + t*d ends on no SURF_SKY face, else that face's light value (qrad sky light when > 0)"""
    q = bsp.first_hit(p, tuple(p[k] + d[k] * 16384 for k in range(3)))
    if q is None:
        return -1
    for n, dist, lo, hi, v in sky:
        if abs(dot(n, q) - dist) < 12 and all(lo[j] <= q[j] <= hi[j] for j in range(3)):
            return v
    return -1


def wmedian(pairs):
    """weighted median of (value, weight)"""
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    if not tot:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= tot / 2:
            return v
    return pairs[-1][0]


class Analysis:
    def __init__(self, path, lights=None, ini=None, emissive=None, styled=False, ratio=4.0, colors=None):
        self.path = path; self.map = os.path.splitext(os.path.basename(path))[0].lower()
        self.bsp = bsp = Bsp(path)
        self.prm = read_ini(ini, self.map)
        self.rows, self.sun, self.raw = read_lights(lights)
        self.styled = styled; self.ratio = ratio
        self.world = bsp.entities[0] if bsp.entities else {}
        emissive = emissive or {}
        prm = self.prm
        self.points = []
        for r in self.rows:
            if r['startoff'] or r['scale'] <= 0 or (r['style'] and not styled):
                continue
            rad = r['radius'] if r['radius'] > 0 else (prm['radius'] if self.raw else 4.0)
            inten = remix_intensity(r['light'], prm, self.raw)
            if self.raw:
                inten *= r['scale']
            k = inten * math.pi * rad * rad
            d = r['dir']
            if d:
                ln = math.sqrt(dot(d, d)) or 1.0; d = [c / ln for c in d]
            self.points.append(dict(row=r, pos=tuple(r['pos']), k=k * lum(r['color']), kq=r['light'], dir=d,
                                    cos=math.cos(math.radians(r['cone'])) if d else -2))
        colors = colors or {}
        self.emit = []
        self.surf = []
        self.skylight = [f for f in bsp.faces if f['flags'] & SURF_SKY and f['flags'] & SURF_LIGHT and f['value'] > 0]
        self.masked = masked_emitters(bsp, set(emissive))
        for f in bsp.faces:
            if f['flags'] & SURF_LIGHT and f['value'] > 0 and not f['flags'] & (SURF_SKY | SURF_WARP | SURF_NODRAW):
                self.surf.append(f)
                if f['index'] in self.masked:
                    continue
                le = emissive.get(f['tex'], min(max(f['value'] / 100.0, 1.0), 15.0)) * colors.get(f['tex'], EMIT_ALBEDO)
                for p, a in patches(bsp, f):
                    self.emit.append(dict(pos=tuple(p[k] + f['normal'][k] for k in range(3)), n=f['normal'],
                                          k=le * a, face=f))
        self.sky = sky_faces(bsp)
        self.tree = fv.Tree(path)
        self.sun_k = 0.0
        if self.sun and self.sun['scale'] > 0:
            half = math.radians(self.sun['angle'] / 2.0)
            self.sun_k = (self.sun['light'] * self.sun['scale'] * prm['sun_scale'] * prm['scale'] * lum(self.sun['color'])
                          * 2 * math.pi * (1 - math.cos(half)))
            sd = self.sun['dir']; ln = math.sqrt(dot(sd, sd)) or 1.0
            self.to_sun = tuple(-c / ln for c in sd)
        self.grid = defaultdict(list)
        for kind, lst in (('p', self.points), ('e', self.emit)):
            for s in lst:
                self.grid[tuple(int(s['pos'][j] // 512) for j in range(3))].append((kind, s))

    def near_sources(self, p, reach=1536):
        c = tuple(int(p[j] // 512) for j in range(3)); r = int(reach // 512) + 1
        for x in range(c[0] - r, c[0] + r + 1):
            for y in range(c[1] - r, c[1] + r + 1):
                for z in range(c[2] - r, c[2] + r + 1):
                    yield from self.grid.get((x, y, z), ())

    def remix(self, p, n):
        """(E, E_point, E_emit, Q): estimated Remix irradiance (luminance) at p with normal n, and the Quake-linear
        point-light sum Q = sum((light - d) * cos)"""
        cand = []
        q = 0.0
        for kind, s in self.near_sources(p):
            v = [s['pos'][j] - p[j] for j in range(3)]
            d2 = dot(v, v)
            if d2 < 1.0:
                continue
            d = math.sqrt(d2); u = [c / d for c in v]
            cs = dot(u, n)
            if cs <= 0:
                continue
            if kind == 'p':
                if s['dir'] and -dot(u, s['dir']) < s['cos']:
                    continue
                e = s['k'] * cs / d2
                ql = max(s['kq'] - d, 0.0) * cs
            else:
                ce = -dot(u, s['n'])
                if ce <= 0:
                    continue
                e = s['k'] * ce * cs / d2; ql = 0.0
            cand.append((e, kind, s, ql))
        cand.sort(key=lambda c: -c[0])
        tot = sum(c[0] for c in cand)
        ep = ee = 0.0; rest = tot
        for e, kind, s, ql in cand:
            if e < 1e-6 or (ep + ee > 0 and rest < 0.03 * (ep + ee)):
                break
            rest -= e
            if self.bsp.clear(p, s['pos']):
                if kind == 'p':
                    ep += e; q += ql
                else:
                    ee += e
        for e, kind, s, ql in cand:
            if kind == 'p' and ql > 0 and e < 1e-6 and self.bsp.clear(p, s['pos']):
                q += ql
        es = 0.0
        if self.sun_k:
            cs = dot(self.to_sun, n)
            if cs > 0 and sees_sky(self.bsp, self.sky, p, self.to_sun) >= 0:
                es = self.sun_k * cs
        return ep + ee + es, ep + es, ee, q

    def samples(self):
        """luxel samples on 2x2 luxel blocks: (pos off the surface, normal, rgb, area, face, style-0 luminance)"""
        out = []
        for f in self.bsp.faces:
            if f['flags'] & (SURF_SKY | SURF_WARP | SURF_NODRAW | SURF_TRANS33 | SURF_TRANS66) or \
                    (f['flags'] & SURF_LIGHT and f['value'] > 0):
                continue
            lux = self.bsp.baked(f, self.styled)
            if not lux:
                continue
            lux0 = self.bsp.baked(f) if self.styled else lux
            if len(lux0) != len(lux):
                lux0 = [(q, (0, 0, 0)) for q, _ in lux]
            w, h = f['size']
            for j in range(0, h, 2):
                for i in range(0, w, 2):
                    ks = [jj * w + ii for jj in (j, j + 1) for ii in (i, i + 1) if jj < h and ii < w]
                    ks = [k for k in ks if inside(f, lux[k][0], 4.0)]
                    blk = [lux[k] for k in ks]
                    if not blk:
                        continue
                    p = tuple(sum(b[0][k] for b in blk) / len(blk) + f['normal'][k] * 2.0 for k in range(3))
                    # luxels at the face's edge can sit in the neighbouring wall: pull them towards the centre
                    c = [f['centre'][k] + f['normal'][k] * 2.0 for k in range(3)]
                    for t in (0.0, 4.0, 8.0, 16.0):
                        dl = math.dist(p, c)
                        q = tuple(p[k] + (c[k] - p[k]) * min(t / dl, 1.0) for k in range(3)) if dl > 0 else p
                        if not self.bsp.solid(q):
                            break
                    else:
                        continue
                    p = q
                    rgb = tuple(sum(b[1][k] for b in blk) / len(blk) for k in range(3))
                    out.append((p, f['normal'], rgb, 256.0 * len(blk), f, sum(lum(lux0[k][1]) for k in ks) / len(ks)))
        return out

    def run(self, bright_pct=0.6):
        smp = self.samples()
        if not smp:
            self.result = dict(map=self.map, K=None, clusters=[], gap=0.0, samples=0); return self.result
        ls = sorted(lum(s[2]) for s in smp)
        self.bright = max(ls[int(bright_pct * (len(ls) - 1))], 24.0)
        ev = []
        for p, n, rgb, a, f, b0 in smp:
            b = lum(rgb)
            if b < self.bright:
                continue
            e, ep, ee, q = self.remix(p, n)
            ev.append((p, n, rgb, a, f, b, e, ep, ee, q, b0))
        K = wmedian([(s[10] / s[6], s[3]) for s in ev if s[6] > 0 and s[10] > 0])
        Kq = wmedian([(s[10] / s[9], s[3]) for s in ev if s[9] > 0 and s[10] > 0])
        self.K, self.Kq = K, Kq
        gaps = []
        for s in ev:
            if K is None or s[5] > self.ratio * K * s[6]:
                gaps.append(s)
        self.result = dict(map=self.map, K=K, Kq=Kq, bright=self.bright, samples=len(smp), evaluated=len(ev),
                           masked=sorted(self.masked), clusters=self.clusters(gaps))
        self.result['gap'] = sum(c['excess'] for c in self.result['clusters'])
        lit = sum(s[3] * s[5] for s in ev) / 255.0
        self.result['gap_share'] = self.result['gap'] / lit if lit else 0.0
        return self.result

    def clusters(self, gaps):
        K = self.K or 0.0
        cells = defaultdict(list)
        for s in gaps:
            cells[tuple(int(math.floor(s[0][j] / CELL)) for j in range(3))].append(s)
        seen = set(); out = []
        for c0 in cells:
            if c0 in seen:
                continue
            comp = []; stack = [c0]; seen.add(c0)
            while stack:
                c = stack.pop(); comp.extend(cells[c])
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            nb = (c[0] + dx, c[1] + dy, c[2] + dz)
                            if nb in cells and nb not in seen:
                                seen.add(nb); stack.append(nb)
            out.append(self.describe(comp, K))
        out.sort(key=lambda c: -c['excess'])
        return out

    def describe(self, comp, K):
        A = sum(s[3] for s in comp)
        excess = sum(s[3] * max(s[5] - K * s[6], 0.0) for s in comp) / 255.0
        cen = tuple(sum(s[0][j] * s[3] for s in comp) / A for j in range(3))
        nrm = [sum(s[1][j] * s[3] for s in comp) for j in range(3)]
        ln = math.sqrt(dot(nrm, nrm)) or 1.0; nrm = tuple(c / ln for c in nrm)
        lo = [min(s[0][j] for s in comp) for j in range(3)]; hi = [max(s[0][j] for s in comp) for j in range(3)]
        rgb = [sum(s[2][j] * s[3] for s in comp) / A for j in range(3)]
        b = sum(s[5] * s[3] for s in comp) / A
        e = sum(s[6] * s[3] for s in comp) / A
        q = sum(s[9] * s[3] for s in comp) / A
        styled = 1.0 - sum(s[10] * s[3] for s in comp) / A / b if b else 0.0
        # anchor: the brightest sample's spot (centre of mass can fall outside an L-shaped patch)
        top = max(comp, key=lambda s: s[5] * s[3])
        anchor = top[0]; anrm = top[1]
        src = self.sources(anchor, anrm)
        point_share = (self.Kq or 0.0) * q / b if b else 0.0
        main = src['surf'][0] if src['surf'] and src['surf'][0]['share'] > 0.25 else None
        if main and main['masked']:
            kind = 'masked emitter'
        elif styled > 0.5:
            kind = 'styled light'
        elif point_share > 0.6:
            kind = 'falloff'
        elif main:
            kind = 'surface light'
        elif src['sky'] > 0:
            kind = 'sky light'
        elif src['sky'] >= 0 and src['ambient']:
            kind = 'ambient'
        else:
            kind = 'bounce'
        sug = self.suggest(comp, anchor, anrm, rgb, b, e, K, src, kind, hi, lo)
        return dict(centre=[round(c, 1) for c in cen], anchor=[round(c, 1) for c in anchor],
                    normal=[round(c, 2) for c in anrm], size=[round(hi[j] - lo[j] + 32) for j in range(3)],
                    area=round(A), excess=round(excess, 1), baked=round(b, 1), remix=round(K * e, 2),
                    ratio=round(b / (K * e), 1) if K * e > 0 else None,
                    color=[round(c / max(max(rgb), 1e-6), 3) for c in rgb], kind=kind, point_share=round(point_share, 2),
                    styled_share=round(styled, 2),
                    lights=src['lights'], surf=src['surf'], sky=src['sky'], ambient=src['ambient'],
                    suggest=sug, view=self.view(anchor, anrm))

    def sources(self, p, n):
        lights = []
        for s in self.points:
            d = math.dist(s['pos'], p)
            if d < 768:
                lights.append((d, s))
        lights.sort(key=lambda x: x[0])
        ll = [dict(index=s['row']['index'], light=s['row']['light'], dist=round(d), visible=self.bsp.clear(p, s['pos']))
              for d, s in lights[:3]]
        surf = {}
        for f in self.surf:
            v = [f['centre'][j] - p[j] for j in range(3)]
            d = math.sqrt(dot(v, v))
            if d > 1024 or d < 1:
                continue
            u = [c / d for c in v]
            cs, ce = dot(u, n), -dot(u, f['normal'])
            if cs <= 0 or ce <= 0:
                continue
            c = f['value'] * f['area'] * cs * ce / (d * d + f['area'])
            if c <= 0 or not self.bsp.clear(p, tuple(f['centre'][j] + f['normal'][j] for j in range(3))):
                continue
            key = (f['tex'], f['value'])
            g = surf.setdefault(key, dict(tex=f['tex'], value=f['value'], c=0.0, dist=d, faces=0, pos=f['centre'],
                                          normal=f['normal'], best=0.0, masked=0))
            g['c'] += c; g['faces'] += 1; g['masked'] += f['index'] in self.masked
            if c > g['best']:
                g['best'] = c; g['pos'] = f['centre']; g['normal'] = f['normal']; g['dist'] = d
        tot = sum(g['c'] for g in surf.values())
        q = 0.0
        for d, s in lights:
            if s['kq'] > d and self.bsp.clear(p, s['pos']):
                q += s['kq'] - d
        sl = sorted(surf.values(), key=lambda g: -g['c'])[:2]
        # surface-light share against point lights in the same (qrad-like) units: value*A/d^2 vs (light - d)
        out = [dict(tex=g['tex'], value=g['value'], faces=g['faces'], dist=round(g['dist']),
                    pos=[round(c, 1) for c in g['pos']], normal=[round(c, 2) for c in g['normal']], masked=g['masked'],
                    share=round(g['c'] / (tot + q) if tot + q else 0.0, 2)) for g in sl]
        sky = max([sees_sky(self.bsp, self.sky, p, d) for d in ((0, 0, 1), (n[0] * .5, n[1] * .5, .87),
                                                                (n[0], n[1], .3), (n[0], n[1], n[2])) if dot(d, n) > 0] or [-1])
        amb = {k: self.world[k] for k in ('_sun_ambient', '_ambient', 'ambient', '_minlight', 'minlight')
               if k in self.world}
        return dict(lights=ll, surf=out, sky=sky, ambient=amb)

    def suggest(self, comp, anchor, n, rgb, b, e, K, src, kind, hi, lo):
        """override `add` row: at the surface source (in front of it) or off the bright surface"""
        tree = self.tree
        ext = max(hi[j] - lo[j] for j in range(3)) + 32
        need = max(b / K - e, 0.0) if K else 0.0
        if kind in ('surface light', 'masked emitter') and src['surf']:
            s = src['surf'][0]
            pos = [s['pos'][j] + s['normal'][j] * 16 for j in range(3)]
            dist = max(math.dist(pos, anchor), 16.0)
        else:
            dist = min(max(0.5 * ext, 48.0), 256.0)
            pos = None
            for dd in (dist, dist * 0.6, dist * 0.35, 24.0):
                q = [anchor[j] + n[j] * dd for j in range(3)]
                if tree.empty(q) and self.bsp.clear(anchor, q):
                    pos, dist = q, dd; break
            pos = pos or [anchor[j] + n[j] * 24 for j in range(3)]
        rad = self.prm['radius']
        inten = need * dist * dist / (math.pi * rad * rad * max(lum([c / max(max(rgb), 1e-6) for c in rgb]), 0.05))
        light = raw_light(inten, self.prm) if self.raw else inten
        col = [c / max(max(rgb), 1e-6) for c in rgb]
        return dict(pos=[round(c) for c in pos], color=[round(c, 2) for c in col], light=round(min(light, 3000)),
                    line='add %d %d %d %.2f %.2f %.2f %d 0' % (round(pos[0]), round(pos[1]), round(pos[2]),
                                                               col[0], col[1], col[2], round(min(light, 3000))))

    def view(self, c, n):
        tree = self.tree
        for dist in (160.0, 240.0, 96.0):
            for cam in fv.candidates(c, n, dist):
                if tree.empty(cam) and tree.clear(cam, c):
                    p, y = fv.look(cam, c)
                    return [round(cam[0], 1), round(cam[1], 1), round(cam[2], 1), round(p, 1), round(y, 1)]
        return None


def report(res, top):
    print('%s: K %.4g, bright >= %.0f, %d samples, gap %.0f (%.1f%% of the bright light), %d clusters%s' % (
        res['map'], res['K'] or 0, res.get('bright', 0), res['samples'], res['gap'], 100 * res.get('gap_share', 0),
        len(res['clusters']), ', %d light faces with emission switched off by .estyles' % len(res['masked'])
        if res.get('masked') else ''))
    for i, c in enumerate(res['clusters'][:top]):
        print('  #%d excess %.0f at %s size %s n %s: baked %.0f vs Remix %.1f (x%s), colour %s, %s' % (
            i, c['excess'], ' '.join('%.0f' % v for v in c['anchor']), 'x'.join(str(v) for v in c['size']),
            ' '.join('%.2f' % v for v in c['normal']), c['baked'], c['remix'], c['ratio'],
            ' '.join('%.2f' % v for v in c['color']), c['kind']))
        if c['surf']:
            print('     surface lights: ' + '; '.join('%s value %d x%d%s at %d (share %.2f)' % (
                s['tex'], s['value'], s['faces'], ' (%d off by .estyles)' % s['masked'] if s['masked'] else '',
                s['dist'], s['share']) for s in c['surf']))
        if c['lights']:
            print('     lights: ' + '; '.join('#%s light %g at %d%s' % (l['index'], l['light'], l['dist'],
                                                                     '' if l['visible'] else ' (hidden)')
                                           for l in c['lights']))
        extra = []
        if c['sky'] >= 0:
            extra.append('sky in view' + (' (sky light %d)' % c['sky'] if c['sky'] > 0 else ''))
        if c['styled_share'] > 0.05:
            extra.append('styled lightmaps %.0f%%' % (100 * c['styled_share']))
        if c['ambient']:
            extra.append(' '.join('%s %s' % kv for kv in c['ambient'].items()))
        if extra:
            print('     ' + ', '.join(extra))
        if c['view']:
            print('     view: %s gap%d %s' % (res['map'], i, ' '.join('%.1f' % v for v in c['view'])))
        print('     candidate: ' + c['suggest']['line'])


def write_override(res, outdir, top):
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, res['map'] + '.candidates.override')
    rows = ['# %s: CANDIDATE fill lights from tools/baked_light_gaps.py, untested; check each in game before keeping' %
            res['map'], '# (append the wanted lines to rtx-remix/maplights/%s.override)' % res['map']]
    for i, c in enumerate(res['clusters'][:top]):
        src = c['kind'] + (' ' + c['surf'][0]['tex'] if c['kind'] in ('surface light', 'masked emitter') and c['surf']
                           else '')
        rows.append('# gap%d: excess %.0f, baked %.0f vs Remix %.1f, %s, surface at %s; view %s' % (
            i, c['excess'], c['baked'], c['remix'], src, ' '.join('%.0f' % v for v in c['anchor']),
            ' '.join('%.1f' % v for v in c['view']) if c['view'] else '-'))
        if c['kind'] == 'masked emitter':
            rows.append('# (better: keep the light face out of the style-0 .estyles rows; this fill light stands in)')
        rows.append(c['suggest']['line'])
    open(path, 'w').write('\n'.join(rows) + '\n')
    return path


def analyse(path, a, em, colors):
    lights = a.lights
    if not lights and a.lights_dir:
        lights = os.path.join(a.lights_dir, os.path.splitext(os.path.basename(path))[0].lower() + '.lights')
    return Analysis(path, lights, a.ini, em, a.styled, a.ratio, colors).run()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('maps', nargs='+')
    ap.add_argument('--lights', help='.lights file (one map)')
    ap.add_argument('--lights-dir', help='directory with <map>.lights (and <map>.override)')
    ap.add_argument('--ini', help='anox_customise.ini for the [maplights.*] formula')
    ap.add_argument('--emissive-dir', help='BSPs that set the emissive intensities (default: the map\'s directory)')
    ap.add_argument('--textures', help='texture directory (anoxdata/textures) for the emissive colours (needs PIL)')
    ap.add_argument('--ratio', type=float, default=4.0, help='baked / (K * Remix) above which a luxel is a gap')
    ap.add_argument('--styled', action='store_true', help='include styled lightmaps and lights')
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--overrides', help='write <map>.candidates.override files here')
    ap.add_argument('--json', help='write all results as JSON')
    ap.add_argument('--jobs', type=int, default=1)
    a = ap.parse_args(argv)
    if a.lights and len(a.maps) > 1:
        ap.error('--lights takes one map; use --lights-dir')
    em = emissive_table(a.emissive_dir or os.path.dirname(os.path.abspath(a.maps[0])),
                        os.path.join(here, '..', 'maps', 'emissive_intensity.tsv'))
    colors = texture_colors(a.textures, em) if a.textures else {}
    n = len(a.maps)
    if a.jobs > 1 and n > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.jobs) as ex:
            results = list(ex.map(analyse, a.maps, [a] * n, [em] * n, [colors] * n))
    else:
        results = [analyse(p, a, em, colors) for p in a.maps]
    for res in sorted(results, key=lambda r: -r['gap']):
        report(res, a.top)
        if a.overrides and res['clusters']:
            write_override(res, a.overrides, a.top)
    if len(results) > 1:
        print('\nmaps by gap:')
        for res in sorted(results, key=lambda r: -r['gap']):
            print('  %-16s %8.0f  %5.1f%%  %d clusters' % (res['map'], res['gap'], 100 * res.get('gap_share', 0),
                                                         len(res['clusters'])))
    if a.json:
        json.dump(results, open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
