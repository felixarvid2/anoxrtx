#!/usr/bin/env -S sh -c 'exec "${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}" "$0" "$@"'
"""Which particle textures the game's particle definitions (*.apd) use, how they blend, and how rtx.conf tags them.

usage: apd_textures.py DIR [--conf rtx.conf]

DIR holds the extracted anoxdata/particles folders (*.apd) and graphics/particles images (png/tga/pcx), in any
layout below it. Per generator texture it prints the Remix hash (remixhash.py, of the image file), its tag in
rtx.conf (P particle, B beam, I ignore, H hideInstance, - none) and how many generators draw it additively (the
engine's default, GL_SRC_ALPHA/GL_ONE) or alpha-blended (`genblend : 0x0302 : 0x0303`). Alpha-blended ones are
the candidates for QindieGL's additive_textures (see sunstrip in anox_customise.ini). A texture whose image was
not found gets hash "?". The hash is only right when the game uploads the image unchanged.
"""
import collections, glob, os, re, sys
from remixhash import remix_hash

TAGS = (('P', 'rtx.particleTextures'), ('B', 'rtx.beamTextures'), ('I', 'rtx.ignoreTextures'),
        ('H', 'rtx.hideInstanceTextures'))


def generators(path):
    """(texture name, alpha-blended) per generator of one .apd file"""
    gens = []
    for line in open(path, errors='replace'):
        f = [p.strip() for p in line.split('#')[0].split(':')]
        key = f[0].lower()
        if key == 'generator':
            gens.append([set(), False])
        elif gens and key == 'gentexture':
            gens[-1][0].add(re.sub(r'\.(png|tga|pcx)$', '', f[-1].replace('\\', '/').split('/')[-1].lower()))
        elif gens and key == 'genblend':
            gens[-1][1] = [v.lower() for v in f[1:3]] == ['0x0302', '0x0303']
    return [(t, alpha) for tex, alpha in gens for t in tex]


def main():
    args = sys.argv[1:]
    conf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rtx.conf')
    if '--conf' in args:
        i = args.index('--conf'); conf = args[i + 1]; del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    root = args[0]
    tagged = {}
    for line in open(conf):
        for tag, key in TAGS:
            if line.startswith(key + ' '):
                for h in re.findall(r'0x[0-9A-Fa-f]+', line):
                    tagged.setdefault(int(h, 16), set()).add(tag)
    images = {}
    for path in sorted(glob.glob(os.path.join(root, '**', '*.*'), recursive=True)):
        name, ext = os.path.splitext(os.path.basename(path))
        if ext.lower() in ('.png', '.tga', '.pcx'):
            images.setdefault(name.lower(), path)
    use = collections.defaultdict(lambda: [0, 0])
    for path in glob.glob(os.path.join(root, '**', '*.apd'), recursive=True):
        for tex, alpha in generators(path):
            use[tex][alpha] += 1
    print('%-22s %-18s %-4s %5s %5s' % ('texture', 'hash', 'tag', 'add', 'alpha'))
    for tex in sorted(use):
        h = remix_hash(images[tex])[0] if tex in images else None
        tag = ''.join(sorted(tagged.get(h, ()))) or '-'
        print('%-22s %-18s %-4s %5d %5d' % (tex, '0x%016X' % h if h is not None else '?', tag, *use[tex]))


if __name__ == '__main__':
    main()
