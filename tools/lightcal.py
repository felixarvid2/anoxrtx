#!/usr/bin/env python3
"""Empirically calibrate Anachronox light keys `falloff` and `cap` from baked lightmaps.

usage: lightcal.py [MAPS_DIR]    (default: scratchpad maps dir)

For each static (style 0) light, luxels of the baked lightmap (first style block, raw 0..255 RGB,
no overbright correction) within 1024 units, on faces facing the light, whose nearest other light
is >= 2x farther, are sampled as (distance, luminance / colour luminance).  No occlusion test, so
samples contain noise from walls in between, sun/ambient, and light from non-light surfaces.
Pure Python (numpy not installed).  Per falloff group: median b/L profile by distance bin, and fits
  linear   b = a*(L - k*d)      (least squares in b on [L, d]; reach = L/k)
  inverse  b = a*L/d^p          (grid on p, a closed form, least squares in log b)
Capped lights: plateau (high percentile of b near the light) vs cap value.
"""
import glob, importlib.util, math, os, struct, sys, time, random
from collections import defaultdict

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('bspinfo', os.path.join(here, 'bspinfo.py'))
bspinfo = importlib.util.module_from_spec(spec); spec.loader.exec_module(bspinfo)

DEF = '/tmp/claude-1000/-home-felix/bd228632-acec-45ae-b061-56839c96ea01/scratchpad/maps'
MAXR = 1024.0
MAXLUX = 80000   # luxel subsample per map
random.seed(1)


def lumps_of(data):
    return [struct.unpack_from('<ii', data, 8 + 8 * i) for i in range(19)]


