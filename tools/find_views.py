#!/usr/bin/env python3
"""Find camera views for the test rig from a map's BSP: look at the surfaces that use a texture.

usage: find_views.py MAP.bsp TEXTURE[,TEXTURE...] [--count N] [--distance D] [--name PREFIX]
       find_views.py MAP.bsp --light N [--distance D]          (view of map light N, index as in <map>.lights)
       find_views.py MAP.bsp --spots N                          (N views from places the player or NPCs go)
       find_views.py MAP.bsp --sky N [--distance D]             (N views towards the sky from places the player goes)
       find_views.py MAP.bsp --entity CLASS[,CLASS...] [--count N] [--distance D]   (views of placed entities)

TEXTURE is a texture path as in the BSP (e.g. levant/proc_lava; substring match, case-insensitive). For the
largest faces that use it (one per texture, up to --count) the view is placed --distance units (default 140)
in front of the face along its normal, raised a little, looking at the face centre. Prints lines for
tools/anoxcheck.py --views:   MAP NAME X Y Z PITCH YAW
(QindieGL renders world views from rtx-remix/rigcam.txt "X Y Z PITCH YAW", Quake 2 angles: pitch > 0 = down.)
--spots picks eye-height views at info_player_start and path_corner entities, spread over the map (each next spot
the one farthest from those already picked), looking along the most open of 16 directions, slightly down; for
measuring a map as a whole (e.g. exposure) where the start view is unusable. Only spots in the PVS of the
spawn point are used (see --sky), and none within 96 units of it (the camera would be inside the player model).
--sky starts from the same player/NPC spots (only those in the PVS of the info_player_start the game spawns at: the one
without targetname, else the first; the engine draws nothing else) and looks (level or up to 30 degrees up) where the most traced rays
end on a SURF_SKY face; the N spots with the most sky, at least 512 units apart. For checking that the skybox shows
through windows and openings and is not hidden by fog.
--entity looks at placed entities of the given classnames (e.g. models from entity.dat) from eye height around them,
--distance away (shorter or longer if blocked), only inside the spawn's PVS; up to --count, 256 units apart.
Camera positions are checked against the BSP tree: only empty leaves inside the map (cluster >= 0, no solid or
liquid contents) are used,
trying shorter distances and, for floors, oblique views from four sides.
"""
import math, os, re, struct, sys


def lumps(data):
    return [struct.unpack_from('<ii', data, 8 + 8 * i) for i in range(19)]


def faces_with(path, wanted, flags=0, points=False):
    data = open(path, 'rb').read()
    L = lumps(data)
    def arr(i, size):
        off, ln = L[i]
        return off, ln // size
    poff, _ = arr(1, 20); voff, _ = arr(2, 12); eoff, _ = arr(11, 4); seoff, _ = arr(12, 4)
    toff, tn = arr(5, 76); foff, fn = arr(6, 20)
    tex = [data[toff + i * 76 + 40:toff + i * 76 + 72].split(b'\0', 1)[0].decode('latin-1').replace('\\', '/').lower()
           for i in range(tn)]
    out = []
    for i in range(fn):
        plane, side, first, num, ti = struct.unpack_from('<HHiHH', data, foff + i * 20)
        name = tex[ti]
        if flags:
            if not struct.unpack_from('<i', data, toff + ti * 76 + 32)[0] & flags:
                continue
        elif not any(w in name for w in wanted):
            continue
        pts = []
        for k in range(num):
            se = struct.unpack_from('<i', data, seoff + (first + k) * 4)[0]
            v0, v1 = struct.unpack_from('<HH', data, eoff + abs(se) * 4)
            pts.append(struct.unpack_from('<fff', data, voff + (v0 if se >= 0 else v1) * 12))
        n = list(struct.unpack_from('<fff', data, poff + plane * 20))
        if side:
            n = [-c for c in n]
        c = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
        area = 0.0
        for k in range(1, len(pts) - 1):
            a = [pts[k][j] - pts[0][j] for j in range(3)]; b = [pts[k + 1][j] - pts[0][j] for j in range(3)]
            x = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
            area += 0.5 * math.sqrt(sum(v * v for v in x))
        out.append((area, name, c, n, pts) if points else (area, name, c, n))
    return out


