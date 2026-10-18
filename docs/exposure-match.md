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

## All maps

A second run covered the other 79 maps (all except `cine*`, `black`, `flashback`, `whitecaves*`, `sphere*` and
the seven above), measured at the global bias `-2.0` with `--settle 15`. Per-map bias = `-2.0 + EV`, rounded to
0.1, written for the 54 maps with |EV| >= 0.3 (the values are in `anox_customise.ini`, from `mystech2 -5.2` /
`sexmach -6.3` to `baltown -0.5`). Maps with |EV| < 0.3 keep the global value.

Re-check of the five largest changes (after, EV): baltown +0.12, hephtower2 -0.21, mystech2 -0.22, whitendon -0.06,
sexmach -1.04 at -5.3, so a second pass set it to -6.3 (-0.23).

Not set (no usable comparison): ballotine, basement, braintrain, braintrain-b, commbase, commiteon,
crevicelanding, fortress1, fortress2, hivebay, kraptonbay, labbuilding, mburger, servicetunnel, slevant (black
frames, a scene still moving between the two shots, or a start view that differs between the runs), and
baltownr (Remix start frame mostly black). These need a hand-picked view (`--views`) to measure.

To match another map: run the `--ab-original` check for it, take the EV from the report (or the corrected value
as above), set `rtx.tonemap.exposureBias` in its `[rtxconf.<map>]` section and check once more.

## Characters

The original lights models with the lightmap value under them (`R_LightPoint`) plus a per-map model light
(e.g. rowdys 0.6/1/1, the teal on Boots' coat); path tracing has neither, so characters were about 2.2 EV
darker than in the original although whole frames matched. QindieGL #30 adds a fill light per character
(`[maplights.*] model_fill`). Rowdys character region (linear luminance): 0.0031 without, 0.0155 with
`model_fill = 10`, 0.0139 in the original; museum and tenements checked side by side. The fill light also
brightens the floor right around a character a little.