def luxels(path):
    """yield (pos, normal, rgb) for static lightmap luxels, subsampled."""
    data = open(path, 'rb').read()
    L = lumps_of(data)
    def arr(i, fmt, sz):
        o, n = L[i]
        return [struct.unpack_from(fmt, data, o + k * sz) for k in range(n // sz)]
    planes = arr(1, '<4fi', 20)
    verts = arr(2, '<3f', 12)
    faces = arr(6, '<hhihh4Bi', 20)
    texinfo = arr(5, '<8f2i32si', 76)
    edges = arr(11, '<2H', 4)
    surfedges = [x[0] for x in arr(12, '<i', 4)]
    lo, ln = L[7]
    light = data[lo:lo + ln]
    cand = []
    for f in faces:
        pn, side, fe, ne, ti, s0, s1, s2, s3, lofs = f
        if lofs < 0 or s0 != 0 or lofs + 3 > len(light):
            continue
        t = texinfo[ti]
        if t[9] & 0xC:
            continue
        pl = planes[pn]
        n = (pl[0], pl[1], pl[2]); dist = pl[3]
        if side:
            n = (-n[0], -n[1], -n[2]); dist = -dist
        S = t[0:3]; s_off = t[3]; T = t[4:7]; t_off = t[7]
        pts = []
        for k in range(ne):
            se = surfedges[fe + k]
            v = verts[edges[se][0]] if se >= 0 else verts[edges[-se][1]]
            pts.append(v)
        ss = [v[0]*S[0]+v[1]*S[1]+v[2]*S[2]+s_off for v in pts]
        tt = [v[0]*T[0]+v[1]*T[1]+v[2]*T[2]+t_off for v in pts]
        ms, Ms = math.floor(min(ss)/16), math.ceil(max(ss)/16)
        mt, Mt = math.floor(min(tt)/16), math.ceil(max(tt)/16)
        w, h = Ms - ms + 1, Mt - mt + 1
        if lofs + w*h*3 > len(light):
            continue
        # solve [S;T;n] p = [s - s_off; t - t_off; dist]
        a = (S, T, n)
        det = (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1]) - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
               + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
        if abs(det) < 1e-9:
            continue
        def cross(u, v): return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        cTn, cnS, cST = cross(T, n), cross(n, S), cross(S, T)
        for j in range(h):
            for i in range(w):
                cand.append((lofs + (j*w + i)*3, (ms+i)*16 - s_off, (mt+j)*16 - t_off, dist,
                             cTn, cnS, cST, det, n))
    if len(cand) > MAXLUX:
        cand = random.sample(cand, MAXLUX)
    for off, sv, tv, dist, cTn, cnS, cST, det, n in cand:
        p = tuple((sv*cTn[k] + tv*cnS[k] + dist*cST[k]) / det for k in range(3))
        yield p, n, light[off:off+3]


def lum(c): return 0.299*c[0] + 0.587*c[1] + 0.114*c[2]


def pct(v, q):
    v = sorted(v)
    return v[min(len(v)-1, int(q*len(v)))] if v else float('nan')


def collect(mapsdir):
    samples = []   # (d, b, Lval, falloff, cap, has_cap)
    files = sorted(glob.glob(os.path.join(mapsdir, '*.bsp')))
    for fp in files:
        try:
            ver, ents, tex = bspinfo.load(fp)
            ls = [l for l in bspinfo.lights(ents) if l['style'] in ('', '0')]
            if not ls:
                continue
            # lights must be pointlike entities; skip spotlights (target) for cleanliness
            ls = [l for l in ls if not l['target']]
            others_all = ls
            grid = defaultdict(list)
            for k, l in enumerate(ls):
                o = l['origin']
                grid[(int(o[0]//2048), int(o[1]//2048), int(o[2]//2048))].append(k)
            for pos, n, rgb in luxels(fp):
                cx, cy, cz = int(pos[0]//2048), int(pos[1]//2048), int(pos[2]//2048)
                near = [k for x in (cx-1, cx, cx+1) for y in (cy-1, cy, cy+1) for z in (cz-1, cz, cz+1)
                        for k in grid.get((x, y, z), ())]
                if not near: continue
                b = lum(rgb)
                ds = []
                for k in near:
                    o = ls[k]['origin']
                    dx, dy, dz = o[0]-pos[0], o[1]-pos[1], o[2]-pos[2]
                    d2 = dx*dx+dy*dy+dz*dz
                    if d2 < 4*MAXR*MAXR:
                        ds.append((d2, k, dx*n[0]+dy*n[1]+dz*n[2]))
                if not ds:
                    continue
                ds.sort()
                d2, k, facing = ds[0]
                d = math.sqrt(d2)
                if d > MAXR or d < 24 or facing <= 0:
                    continue
                if len(ds) > 1 and math.sqrt(ds[1][0]) < 2*d:
                    continue
                l = ls[k]
                kk = l['keys']
                cl = max(lum([c if c <= 1.0001 else c/255.0 for c in l['color']]), 0.1)
                fo = kk.get('falloff', '')
                cp = kk.get('cap', '')
                try: fo = float(fo)
                except ValueError: fo = None
                try: cp = float(cp)
                except ValueError: cp = None
                samples.append((d, b/cl, l['light'], fo, cp, (fp, k)))
        except Exception as e:
            print('skip', fp, e, file=sys.stderr)
    return samples, len(files)


def lstsq2(X, y):
    """least squares y = c0*x0 + c1*x1 (no intercept)."""
    s00 = sum(a*a for a, _ in X); s01 = sum(a*b for a, b in X); s11 = sum(b*b for _, b in X)
    t0 = sum(a*yy for (a, _), yy in zip(X, y)); t1 = sum(b*yy for (_, b), yy in zip(X, y))
    det = s00*s11 - s01*s01
    if abs(det) < 1e-12: return None
    return (t0*s11 - t1*s01)/det, (s00*t1 - s01*t0)/det


def fit(group):
    """group: list of (d, b, L). Use unsaturated, non-black luxels. Returns dict."""
    g = [s for s in group if 3 <= s[1] <= 250 and s[2] > 0]
    if len(g) < 40: return None
    X = [(L, d) for d, b, L in g]; y = [b for d, b, L in g]
    c = lstsq2(X, y)
    if not c: return None
    a, ad = c
    k = -ad / a if a else float('nan')
    ss = sum((yy - (a*x0 + ad*x1))**2 for (x0, x1), yy in zip(X, y))
    mean = sum(y)/len(y); sst = sum((yy-mean)**2 for yy in y)
    r2_lin = 1 - ss/sst
    # inverse power: log b = log a + log L - p log d
    best = None
    ly = [math.log(b/L) for d, b, L in g]; lx = [math.log(d) for d, b, L in g]
    mx = sum(lx)/len(lx); my = sum(ly)/len(ly)
    sxx = sum((x-mx)**2 for x in lx)
    p = -sum((x-mx)*(yy-my) for x, yy in zip(lx, ly))/sxx
    la = my + p*mx
    pred = [math.exp(la)*L/d**p for d, b, L in g]
    ss2 = sum((yy-pp)**2 for yy, pp in zip(y, pred))
    r2_pow = 1 - ss2/sst
    return dict(n=len(g), a=a, k=k, reach=(a and 1/ (k/ (1.0)) if k > 0 else float('inf')),
                r2_lin=r2_lin, p=p, r2_pow=r2_pow, pa=math.exp(la))


def env_report(groups):
    """Envelope fit: p90 of b/L in log-spaced distance bins (luxels with b<250), linear + power fits."""
    print('\nEnvelope (p90 of b/L per distance bin, unsaturated): linear k=-slope/intercept vs power p')
    print('%-9s %-4s %6s %8s %7s %7s %8s %7s' % ('falloff', 'cap', 'n', 'env@d0', 'k_lin', 'R2lin', 'p_pow', 'R2pow'))
    edges = [24, 40, 64, 100, 160, 256, 400, 640, 1024]
    for key in sorted(groups, key=lambda k: (k[0] is None, k[0] or 0, k[1])):
        g = groups[key]
        if len(g) < 400: continue
        pts = []
        for lo, hi in zip(edges, edges[1:]):
            v = [b/L for d, b, L in g if lo <= d < hi and L > 0 and b < 250]
            if len(v) >= 25: pts.append((math.sqrt(lo*hi), pct(v, .9)))
        pts = [(d, e) for d, e in pts if e > 0.002]
        if len(pts) < 4: continue
        n = len(pts); mx = sum(d for d, e in pts)/n; my = sum(e for d, e in pts)/n
        sxx = sum((d-mx)**2 for d, e in pts)
        c1 = sum((d-mx)*(e-my) for d, e in pts)/sxx; c0 = my - c1*mx
        sst = sum((e-my)**2 for d, e in pts) or 1e-12
        r2l = 1 - sum((e-(c0+c1*d))**2 for d, e in pts)/sst
        lx = [math.log(d) for d, e in pts]; ly = [math.log(e) for d, e in pts]
        ax = sum(lx)/n; ay = sum(ly)/n
        sl = sum((x-ax)*(y-ay) for x, y in zip(lx, ly))/sum((x-ax)**2 for x in lx)
        ic = ay - sl*ax
        r2p = 1 - sum((e-math.exp(ic)*d**sl)**2 for d, e in pts)/sst
        fs = ('%.2f' % key[0]) if key[0] is not None else 'none'
        print('%-9s %-4s %6d %8.3f %7.4f %7.2f %8.2f %7.2f' % (fs, 'yes' if key[1] else 'no', len(g), c0,
              -c1/c0 if c0 else float('nan'), r2l, -sl, r2p))


def perlight_report(samples):
    """Per-light reach: farthest distance with a lit luxel (b>=THR); occlusion only shrinks it."""
    THR = 8
    bylight = defaultdict(list)
    for d, b, L, fo, cp, i in samples:
        bylight[i].append((d, b, L, fo, cp))
    print('\nPer-light: reach = 90th pct distance of luxels with b>=%d (lights with >=150 samples, >=15 lit);' % THR)
    print('peak = p90 of b/L for d<150.  Hypothesis A reach ~ L/falloff-ish; compare reach*falloff/L')
    print('%-9s %-4s %6s %7s %9s %11s %8s %8s' % ('falloff', 'cap', 'lights', 'medL', 'reach', 'reach/L', 'r*F/L', 'peak/L'))
    agg = defaultdict(list)
    for i, v in bylight.items():
        if len(v) < 150: continue
        lit = [d for d, b, L, fo, cp in v if b >= THR]
        if len(lit) < 15: continue
        L, fo, cp = v[0][2], v[0][3], v[0][4]
        near = [b/L for d, b, L2, f2, c2 in v if d < 150 and L > 0]
        agg[(fo, cp is not None)].append((L, pct(lit, .9), pct(near, .9) if len(near) >= 8 else float('nan')))
    for key in sorted(agg, key=lambda k: (k[0] is None, k[0] or 0, k[1])):
        a = agg[key]
        if len(a) < 5: continue
        med = lambda x: pct([y for y in x if y == y], .5)
        fo = key[0]
        rl = [r/L for L, r, p in a]
        rf = [r*(fo if fo else 1)/L for L, r, p in a]
        print('%-9s %-4s %6d %7.0f %9.0f %11.2f %8.2f %8.2f' % ('none' if fo is None else '%.2f' % fo,
              'yes' if key[1] else 'no', len(a), med([L for L, r, p in a]), med([r for L, r, p in a]),
              med(rl), med(rf), med([p for L, r, p in a])))


def main():
    t0 = time.time()
    mapsdir = sys.argv[1] if len(sys.argv) > 1 else DEF
    import pickle
    cache = os.environ.get('LIGHTCAL_CACHE')
    if cache and os.path.exists(cache):
        samples, nmaps = pickle.load(open(cache, 'rb'))
    else:
        samples, nmaps = collect(mapsdir)
        if cache: pickle.dump((samples, nmaps), open(cache, 'wb'))
    print('maps: %d  samples: %d  (raw luxel bytes, luminance / light colour luminance)' % (nmaps, len(samples)))
    groups = defaultdict(list)
    for d, b, L, fo, cp, _id in samples:
        groups[(fo, cp is not None)].append((d, b, L))
    bins = [(24, 64), (64, 128), (128, 256), (256, 512), (512, 1024)]
    print('\nb/L x1000 by distance bin as median/p90 (p90 ~ unoccluded envelope); fits on unsaturated luxels (3<=b<=250)')
    hdr = '%-9s %-4s %6s | ' % ('falloff', 'cap', 'n') + ' '.join('%7s' % ('%d-%d' % x) for x in bins) + \
          ' | %6s %7s %6s | %5s %6s' % ('a_lin', 'k', 'R2lin', 'p', 'R2pow')
    print(hdr)
    for key in sorted(groups, key=lambda k: (k[0] is None, k[0] or 0, k[1])):
        g = groups[key]
        if len(g) < 200: continue
        cells = []
        for lo, hi in bins:
            v = [b/L for d, b, L in g if lo <= d < hi and L > 0]
            cells.append('%3.0f/%-3.0f' % (1000*pct(v, .5), 1000*pct(v, .9)) if len(v) >= 20 else '%7s' % '-')
        f = fit(g)
        fs = ('%.2f' % key[0]) if key[0] is not None else 'none'
        tail = ' | %6.2f %7.4f %6.2f | %5.2f %6.2f' % (f['a'], f['k'], f['r2_lin'], f['p'], f['r2_pow']) if f else ' | (too few)'
        print('%-9s %-4s %6d | %s%s' % (fs, 'yes' if key[1] else 'no', len(g), ' '.join(cells), tail))
    env_report(groups)
    perlight_report(samples)
    # same-L controlled view: per falloff, light L in [250,350]
    print('\nControlled: only L in 250..350 -> slope of b vs d (per-falloff linear fit b = c0 + c1*d, d<=600)')
    print('%-9s %6s %8s %8s %9s' % ('falloff', 'n', 'c0', 'c1', 'zero@d'))
    for fo in sorted({k[0] for k in groups if k[0] is not None} | {None}, key=lambda x: (x is None, x or 0)):
        g = [(d, b) for d, b, L, f, cp, _id in samples if f == fo and cp is None and 250 <= L <= 350 and d <= 600 and 3 <= b <= 250]
        if len(g) < 100: continue
        n = len(g); mx = sum(d for d, b in g)/n; my = sum(b for d, b in g)/n
        c1 = sum((d-mx)*(b-my) for d, b in g)/sum((d-mx)**2 for d, b in g); c0 = my - c1*mx
        print('%-9s %6d %8.1f %8.4f %9s' % ('none' if fo is None else '%.2f' % fo, n, c0, c1,
              '%.0f' % (-c0/c1) if c1 < 0 else 'n/a'))
    # caps
    print('\nCap: samples within d<=200 (raw luminance/colour, not divided by L).  p95/p99 of b vs cap')
    print('%-6s %6s %7s %7s %7s %7s %8s' % ('cap', 'n', 'medL', 'medb', 'p95', 'p99', 'p95/cap'))
    bycap = defaultdict(list)
    for d, b, L, fo, cp, _id in samples:
        if cp is not None and d <= 200: bycap[cp].append((b, L))
    for cp in sorted(bycap):
        v = bycap[cp]
        if len(v) < 50: continue
        bb = [b for b, L in v]
        print('%-6g %6d %7.0f %7.1f %7.1f %7.1f %8.2f' % (cp, len(v), pct([L for b, L in v], .5), pct(bb, .5),
              pct(bb, .95), pct(bb, .99), pct(bb, .95)/cp))
    # capped vs uncapped, matched L: peak
    print('\nPeak (p95 of b, d<=150) by light value L bucket: uncapped vs capped')
    print('%-10s %8s %8s %8s %8s' % ('L bucket', 'n_unc', 'p95_unc', 'n_cap', 'p95_cap'))
    for lo, hi in [(0, 100), (100, 200), (200, 300), (300, 500), (500, 1000), (1000, 1e9)]:
        u = [b for d, b, L, fo, cp, _id in samples if cp is None and d <= 150 and lo <= L < hi]
        c = [b for d, b, L, fo, cp, _id in samples if cp is not None and d <= 150 and lo <= L < hi]
        print('%-10s %8d %8.1f %8d %8.1f' % ('%d-%s' % (lo, '+' if hi > 1e8 else int(hi)), len(u), pct(u, .95), len(c), pct(c, .95)))
    print('\nruntime %.1fs' % (time.time()-t0))


if __name__ == '__main__':
    main()
