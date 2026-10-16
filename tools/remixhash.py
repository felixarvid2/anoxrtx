#!/usr/bin/env python3
"""Compute the RTX Remix texture hash of game image files, as seen through QindieGL.

usage: remixhash.py IMAGE...          prints  HASH  WIDTHxHEIGHT  path

Remix (dxvk-remix 1.5.2, d3d9_common_texture.cpp) hashes a texture as XXH3_64 over mip 0 of the D3D9
texture. QindieGL uploads 24-bit images as X8R8G8B8 and 32-bit images as A8R8G8B8, i.e. bytes
B,G,R,A per pixel with A = 255 when the image has no alpha. Verified against QindieGL's DumpTextures
output and against hashes in vinevi1's rtx.conf (e.g. sky\\spacebk.tga -> 0x0B4482A4B3668073).

Only valid when the game uploads the image unchanged (same size, no palette, no runtime generation).
Needs: pip install pillow xxhash
"""
import sys
import xxhash
from PIL import Image


def remix_hash(path):
    im = Image.open(path)
    has_alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
    im = im.convert('RGBA')
    if not has_alpha:
        im.putalpha(255)
    r, g, b, a = im.split()
    bgra = Image.merge('RGBA', (b, g, r, a)).tobytes()
    return xxhash.xxh3_64_intdigest(bgra), im.size


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for p in sys.argv[1:]:
        try:
            h, (w, hh) = remix_hash(p)
            print('0x%016X  %dx%d  %s' % (h, w, hh, p))
        except Exception as e:  # unreadable image
            print('ERROR %s: %s' % (p, e), file=sys.stderr)


if __name__ == '__main__':
    main()
