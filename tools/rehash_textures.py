#!/usr/bin/env python3
"""Map RTX Remix texture hashes from the original Anachronox textures to a replacement texture pack,
and rewrite config/USD files to the new hashes.

usage: rehash_textures.py map ORIG_TEXTURES.dat PACK_TEXTURE_DIR OUT_MAP.tsv
       rehash_textures.py apply MAP.tsv FILE...        (rtx.conf, mod.usda, liquids.usda, ...)
       rehash_textures.py add MAP.tsv FILE... [--only HASHES.tsv]

`map`: for every image in the original archive, compute its Remix hash (see remixhash.py) and the hash of
the pack's file with the same path (any extension, e.g. .png) -> TSV: old_hash new_hash path.
`apply`: replace 0xOLD (rtx.conf lists) and mat_OLD (USD material overrides) with the new hash, in place,
keeping a .bak copy. Animated (.atd) and runtime-generated textures have no fixed hash and are skipped.
`add MAP.tsv FILE... [--only HASHES.tsv]`: keep the old hashes and add the new ones: rtx.conf lists get every new
hash of a listed old one (identical originals can map to several pack files), USD `over "mat_OLD"` blocks are
copied once per new hash. Safe to run twice and when a new hash equals an unrelated old one. --only limits it to
the old hashes at the start of the lines of HASHES.tsv (e.g. maps/posters_flux.tsv).
Example (Chuncki's 4x pack): map anoxdata/TEXTURES.dat.orig anoxdata/textures map.tsv
"""
import glob, importlib.util, io, os, re, shutil, sys

here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
adat, rh = _load('adat'), _load('remixhash')


def cmd_map(dat, packdir, out):
    pack = {}
    for p in glob.glob(os.path.join(packdir, '**', '*'), recursive=True):
        if os.path.isfile(p):
            rel = os.path.relpath(p, packdir).replace('\\', '/').lower()
            pack.setdefault(os.path.splitext(rel)[0], p)
    rows, skipped = [], 0
    with open(dat, 'rb') as f:
        for name, o, n, c in adat.entries(dat):
            key = os.path.splitext(name.replace('\\', '/').lower())[0]
            if name.lower().endswith(('.atd', '.dat')) or key not in pack:
                skipped += 1; continue
            try:
                old, _ = rh.remix_hash(io.BytesIO(adat.read(f, o, n, c)))
                new, _ = rh.remix_hash(pack[key])
            except Exception:
                skipped += 1; continue
            rows.append('0x%016X\t0x%016X\t%s' % (old, new, key))
    open(out, 'w').write('\n'.join(rows) + '\n')
    print('%d textures mapped, %d skipped -> %s' % (len(rows), skipped, out))


def cmd_apply(mapfile, files):
    m = {}
    for l in open(mapfile):
        p = l.split('\t')
        if len(p) >= 2:
            m[int(p[0], 16)] = int(p[1], 16)
    for path in files:
        s = open(path, encoding='latin-1').read(); n = [0]
        def hexrep(mo):
            h = int(mo.group(2), 16)
            if h in m:
                n[0] += 1
                return mo.group(1) + '%016X' % m[h]
            return mo.group(0)
        s2 = re.sub(r'(0x)([0-9A-Fa-f]{1,16})\b', hexrep, s)
        s2 = re.sub(r'(mat_)([0-9A-Fa-f]{16})\b', hexrep, s2)
        if n[0]:
            shutil.copy(path, path + '.bak')
            open(path, 'w', encoding='latin-1').write(s2)
        print('%s: %d hashes rewritten' % (path, n[0]))


def cmd_add(mapfile, files, only=None):
    m = {}
    for l in open(mapfile):
        p = l.split('\t')
        if len(p) >= 2 and not l.startswith('#'):
            o, n = int(p[0], 16), int(p[1], 16)
            if o != n and (only is None or o in only):
                m.setdefault(o, [])
                if n not in m[o]:
                    m[o].append(n)
    for path in files:
        lines = open(path, encoding='latin-1').read().split('\n'); out = []; n = 0
        if path.endswith('.usda'):
            have = set(int(h, 16) for h in re.findall(r'over "mat_([0-9A-Fa-f]{16})"', '\n'.join(lines)))
            i = 0
            while i < len(lines):
                mo = re.match(r'^(\s*)over "mat_([0-9A-Fa-f]{16})"\s*$', lines[i])
                if not mo or int(mo.group(2), 16) not in m:
                    out.append(lines[i]); i += 1; continue
                ind = mo.group(1); j = i + 1
                while j < len(lines) and lines[j] != ind + '}':
                    j += 1
                block = lines[i:j + 1]; out += block
                for h in m[int(mo.group(2), 16)]:
                    if h not in have:
                        have.add(h); n += 1
                        out += [block[0].replace(mo.group(2), '%016X' % h)] + block[1:]
                i = j + 1
        else:
            for l in lines:
                mo = re.match(r'^(\s*rtx\.\w+(?:\.\w+)*\s*=\s*)(.*)$', l)
                if mo and re.fullmatch(r'\s*0x[0-9A-Fa-f]{1,16}(\s*,\s*0x[0-9A-Fa-f]{1,16})*\s*,?\s*', mo.group(2)):
                    hs = [int(h, 16) for h in re.findall(r'0x([0-9A-Fa-f]{1,16})', mo.group(2))]
                    new = [x for h in hs for x in m.get(h, []) if x not in hs]
                    new = list(dict.fromkeys(new))
                    if new:
                        n += len(new)
                        l = l.rstrip().rstrip(',') + ''.join(', 0x%016X' % h for h in new)
                out.append(l)
        if n:
            shutil.copy(path, path + '.bak')
            open(path, 'w', encoding='latin-1').write('\n'.join(out))
        print('%s: %d hashes added' % (path, n))


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == 'map':
        cmd_map(*sys.argv[2:5])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'apply':
        cmd_apply(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'add':
        a = sys.argv[3:]; only = None
        if '--only' in a:
            k = a.index('--only'); only = set(int(h, 16) for h in re.findall(r'^0x([0-9A-Fa-f]{16})',
                                                                              open(a[k + 1]).read(), re.M))
            del a[k:k + 2]
        cmd_add(sys.argv[2], a, only)
    else:
        print(__doc__); sys.exit(1)
