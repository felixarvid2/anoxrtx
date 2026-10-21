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

### Maps without a usable start view (2026-10-19, last three 2026-10-21)

Sixteen maps had no usable start view. They were measured from rig-camera views spread over each map: up to
three eye-height spots at `info_player_start` and `path_corner` entities (`tools/find_views.py MAP.bsp --spots 3`;
the views are in `docs/views/exposure-spots.txt`), with the same gamma-corrected EV as above.

| Map | Result |
| --- | --- |
| fortress2 | Remix 0.5 EV brighter in both runs (spot0 -0.53, start view -0.52): bias **-2.5**, after -0.19 |
| fortress1, mburger | within ±0.4 EV per view, around 0 overall: global bias kept |
| commbase, commiteon | +0.8 to +1.4 EV, but because the sky is different (Remix draws a dark night sky, the original a bright sky with sun): not exposure, left at global until the sky is fixed |
| slevant | +2.4 EV, but because the original's orange haze over the lava is missing under Remix: not exposure (fog) |
| crevicelanding | spots 0/3/4/5 +0.40/+0.96/+0.63/+0.64, median +0.6 (Remix darker): bias **-1.4**, after -0.19/+0.43/+0.13/+0.11 (median +0.12). spot1 left out: the landed ship model is nearly unlit under Remix (+2.0, model lighting, not exposure); spot2 looks into the void |
| servicetunnel | start view -0.76 (spot0 -1.17 agrees but its shots differed): bias **-2.8**, after +0.04. The other five spots render no world in either renderer (far from the player start; the engine only draws what is visible from the player) |
| labbuilding | spots 0/4/5 -0.73/+1.54/-0.39, too spread to set a value: Remix shows a brighter sky through the glass roof, the original has a teal tint in a corridor that Remix lacks, a window shows black instead of the city, and the fill light blows out a character on the stairs. Global bias kept |
| ballotine, basement, braintrain, braintrain-b, kraptonbay, baltownr | spots outside the playable map or black in one renderer: no usable view |
| hivebay | start is a scene that draws no world (all views give the same black frame) |

To match another map: run the `--ab-original` check for it, take the EV from the report (or the corrected value
as above), set `rtx.tonemap.exposureBias` in its `[rtxconf.<map>]` section and check once more.

## Characters

The original lights models with the lightmap value under them (`R_LightPoint`) plus a per-map model light
(e.g. rowdys 0.6/1/1, the teal on Boots' coat); path tracing has neither, so characters were about 2 EV
darker than in the original although whole frames matched. QindieGL adds a fill light per character
(`[maplights.*] model_fill`, QindieGL #30/#32): a spot aimed at each `RF_DIRLIGHT` model (characters, not
props) within 350 units of the camera, as bright as `model_fill` times the map lights' irradiance at the
model, with the original's model-light colour. A fixed brightness (#30) depended on each map's exposure and
autoexposure (votowne +2 EV too dark, baltown 2 EV too bright).

Measured with `anoxcheck.py --ab-original`, character region (centre bottom) minus whole frame, original
gamma-corrected; negative = character brighter than in the original:

| Map | `model_fill` | Character vs frame (EV) |
| --- | --- | --- |
| votowne | 1.5 (default) | -0.03 |
| krapton | 1.5 | +0.31 |
| comhills | 1.5 | -0.17 |
| scommons | 1.5 | -0.30 |
| hephaestus | 1.5 | -0.24 |
| rowdys | 0.9 | -0.24 |
| baltown | 0 | 0.00 |
| greattree | 0.1 | -0.24 |
| starport | 0.3 | -0.12 |
| bricksb | 0.35 | -0.19 |

The irradiance sum has no occlusion and does not include the Numos sky, so where the room or sky already
lights the character (outdoor maps, lamps behind walls) it over-lights; those maps have their own value.
The other ~69 maps use the default unmeasured. Not covered: the greattree view has a purple tint under Remix
that the original does not have (unrelated to the fill light).