class Tree:
    """point contents from the BSP nodes/leaves (Quake 2 dnode_t 28 bytes, dleaf_t 28 bytes)"""
    def __init__(self, path):
        d = open(path, 'rb').read(); L = lumps(d)
        self.d = d; self.poff = L[1][0]; self.noff = L[4][0]; self.loff = L[8][0]

    def leaf(self, p):
        """(contents, cluster) of the leaf containing p"""
        n = 0
        while n >= 0:
            plane, c0, c1 = struct.unpack_from('<iii', self.d, self.noff + n * 28)
            nx, ny, nz, dist = struct.unpack_from('<ffff', self.d, self.poff + plane * 20)
            n = c0 if nx * p[0] + ny * p[1] + nz * p[2] - dist >= 0 else c1
        return struct.unpack_from('<ih', self.d, self.loff + (-1 - n) * 28)

    def pvs(self, cluster):
        """set of clusters potentially visible from cluster (Quake 2 run-length coded vis lump)"""
        voff = lumps(self.d)[3][0]
        nclusters = struct.unpack_from('<i', self.d, voff)[0]
        i = voff + struct.unpack_from('<i', self.d, voff + 4 + cluster * 8)[0]
        out = set(); c = 0
        while c < nclusters:
            b = self.d[i]; i += 1
            if b == 0:
                c += 8 * self.d[i]; i += 1
                continue
            for k in range(8):
                if b & (1 << k):
                    out.add(c + k)
            c += 8
        return out

    def empty(self, p):
        n = 0
        for _ in range(4096):
            if n < 0:
                contents, cluster = struct.unpack_from('<ih', self.d, self.loff + (-1 - n) * 28)
                return contents & 0x39 == 0 and cluster >= 0   # not solid/lava/slime/water, inside the map
            plane, c0, c1 = struct.unpack_from('<iii', self.d, self.noff + n * 28)
            nx, ny, nz, dist = struct.unpack_from('<ffff', self.d, self.poff + plane * 20)
            n = c0 if nx * p[0] + ny * p[1] + nz * p[2] - dist >= 0 else c1
        return False

    def clear(self, a, b, steps=24):
        """all points along a..b (excluding the last 15%) are empty"""
        return all(self.empty([a[j] + (b[j] - a[j]) * t / steps for j in range(3)]) for t in range(int(steps * 0.85) + 1))


def candidates(c, n, dist):
    if abs(n[2]) > 0.7:     # floor: oblique views from four sides
        for dd in (dist, dist * 0.7, dist * 0.45):
            for ang in range(0, 360, 90):
                a = math.radians(ang)
                yield (c[0] + math.cos(a) * dd, c[1] + math.sin(a) * dd, c[2] + n[2] * dd * 0.8)
    else:
        for dd in (dist, dist * 0.7, dist * 0.45, dist * 0.25):
            yield (c[0] + n[0] * dd, c[1] + n[1] * dd, c[2] + n[2] * dd + 16.0)


def look(cam, target):
    d = [target[j] - cam[j] for j in range(3)]
    yaw = math.degrees(math.atan2(d[1], d[0]))
    pitch = -math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return pitch, yaw


def entities(path):
    data = open(path, 'rb').read()
    off, ln = lumps(data)[0]
    text = data[off:off + ln].decode('latin-1')
    return [dict(re.findall(r'"([^"]+)"\s+"([^"]*)"', block)) for block in re.findall(r'\{([^{}]*)\}', text)]


def spots(path, count):
    tree = Tree(path)
    pts = []
    for e in entities(path):
        if e.get('classname') in ('info_player_start', 'path_corner') and 'origin' in e:
            x, y, z = (float(v) for v in e['origin'].split()[:3])
            for dz in (40.0, 24.0, 56.0):
                if tree.empty((x, y, z + dz)):
                    pts.append((x, y, z + dz)); break
    starts, vis = spawn_vis(path, tree)
    if vis is not None:
        pts = [q for q in pts if tree.leaf(q)[1] in vis]
    # at the spawn the camera is inside the player model, which Remix renders as a black frame
    pts = [q for q in pts if all(math.dist(q, s) > 96 for s in starts)]
    picked = []
    while pts and len(picked) < count:
        best = max(pts, key=lambda p: min((math.dist(p, q) for q in picked), default=1e9))
        pts.remove(best)
        if picked and min(math.dist(best, q) for q in picked) < 256:
            break
        picked.append(best)
    out = []
    for cam in picked:
        def reach(a):
            far = 0
            for d in range(32, 1025, 32):
                if not tree.empty((cam[0] + math.cos(a) * d, cam[1] + math.sin(a) * d, cam[2])):
                    break
                far = d
            return far
        a = max((math.radians(k * 22.5) for k in range(16)), key=reach)
        out.append((cam, 10.0, math.degrees(a)))
    return out


