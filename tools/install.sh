#!/bin/bash
# Anachronox RTX Remix installer for Linux: creates a Python environment in ~/.cache/anoxrtx/venv
# (Pillow, numpy, xxhash, usd-core, python-xlib) and runs tools/install.py. See tools/install.sh --help.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
venv="${ANOXRTX_VENV:-$HOME/.cache/anoxrtx/venv}"
if [ ! -x "$venv/bin/python" ]; then
    echo "[anoxrtx] creating Python environment in $venv"
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q --upgrade pip
    "$venv/bin/pip" install -q pillow numpy xxhash usd-core python-xlib
fi
exec "$venv/bin/python" "$here/install.py" "$@"
