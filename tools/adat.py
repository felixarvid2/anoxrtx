#!/usr/bin/env python3
"""List / extract Anachronox ADAT archives (anoxdata/*.dat, version 9).

Format (from hogsy/chronon qcommon/files.cpp):
  header: char magic[4] = "ADAT", uint32 tableOffset, uint32 tableLength, uint32 version (9)
  table:  tableLength / 144 entries of
          char name[128], uint32 offset, uint32 length (uncompressed),
          uint32 compressedLength (0 = stored), uint32 unknown
  data:   zlib streams (or raw when compressedLength is 0)

usage: adat.py list ARCHIVE.dat [PATTERN]
       adat.py extract ARCHIVE.dat OUTDIR [PATTERN]     (PATTERN is a shell glob, e.g. '*.bsp')
"""
import fnmatch, os, struct, sys, zlib


def entries(path):
    with open(path, 'rb') as f:
        magic, off, size, ver = struct.unpack('<4sIII', f.read(16))
        if magic != b'ADAT':
            raise SystemExit('%s: not an ADAT archive' % path)
        f.seek(off)
        table = f.read(size)
    for i in range(0, len(table) - 143, 144):
        name, o, n, c, _ = struct.unpack_from('<128sIIII', table, i)
        yield name.split(b'\0', 1)[0].decode('latin-1'), o, n, c


def read(f, o, n, c):
    f.seek(o)
    if c == 0:
        return f.read(n)
    data = zlib.decompress(f.read(c))
    if len(data) != n:
        raise ValueError('size mismatch')
    return data


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, arc = sys.argv[1], sys.argv[2]
    if cmd == 'list':
        pat = sys.argv[3] if len(sys.argv) > 3 else '*'
        for name, o, n, c in entries(arc):
            if fnmatch.fnmatch(name.lower(), pat.lower()):
                print('%10d %10d  %s' % (n, c, name))
    elif cmd == 'extract':
        out = sys.argv[3]; pat = sys.argv[4] if len(sys.argv) > 4 else '*'
        with open(arc, 'rb') as f:
            for name, o, n, c in entries(arc):
                if not fnmatch.fnmatch(name.lower(), pat.lower()):
                    continue
                dst = os.path.normpath(os.path.join(out, name.replace('\\', '/').lstrip('/')))
                if not dst.startswith(os.path.normpath(out) + os.sep):
                    continue  # refuse paths escaping OUTDIR
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as g:
                    g.write(read(f, o, n, c))
                print(name)
    else:
        print(__doc__); sys.exit(1)


if __name__ == '__main__':
    main()
