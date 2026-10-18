#!/bin/bash
# Run a game test in the nested rig session and always restore the desktop setup afterwards.
#
# usage: tools/rigsession.sh [--map NAME] [--keep-steam-off] SCRIPT [ARGS...]
#
# Sets up: Xwayland :7 (1920x1200), Steam shut down, "DISPLAY=:7 " prefixed to the game's launch options
# (and " +map NAME" after %command% with --map). Then runs SCRIPT (bash) with these variables exported:
#   RIG   - command prefix for tools/anoxrig.py ("$RIG start", "$RIG shot name", ...)
#   GAME  - game folder        LOGS - $GAME/rtx-remix/logs       QLOG - $GAME/QindieGL.log
# On exit (also on failure or Ctrl+C): stops the game, shuts Steam down, removes DISPLAY=:7 and +map from the
# launch options, kills the :7 Xwayland it started, restarts Steam on the desktop (unless --keep-steam-off).
# Prints "rigsession: restored" at the end; check that line in logs.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
map=""; keep_off=0
while [ $# -gt 0 ]; do
    case "$1" in
        --map) map="$2"; shift 2 ;;
        --keep-steam-off) keep_off=1; shift ;;
        -h|--help) sed -n 2,13p "$0"; exit 0 ;;
        *) break ;;
    esac
done
[ $# -ge 1 ] || { sed -n 2,13p "$0"; exit 1; }
script="$1"; shift

GAME="${ANOX_GAME:-$HOME/.steam/debian-installation/steamapps/common/Anachronox}"
PY="${ANOX_PY:-$HOME/.cache/anoxrtx/venv/bin/python}"
[ -x "$PY" ] || PY=python3
RIG="$PY -W ignore $here/anoxrig.py"
LOGS="$GAME/rtx-remix/logs"; QLOG="$GAME/QindieGL.log"
export GAME RIG LOGS QLOG ANOX_DISPLAY=:7
VDF=$(ls "$HOME"/.steam/debian-installation/userdata/*/config/localconfig.vdf 2>/dev/null | head -1)
[ -f "$VDF" ] || { echo "rigsession: localconfig.vdf not found"; exit 1; }

xw_pid() { for p in $(pgrep -x Xwayland); do tr '\0' ' ' < /proc/$p/cmdline | grep -q ' :7 ' && echo $p; done; }
steam_down() { steam -shutdown >/dev/null 2>&1; for _ in $(seq 1 30); do pgrep -x steam >/dev/null || return 0; sleep 2; done; }
started_xw=""

restore() {
    trap - EXIT INT TERM
    $RIG stop >/dev/null 2>&1
    steam_down
    sed -i 's|%command% +map [A-Za-z0-9_-]*|%command%|; s|"LaunchOptions"\t\t"DISPLAY=:7 |"LaunchOptions"\t\t"|' "$VDF"
    [ -n "$started_xw" ] && kill "$started_xw" 2>/dev/null
    [ $keep_off = 1 ] || (cd "$HOME" && DISPLAY="${DESKTOP_DISPLAY:-:1}" nohup steam -silent >/dev/null 2>&1 &)
    if grep -q 'DISPLAY=:7\|+map ' "$VDF"; then echo "rigsession: WARNING launch options not fully restored"; fi
    echo "rigsession: restored"
}
trap restore EXIT
trap 'exit 130' INT TERM

if [ -z "$(xw_pid)" ]; then
    setsid Xwayland :7 -geometry 1920x1200 -decorate -noreset >/dev/null 2>&1 < /dev/null &
    sleep 2; started_xw=$(xw_pid)
fi
steam_down
sed -i 's|"LaunchOptions"\t\t"__NV_PRIME|"LaunchOptions"\t\t"DISPLAY=:7 __NV_PRIME|' "$VDF"
[ -n "$map" ] && sed -i "s|%command%\\(\"\\)|%command% +map $map\\1|; s|%command% +map [A-Za-z0-9_-]* +map|%command% +map|" "$VDF"
grep -q 'DISPLAY=:7' "$VDF" || { echo "rigsession: could not set launch options"; exit 1; }
echo "rigsession: session ready (map: ${map:-none})"
cd "$HOME" && bash "$script" "$@"
