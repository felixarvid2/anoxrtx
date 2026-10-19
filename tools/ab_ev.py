#!/usr/bin/env -S sh -c 'exec "${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}" "$0" "$@"'
"""Exposure difference per view of an `anoxcheck.py --ab-original` run, with the original's gamma corrected.

usage: ab_ev.py CHECKDIR [--gamma 1.4]

The original renderer (Wine D3D9, Remix' d3d9.dll moved aside) does not apply the game's hardware gamma
(`u_gl_gamma 1.4`), so its shots are corrected with v' = v^(1/gamma) before comparing mean linear luminance.
EV = log2(original / Remix); negative = Remix brighter. The top 40 rows (Remix welcome overlay) are ignored.
Per view it also prints the black fraction of each shot and how much the Remix shot changed between the two
captures ("settle", EV), plus FAIL if anoxcheck's report marked the view. A view is usable only when neither
shot is mostly black and settle is small; check the compare_*.png before trusting a number.
"""
import glob, os, re, sys
import numpy as np
from PIL import Image


def lum(path, gamma=1.0):
    a = np.asarray(Image.open(path).convert('RGB'), dtype=np.float32)[40:] / 255.0
    if gamma != 1.0:
        a = a ** (1 / gamma)
    l = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    y = 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
    return float(y.mean()), float((a.max(-1) < 0.02).mean())


def main():
    args = sys.argv[1:]
    gamma = 1.4
    if '--gamma' in args:
        i = args.index('--gamma'); gamma = float(args[i + 1]); del args[i:i + 2]
    if len(args) != 1:
        print(__doc__); sys.exit(1)
    d = args[0]
    rep = open(os.path.join(d, 'report.md')).read() if os.path.exists(os.path.join(d, 'report.md')) else ''
    fails = set(re.findall(r'^\| (\S+) \| FAIL', rep, re.M))
    for on in sorted(glob.glob(os.path.join(d, 'on-*_b.png'))):
        view = os.path.basename(on)[3:-6]
        off = os.path.join(d, 'off-%s_b.png' % view); on_a = os.path.join(d, 'on-%s_a.png' % view)
        if not os.path.exists(off):
            continue
        lo, black_on = lum(on); lf, black_off = lum(off, gamma); la, _ = lum(on_a)
        settle = abs(np.log2((la + 1e-6) / (lo + 1e-6)))
        ev = np.log2((lf + 1e-6) / (lo + 1e-6))
        print('%-22s ev %+6.2f  on %.4f off %.4f  black on %.2f off %.2f settle %.2f %s'
              % (view, ev, lo, lf, black_on, black_off, settle, 'FAIL' if view in fails else ''))


if __name__ == '__main__':
    main()