def spawn_vis(path, tree):
    """(spawn points, clusters in their PVS or None): the info_player_start the game uses (the one without
    targetname, else the first). The engine only draws what the player can see from there."""
    starts = []; first = None
    for e in entities(path):
        if e.get('classname') == 'info_player_start' and 'origin' in e:
            x, y, z = (float(v) for v in e['origin'].split()[:3])
            for dz in (40.0, 24.0, 56.0):
                if tree.empty((x, y, z + dz)):
                    first = first or (x, y, z + dz)
                    if 'targetname' not in e:
                        starts.append((x, y, z + dz))
                    break
    starts = starts or ([first] if first else [])
    return starts, (set().union(*(tree.pvs(tree.leaf(q)[1]) for q in starts)) if starts else None)


def entity_views(path, classes, count, dist):
    """views of placed entities (classname match) inside the spawn's PVS, from eye height around each one"""
    tree = Tree(path)
    starts, vis = spawn_vis(path, tree)
    out = []
    for e in entities(path):
        c = e.get('classname', '').lower()
        if c not in classes or 'origin' not in e or len(out) >= count:
            continue
        o = tuple(float(v) for v in e['origin'].split()[:3])
        if any(math.dist(o, q) < 256 for _, q, _ in out):
            continue
        target = (o[0], o[1], o[2] + 24)
        for dd in (dist, dist * 0.7, dist * 1.5, dist * 0.45):
            for ang in range(0, 360, 45):
                a = math.radians(ang)
                cam = (o[0] + math.cos(a) * dd, o[1] + math.sin(a) * dd, o[2] + 48)
                if not tree.empty(cam) or not tree.clear(cam, target):
                    continue
                if vis is not None and tree.leaf(cam)[1] not in vis:
                    continue
                if any(math.dist(cam, q) < 96 for q in starts):
                    continue
                out.append((c, o, cam)); break
            if out and out[-1][1] == o:
                break
    return [(c, cam) + look(cam, (o[0], o[1], o[2] + 24)) for c, o, cam in out]


