# Repeatable save-based visual tests

Use the nested Xwayland setup in `HANDOFF.md`. The rig defaults to `:7`; keep the
game, runtime, output geometry, and active config files the same between runs.
Wait for the initial Remix material-loading overlay to finish. `start` confirms
visible content, not that a level is fully loaded.

## Select a local baseline

```sh
python tools/anoxrig.py list-saves
python tools/anoxrig.py load-save steamuser/1
```

Selectors name an existing profile and slot. The listing includes the save's
SHA-256 fingerprint so two different saves with the same slot/name are not
mistaken for the same baseline. Save files remain local and are not included in
the repository. The rig reads their gzip-compressed header; it supports the
installed Anachronox save format (header version 1004).

Loading replaces the current unsaved state. It does not save progress. The
command verifies a fresh console transcript for the requested save and reports
settled position and yaw after the scene has drawn. Failure exits nonzero.
The game's [editing documentation](https://anachrodox.talonbrave.info/appendix/console_commands.html)
describes the `loadgame`, `viewpos`, and `condump` commands used by the rig.
The game console must retain its default layout/gold build footer; customized
fonts or a different console key may need adjustment (`ANOX_CONSOLE_KEY`).
Console typing uses 80 ms key holds and 40 ms gaps: faster input dropped
characters during a loaded Rowdy's session. The timeout is a waiting budget,
not a hard wall-clock limit; typing and restoration can extend beyond it.
Those timings can still fail under load. The 2026-10-17 saved-view check needed
an isolated probe with held Backspace autorepeat and 120 ms key holds/gaps;
the tracked rig remains unchanged. Always require its fresh transcript checks.

## Location coverage

| Environment | Local baseline | Status |
| --- | --- | --- |
| Indoor lighting / materials | `steamuser/1`, `rowdys` | Verified repeated restores at `(1168, 1235, 336)`, yaw `9`, after movement between loads |
| Second indoor view | `steamuser/2`, `rowdys` | Verified at `(756, 1289, 8)`, yaw `11`; a distinct local Rowdy's view |
| Outdoor sky / sun shadows | A TimeMinder save in an outdoor area | Pending: the inspected saves contain only Rowdy's and intro scenes |
| Water / transparency | A TimeMinder save near water in Limbus | Pending: no corresponding local save found |
| Lava / procedural replacements | A TimeMinder save near the lava in Levant | Pending: no corresponding local save found |

`GLOBAL/1` and `GLOBAL/999` are intro saves in `sphere`; `GLOBAL/5` is a Rowdy's
cinematic. They are not substitutes for stationary gameplay views. Avoid using a
cinematic as a material/lighting baseline unless its timing is controlled.

The [fixed-wrapper lighting check](saved-view-lighting-check.md) verified visible
scale-0/scale-1 contribution in both saved views and retained default scale 1.
A successful save restore does not by itself confirm the initial lighting state:
the first view's initial scale-1 frames were dim until explicit reload. Validate
lighting initialization before using such frames as a brightness baseline.

To add a later location, reach a TimeMinder through normal play, save to an
unused slot, list the saves, and verify a restore. Record the selector, map,
fingerprint, reported position/yaw, runtime, geometry, and the feature visible
from that saved view. Keep the save and screenshots outside tracked files.

## Capture before and after

```sh
python tools/anoxrig.py load-save steamuser/1 > /tmp/rowdys-before.txt
sleep 8
python tools/anoxrig.py shot rowdys-before
```

Make one intended lighting/material/config change, then repeat:

```sh
python tools/anoxrig.py load-save steamuser/1 > /tmp/rowdys-after.txt
sleep 8
python tools/anoxrig.py shot rowdys-after
```

Check that both transcripts name the same save fingerprint, position, and yaw
before comparing the images. Small camera settling/rounding differences can
occur; reject a materially different view. Use the same settling interval for
both captures. NPC animations, particles, exposure adaptation, and temporal
rendering can still vary, so screenshots are not expected to be pixel-identical.
Shots are written to ignored `tools/shots/` (or `ANOX_SHOTS`). Keep the relevant
game/Remix logs and a copy of the active configs alongside local test evidence.

After testing, stop the game and restore the original Steam launch options and
desktop session as described in `HANDOFF.md`. Do not mark the outdoor, water, or
lava material checks complete until the relevant scene has actually been seen.
