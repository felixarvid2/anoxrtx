---
name: anox-game-test
description: Run Anachronox under RTX Remix in the nested test session and collect evidence (screenshots, QindieGL/Remix logs). Use whenever a change must be checked in the running game, a map/save must be loaded, or Remix settings/QindieGL builds need an in-game test.
---

# Testing in the game (anoxrtx rig)

Everything runs through `tools/rigsession.sh`, which prepares the nested display and Steam, runs your test
script, and **always** restores the owner's desktop setup (launch options, Steam, Xwayland) – also on failure.
Never edit Steam's `localconfig.vdf` or start Xwayland by hand.

## Steps

1. Preconditions: game not running; ComfyUI not running (8 GB GPU / 14 GB RAM); new QindieGL DLL or configs
   installed into the game folder with a backup of what they replace.
2. Write a short bash test script (scratchpad). It gets `$RIG` (anoxrig.py), `$GAME`, `$LOGS`, `$QLOG`:
   ```bash
   $RIG start                      # launches via Steam, waits for visible content
   sleep 40                        # with +map: let the map load
   $RIG shot my_check              # -> tools/shots/my_check.png (+ prints brightness)
   grep -aE "MapLights|DLights|ProcTex|RTX.conf|Remix API" "$QLOG" | tail -20   # -a: binary bytes in the log
   echo "remix crash: $(grep -c 'err:   The RTX' "$LOGS/bridge32.log")"
   ```
   Other rig commands: `console TEXT` (one console line from the menu, e.g. `console map servicetunnel`;
   retries while the intro is still up), `load-save SLOT`, `to-rowdys`, `timeline PFX T...`, `hold SECS KEY`, `key`, `chord`,
   `sendkey` (reaches Remix), `move`, `click`, `log`, `list-saves`. Saved test views: `docs/test-locations.md`.
3. Run it in the background (a full run takes 2–6 min):
   `tools/rigsession.sh [--map NAME] /path/to/test.sh > log 2>&1`
   `--map NAME` starts straight into a map (`+map`); some maps (whitecaves-*) need a save instead. To load
   from the menu like a player: start without `--map` and use `$RIG console map NAME`.
4. Check the log ends with `rigsession: restored` (no WARNING), then look at the screenshots. Compare views
   with `tools/anoxcapture.py` / `tools/anoxcompare.py` (docs/screenshot-regression.md) when a baseline exists.

## Evidence to report
Map/save, runtime (stock Remix 1.5.2 or Remix Plus 1.5.1), changed settings, screenshot paths, the relevant
QindieGL.log lines, and whether Remix crashed. A rig "timeout" alone does not prove a crash; a crash shows as
"The RTX Remix Runtime has encountered an unexpected issue" in `bridge32.log`. A stall (not a crash) shows as `Data Queue overwrite` in `bridge32.log` without a following "resolved"; that
is the bridge deadlock fixed by `clientChannelMemSize = 201326592` in `.trex/bridge.conf`.
For brightness comparisons with the original renderer use the `anox-ab-measure` skill. Known problems and fixes:
docs/TROUBLESHOOTING.md.
