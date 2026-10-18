# Exposure matched to the original game — 2026-10-18

Goal: Remix should not look brighter than the original Anachronox.

Method: `tools/anoxcheck.py OUT MAP... --ab-original` shoots each map's start view with RTX Remix and with the
original rasterised renderer (Remix' `d3d9.dll` moved aside for that run: QindieGL draws through Wine's D3D9 with
the game's lightmaps). QindieGL does not implement the game's hardware gamma (`u_gl_gamma 1.4` in
`SAVE/GLOBAL/settings.cfg`), so the original shots are corrected with `v' = v^(1/1.4)` before comparing mean linear
luminance. EV = log2(original / Remix). Setup: GE-Proton 11-9, Remix Plus 1.5.1, autoexposure on.

| Map | Before (EV) | `rtx.tonemap.exposureBias` | After (EV) |
| --- | --- | --- | --- |
| rowdys | -1.86 | -1.9 | -0.29 |
| tenements | -2.32 | -3.2 | -0.69 |
| votowne | -3.39 | -3.4 | -0.43 |
| museum | -2.84 | -2.8 | -0.22 |
| crevice | -0.81 | -0.8 | -0.05 |
| sunstrip | -3.30 | -4.3 | -0.16 |
| bricksb | -1.80 | -1.8 | -0.32 |

Negative = Remix brighter than the original. The values are in `anox_customise.ini` (`[rtxconf.<map>]`); other
maps get the global `-2.0` (also in `rtx.conf`). Autoexposure absorbs part of a bias change, so a second pass was
needed for tenements and sunstrip. Remaining visible difference: characters (Boots) are darker under Remix than
with the original lighting, which is a lighting/material difference, not exposure.

To match another map: run the `--ab-original` check for it, take the EV from the report (or the corrected value
as above), set `rtx.tonemap.exposureBias` in its `[rtxconf.<map>]` section and check once more.
