#!/usr/bin/env python3
"""Give the upscaled pack textures the corrected alpha channel of a fix mod's same-size originals.

usage: merge_alpha.py PACK_TEXTURE_DIR FIX_TEXTURE_DIR MAP.tsv

Graphical Enhancements 0.3 ships 12 level textures (bricks/01comp, 02comp, sexmachine bottles and glasses) at the
original size with only the alpha changed: the original's grey, see-through alpha becomes a solid cutout. Chuncki's
4x pack keeps the old alpha. For every image in FIX_TEXTURE_DIR whose path (any extension) exists in
PACK_TEXTURE_DIR, the pack image keeps its colour and gets the fix's alpha, scaled up bilinearly with crisp edges
(0..64 -> 0, 192..255 -> 255). The pack file is rewritten in place (same format, made writable); the original is
kept as FILE.orig the first time. MAP.tsv gets "0xOLD<TAB>0xNEW<TAB>path" rows (Remix hashes, see remixhash.py) for rehash_textures.py add;
existing rows are kept, so a second run (old == new) changes nothing.
"""
import glob, importlib.util, os, shutil, sys

import numpy as np
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('remixhash', os.path.join(here, 'remixhash.py'))
rh = importlib.util.module_from_spec(spec); spec.loader.exec_module(rh)


def main():
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    pack, fix, mapfile = sys.argv[1:]
    packfiles = {}
    for p in glob.glob(os.path.join(pack, '**', '*.*'), recursive=True):
        if not p.endswith('.orig'):
            packfiles[os.path.splitext(os.path.relpath(p, pack).replace('\\', '/').lower())[0]] = p
    rows = [l.rstrip('\n') for l in open(mapfile)] if os.path.exists(mapfile) else []
    n = 0
    for f in sorted(glob.glob(os.path.join(fix, '**', '*.*'), recursive=True)):
        key = os.path.splitext(os.path.relpath(f, fix).replace('\\', '/').lower())[0]
        if key not in packfiles or f.lower().endswith('.dat'):
            continue
        dst = packfiles[key]
        old, _ = rh.remix_hash(dst)
        if not os.path.exists(dst + '.orig'):
            shutil.copy2(dst, dst + '.orig')
        col = Image.open(dst + '.orig').convert('RGBA')
        a = Image.open(f).convert('RGBA').getchannel('A').resize(col.size, Image.BILINEAR)
        a = np.clip((np.asarray(a, dtype=np.float32) - 64) * (255.0 / 128), 0, 255).astype(np.uint8)
        col.putalpha(Image.fromarray(a, 'L'))
        os.chmod(dst, os.stat(dst).st_mode | 0o200)
        col.save(dst)
        new, _ = rh.remix_hash(dst)
        if old != new:
            rows.append('0x%016X\t0x%016X\t%s' % (old, new, key)); n += 1
    open(mapfile, 'w').write('\n'.join(r for r in rows if r) + '\n')
    print('%d pack textures given the fix alpha -> %s' % (n, mapfile))


if __name__ == '__main__':
    main()
