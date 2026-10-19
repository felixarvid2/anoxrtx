---
name: anox-ab-measure
description: Measure how Anachronox looks under RTX Remix versus the original renderer and calibrate settings from it (per-map exposure bias, character fill light model_fill, dlight strength). Use when asked whether Remix is too bright/dark, to match the original, to set rtx.tonemap.exposureBias or model_fill for a map, or to check a lighting change across maps.
---

# A/B measurement against the original renderer

Game runs go through the rig (see the `anox-game-test` skill for preconditions and restoring). Here: how to get
numbers you can trust, and how to turn them into settings.

## Shoot

```bash
tools/anoxcheck.py ~/.cache/anoxrtx/checks/NAME MAP [MAP...] --ab-original [--views FILE] --settle 15
tools/ab_ev.py ~/.cache/anoxrtx/checks/NAME          # gamma-corrected EV per view
```

- `--ab-original` shoots each view with Remix ("on") and with Remix' `d3d9.dll` moved aside ("off" = Wine
  D3D9 with the game's lightmaps). The report's own EV is **not** gamma-corrected; always use `tools/ab_ev.py`
  (original shots ^(1/1.4), top 40 rows ignored for the Remix overlay). EV < 0 = Remix brighter.
- Views: without `--views` the map's start view is used. Rig-camera views (`MAP NAME X Y Z PITCH YAW`) come
  from `tools/find_views.py`: `--spots 3` (eye height at player start / path_corners, for whole-map exposure),
  `TEXTURE` (faces with a texture, e.g. `proc_lava`), `--light N`. Saved view files: `docs/views/`.
- Other A/B switches: `--ab-cfg "set r_novis 1"`, `--ab LAYER`, `--ab-dlight "X Y Z R G B I"` (test light).
- Long batches: run in the background (`run_in_background`), ~2–3 min per map and side.

## Trust a number only when

1. You looked at `compare_<view>.png`. Numbers lie when: a view is outside the map (void), the start is a
   cutscene or fade (all views give the **same** frame, even in the original: hivebay, levant1, hephlava),
   NPCs walk through the view (settle > ~0.1), or one side is black.
2. Neither shot is mostly black (`black on/off` < ~0.5).
3. The difference is exposure, not content. A dark Remix night sky against a bright original sky (commbase,
   commiteon) or missing fog/haze (slevant) shows up as EV but a bias would only hide it: record those as
   sky/fog issues in TODO instead.

Decide the rule before you look at the data: median of the usable views, write a value only when
|EV| >= 0.3, rounded to 0.1.

## Turn into settings

- Exposure: `[rtxconf.<map>] rtx.tonemap.exposureBias = -2.0 + EV` in `anox_customise.ini` (global is
  -2.0). Autoexposure absorbs part of a change: re-check once and correct large ones a second time.
- Characters: `[maplights.<map>] model_fill` (default 1.5). Measure the character region against the frame
  (original vs Remix); outdoor or enclosed maps usually need less (baltown 0, greattree 0.1).
- Install: copy `anox_customise.ini` to the game folder (back up the old one first), check `cmp` afterwards.
- Document in `docs/exposure-match.md` (tables per pass), TODO in Swedish, then commit/PR/merge.

## Known rig traps

- `+map` at launch (what `anoxcheck` uses) stalls the Remix bridge on crevicelanding, labbuilding and
  servicetunnel: black Remix frame, `Data Queue overwrite` in `*bridge32.log`, "handshake timeout" in the
  Remix log. Load those from the menu instead: `$RIG start; sleep 20; $RIG console map NAME`.
- Loading from the menu can also stall intermittently (2/~7 on servicetunnel/labbuilding). Before
  attributing a fix, repeat the baseline too: a single passing run proves nothing.