def sky_views(path, count):
    """views from player/NPC spots towards the direction where the most traced rays end on a SURF_SKY face"""
    tree = Tree(path)
    sky = []
    for area, name, c, n, pts in faces_with(path, [], flags=0x4, points=True):
        lo = [min(q[j] for q in pts) - 12 for j in range(3)]; hi = [max(q[j] for q in pts) + 12 for j in range(3)]
        sky.append((n, sum(n[j] * c[j] for j in range(3)), lo, hi))
    def hits_sky(cam, pitch, yaw):
        p, y = math.radians(pitch), math.radians(yaw)
        d = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p))
        last = cam
        for t in range(16, 4097, 16):
            q = [cam[j] + d[j] * t for j in range(3)]
            if not tree.empty(q):
                if vis is not None and tree.leaf(last)[1] not in vis:
                    return False
                return any(abs(sum(n[j] * q[j] for j in range(3)) - dist) < 12 and
                           all(lo[j] <= q[j] <= hi[j] for j in range(3)) for n, dist, lo, hi in sky)
            last = q
        return False
    pts = []
    for e in entities(path):
        if e.get('classname') in ('info_player_start', 'path_corner') and 'origin' in e:
            x, y, z = (float(v) for v in e['origin'].split()[:3])
            for dz in (40.0, 24.0, 56.0):
                if tree.empty((x, y, z + dz)):
                    pts.append((x, y, z + dz)); break
    starts, vis = spawn_vis(path, tree)
    if vis is not None:
        pts = [q for q in pts if tree.leaf(q)[1] in vis]
    # at the spawn the camera is inside the player model, which Remix renders as a black frame
    pts = [q for q in pts if all(math.dist(q, s) > 96 for s in starts)]
    spread = []
    while pts and len(spread) < 64:
        best = max(pts, key=lambda p: min((math.dist(p, q) for q in spread), default=1e9))
        pts.remove(best)
        if spread and min(math.dist(best, q) for q in spread) < 128:
            break
        spread.append(best)
    pitches = (0.0, -15.0, -30.0)
    scored = []
    for cam in spread:
        h = {(p, k): hits_sky(cam, p, k * 22.5) for p in pitches for k in range(16)}
        def score(p, k):
            return sum(h[(pp, (k + dk) % 16)] for pp in pitches if abs(pp - p) <= 15 for dk in (-1, 0, 1))
        p, k = max(((p, k) for p in pitches for k in range(16)), key=lambda pk: score(*pk))
        if score(p, k):
            scored.append((score(p, k), cam, p, k * 22.5))
    out = []
    for s, cam, p, yw in sorted(scored, key=lambda r: -r[0]):
        if len(out) < count and all(math.dist(cam, q) >= 512 for q, _, _ in out):
            out.append((cam, p, yw if yw <= 180 else yw - 360))
    return out


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    count = int(opt('--count', '1')); dist = float(opt('--distance', '140')); prefix = opt('--name', '')
    light = opt('--light', ''); nspots = int(opt('--spots', '0')); nsky = int(opt('--sky', '0'))
    ents = opt('--entity', '')
    if ents and args:
        mp = os.path.splitext(os.path.basename(args[0]))[0].lower()
        res = entity_views(args[0], set(ents.lower().split(',')), count, float(opt('--distance', '0') or 0) or dist)
        for i, (c, cam, p, yw) in enumerate(res):
            print('%s %s%s_%d %.1f %.1f %.1f %.1f %.1f' % (mp, prefix, c, i, cam[0], cam[1], cam[2], p, yw))
        if not res:
            sys.exit('%s: no view of %s inside the spawn PVS' % (mp, ents))
        return
    if nsky and args:
        mp = os.path.splitext(os.path.basename(args[0]))[0].lower()
        res = sky_views(args[0], nsky)
        for i, (cam, p, yw) in enumerate(res):
            print('%s %ssky%d %.1f %.1f %.1f %.1f %.1f' % (mp, prefix, i, cam[0], cam[1], cam[2], p, yw))
        if not res:
            sys.exit('%s: no sky visible from player start or path_corner' % mp)
        return
    if nspots and args:
        mp = os.path.splitext(os.path.basename(args[0]))[0].lower()
        res = spots(args[0], nspots)
        for i, (cam, p, yw) in enumerate(res):
            print('%s %sspot%d %.1f %.1f %.1f %.1f %.1f' % (mp, prefix, i, cam[0], cam[1], cam[2], p, yw))
        if not res:
            sys.exit('%s: no player start or path_corner inside the map' % mp)
        return
    if len(args) < 1 or (not light and len(args) < 2):
        print(__doc__); sys.exit(1)
    mp = os.path.splitext(os.path.basename(args[0]))[0].lower()
    if light:
        idx = int(light)
        lf = os.path.join(os.path.dirname(args[0]), mp + '.lights')
        if not os.path.exists(lf):
            sys.exit('give the .lights file next to the BSP, or use a texture')
        rows = [l.split() for l in open(lf) if l.strip() and l.split()[0] not in ('#', 'format', 'sun')
                and not l.startswith('#')]
        x, y, z = (float(v) for v in rows[idx][:3])
        cam = (x - dist * 0.7, y - dist * 0.7, z - dist * 0.3)
        p, yw = look(cam, (x, y, z))
        print('%s %slight%d %.1f %.1f %.1f %.1f %.1f' % (mp, prefix, idx, cam[0], cam[1], cam[2], p, yw))
        return
    wanted = [w.lower() for w in args[1].split(',')]
    tree = Tree(args[0])
    faces = {}
    for area, name, c, n in faces_with(args[0], wanted):
        if n[2] < -0.7:       # ceilings: looking up from below is rarely useful
            continue
        faces.setdefault(name, []).append((area, c, n))
    printed = 0; skipped = []
    for name, lst in sorted(faces.items(), key=lambda kv: -max(f[0] for f in kv[1])):
        if printed >= count:
            break
        found = None
        for area, c, n in sorted(lst, key=lambda f: -f[0])[:12]:
            for cam in candidates(c, n, dist):
                if tree.empty(cam) and tree.clear(cam, c):
                    found = (cam, c); break
            if found:
                break
        if not found:
            skipped.append(name); continue
        cam, c = found
        p, yw = look(cam, c)
        print('%s %s%s %.1f %.1f %.1f %.1f %.1f' % (mp, prefix, name.split('/')[-1], cam[0], cam[1], cam[2], p, yw))
        printed += 1
    if skipped:
        print('%s: no clear view for %s' % (mp, ', '.join(skipped)), file=sys.stderr)
    if not printed:
        sys.exit('%s: no usable view for %s' % (mp, ','.join(wanted)))


if __name__ == '__main__':
    main()
