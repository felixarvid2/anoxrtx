#!/bin/bash
# Switch Anachronox between RTX Remix (QindieGL + Remix) and the plain game, by renaming QindieGL's
# opengl32.dll and Remix' d3d9.dll (Wine then uses its own). usage: toggle.sh [on|off|status] [GAMEDIR]
mode="${1:-status}"
game="${2:-}"
if [ -z "$game" ]; then
    for r in ~/.steam/steam ~/.steam/debian-installation ~/.local/share/Steam; do
        [ -f "$r/steamapps/common/Anachronox/anox.exe" ] && game="$r/steamapps/common/Anachronox" && break
    done
fi
[ -f "$game/anox.exe" ] || { echo "Anachronox not found; usage: toggle.sh on|off|status GAMEDIR"; exit 1; }
cd "$game"
case "$mode" in
    off) for f in opengl32.dll d3d9.dll; do [ -f "$f" ] && mv "$f" "$f.off"; done; echo "RTX Remix off" ;;
    on)  for f in opengl32.dll d3d9.dll; do [ -f "$f.off" ] && mv "$f.off" "$f"; done; echo "RTX Remix on" ;;
    *)   if [ -f opengl32.dll ] && [ -f d3d9.dll ]; then echo "RTX Remix is on"; else echo "RTX Remix is off"; fi ;;
esac
