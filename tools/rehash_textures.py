#!/usr/bin/env python3
"""Map RTX Remix texture hashes from the original Anachronox textures to a replacement texture pack,
and rewrite config/USD files to the new hashes.

usage: rehash_textures.py map ORIG_TEXTURES.dat PACK_TEXTURE_DIR OUT_MAP.tsv
       rehash_textures.py apply MAP.tsv FILE...        (rtx.conf, mod.usda, liquids.usda, ...)

`map`: for every image in the original archive, compute its Remix hash (see remixhash.py) and the hash of
the pack's file with the same path (any extension, e.g. .png) -> TSV: old_hash new_hash path.
`apply`: replace 0xOLD (rtx.conf lists) and mat_OLD (USD material overrides) with the new hash, in place,
keeping a .bak copy. Animated (.atd) and runtime-generated textures have no fixed hash and are skipped.
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


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == 'map':
        cmd_map(*sys.argv[2:5])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'apply':
        cmd_apply(sys.argv[2], sys.argv[3:])
    else:
        print(__doc__); sys.exit(1)
