#!/usr/bin/env python3
"""List the map lights nearest a position, with the index used in <map>.override files.

usage: lights_near.py MAP.lights X Y Z [COUNT]

The index counts the light lines of the .lights file from 0 (comments, `format` and `sun` lines are not
counted), the same way QindieGL does. Get X Y Z in the game: save <map>.override or anox_customise.ini while
standing at the spot; QindieGL.log then shows "MapLights: camera at X Y Z" (needs dlights = 1, which hooks
the view).

<map>.override (next to the .lights file, reloaded while playing), one change per line:
    N off                 remove light N
    N scale S             multiply its strength
    N color R G B         new colour (0..1)
    N move DX DY DZ       move it (game units)
    N radius R            sphere radius
    sun off | sun scale S
    add X Y Z R G B LIGHT RADIUS [DX DY DZ CONE] [style N]     a new light, same format as the .lights file
"""
import math, sys


def lights(path):
    i = 0
    for line in open(path):
        t = line.split()
        if not t or t[0].startswith('#') or t[0] in ('format', 'sun'):
            continue
        try:
            xyz = [float(v) for v in t[:3]]
        except ValueError:
            continue
        yield i, xyz, line.rstrip()
        i += 1


def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(1)
    p = [float(v) for v in sys.argv[2:5]]
    count = int(sys.argv[5]) if len(sys.argv) > 5 else 10
    near = sorted((math.dist(p, xyz), i, line) for i, xyz, line in lights(sys.argv[1]))
    for d, i, line in near[:count]:
        print('%4d  %6.0f  %s' % (i, d, line))


if __name__ == '__main__':
    main()
