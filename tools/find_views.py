#!/usr/bin/env python3
"""Find camera views for the test rig from a map's BSP: look at the surfaces that use a texture.

usage: find_views.py MAP.bsp TEXTURE[,TEXTURE...] [--count N] [--distance D] [--name PREFIX]
       find_views.py MAP.bsp --light N [--distance D]          (view of map light N, index as in <map>.lights)
       find_views.py MAP.bsp --spots N                          (N views from places the player or NPCs go)

TEXTURE is a texture path as in the BSP (e.g. levant/proc_lava; substring match, case-insensitive). For the
largest faces that use it (one per texture, up to --count) the view is placed --distance units (default 140)
in front of the face along its normal, raised a little, looking at the face centre. Prints lines for
tools/anoxcheck.py --views:   MAP NAME X Y Z PITCH YAW
(QindieGL renders world views from rtx-remix/rigcam.txt "X Y Z PITCH YAW", Quake 2 angles: pitch > 0 = down.)
--spots picks eye-height views at info_player_start and path_corner entities, spread over the map (each next spot
the one farthest from those already picked), looking along the most open of 16 directions, slightly down; for
measuring a map as a whole (e.g. exposure) where the start view is unusable.
Camera positions are checked against the BSP tree: only empty leaves inside the map (cluster >= 0, no solid or
liquid contents) are used,
trying shorter distances and, for floors, oblique views from four sides.
"""
import math, os, re, struct, sys


def lumps(data):
    return [struct.unpack_from('<ii', data, 8 + 8 * i) for i in range(19)]


def faces_with(path, wanted):
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
        if not any(w in name for w in wanted):
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
        out.append((area, name, c, n))
    return out


class Tree:
    """point contents from the BSP nodes/leaves (Quake 2 dnode_t 28 bytes, dleaf_t 28 bytes)"""
    def __init__(self, path):
        d = open(path, 'rb').read(); L = lumps(d)
        self.d = d; self.poff = L[1][0]; self.noff = L[4][0]; self.loff = L[8][0]

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


def main():
    args = sys.argv[1:]
    def opt(n, default):
        if n in args:
            i = args.index(n); v = args[i + 1]; del args[i:i + 2]; return v
        return default
    count = int(opt('--count', '1')); dist = float(opt('--distance', '140')); prefix = opt('--name', '')
    light = opt('--light', ''); nspots = int(opt('--spots', '0'))
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
