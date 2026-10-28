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
| commbase, commiteon | +0.8 to +1.4 EV with a near-black sky. Not a night sky: the forest skybox is drawn, but autoexposure adapts to the sunlit ground so the skybox (fixed radiance) was 4.4–7.4 EV darker than in the original while the ground matched. Fixed 2026-10-21 with `rtx.skyBrightness = 140`, bias **-0.2**, and fog remap off (the teal fog `.196 .674 .811` tinted the ground once the sky lit it). After: frame +0.14/-0.07/-0.35/+0.35 (median +0.03), sky +0.24 to +0.85 |
| whitendon | the mountain skybox ~4 EV too dark against the ground (top/bottom of upward views +2.6–3.5 / -0.7–-2.0 EV), the same autoexposure effect as commbase. Fixed 2026-10-22: `rtx.skyBrightness = 100`, bias -5.1 → **-4.0**. After: start view -1.10 (bright snow), spots +1.20/+0.42/-0.95 (median -0.3), sky region (top third) +1.2 to -1.1 |
| waukees, greattree | purple tint over the whole scene: the yellow-white fog (`.94 .996 .76`) as volumetric fog. Fixed 2026-10-22 with fog remap off on both. waukees was also ~2.4 EV too dark on spots: bias -1.4 → **-0.4**, after start view -0.53, spots +1.45/+0.93; greattree start view +0.01 at the global bias |
| other outdoor skybox maps (2026-10-22) | upward views (pitch -20) on 24 maps with large sky areas: sky and ground within ~1.5 EV of each other on onegate, fortressgrounds, hovel, tensil, pillars, crevice, crevicelanding, bricksc/bricksd, hephaestus, onegatestn; no sky fix needed. About half the views were black in one renderer (outside the map). Not exposure-matched from these: fortressgrounds spot0 +2.9 (helipad), hephaestus spots -0.6 to -2.5 |
| fog maps, sky through windows (2026-10-22) | views towards the sky from spots in the player start's PVS (`find_views.py MAP.bsp --sky 2`, views in `docs/views/fog-sky.txt`) on the 26 other maps with worldspawn `fog`; 13 show sky from there. Only tours had fog in front of the sky: fog remap off (-1.72 → -1.59 EV on sky0). Not fog: tours' skyline is missing from the skybox under Remix (a brighter sky only washes it white), bricksd's neon signs are dim, mmuseum's windows are white instead of blue. Spots at the player start render black under Remix (the camera is inside the player model) and are skipped |
| hephaestus, fortressgrounds (2026-10-22) | hephaestus: start view -0.27, six spots -0.37 to -2.27 (median -1.2; Remix lights the dark alleys more than the lightmaps): bias -1.4 → **-2.0**, after start +0.13, spots -1.65/-1.90/+0.20/-0.69/-1.31/-0.04. fortressgrounds: start view -0.04, the other spots outside the map; only the white helipad is darker (+2.9, material): bias kept |
| slevant | +2.4 EV, but because the original's orange haze over the lava is missing under Remix: not exposure (fog) |
| crevicelanding | spots 0/3/4/5 +0.40/+0.96/+0.63/+0.64, median +0.6 (Remix darker): bias **-1.4**, after -0.19/+0.43/+0.13/+0.11 (median +0.12). spot1 left out: the landed ship model is nearly unlit under Remix (+2.0, model lighting, not exposure); spot2 looks into the void. The ship (`ob_shuttlewhol6`, `entity.dat` lighting 1 = `RF_DIRLIGHT`, the character model light) gets no fill light; fixed 2026-10-22 with emission from its own texture at 0.5 (`maps/model_emission.tsv`): spot1 -0.23, spot4 -0.63 (`rtx.worldSpaceUiTextures` instead made it flat and ~1 EV too bright) |
| servicetunnel | start view -0.76 (spot0 -1.17 agrees but its shots differed): bias **-2.8**, after +0.04. The other five spots render no world in either renderer (far from the player start; the engine only draws what is visible from the player) |
| labbuilding | start view -0.00 (after the fixes below), spots 0/2/4/5 -0.69/+1.28/+1.54/-0.40: median 0.0, global bias kept. Content differences, not exposure: the window showed opaque grey instead of the city because Remix turned the map fog into volumetric fog (fixed: `[rtxconf.labbuilding] rtx.volumetrics.enableFogRemap = False`); the original has haze over the city and a teal tint in a corridor that Remix lacks, and Remix shows a brighter sky through the glass roof |
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
| labbuilding | 0.6 | +0.17 (1.5: -0.54) |

The irradiance sum has no occlusion and does not include the Numos sky, so where the room or sky already
lights the character (outdoor maps, lamps behind walls) it over-lights; those maps have their own value. A lamp right above a character still over-lights it under path tracing
(labbuilding stairs: -1.2 EV at `model_fill` 0.6, -1.7 at 1.5), because the original lights models only from the
lightmap under them.
Not covered: the greattree view has a purple tint under Remix that the original does not have (unrelated to the
fill light).

### All other maps (2026-10-22)

Start views of the 69 other maps with `--ab-original`, the same character box (centre bottom, x 0.40–0.62,
y 0.50–1.0) checked by eye to contain Boots; 60 usable (commbase, fortress1/2, republic: black or loading;
sewagic1a: no character; mystech1, sunstrip, whitendon, zordos: the camera differs between the renderers).
Maps with |character vs frame| > 0.3 got `model_fill = 1.5 * 2^EV`, then a second pass from each map's measured
response (EV per doubling of `model_fill`, 0.25–0.65; the fill is only part of the light on the character).
Verified Remix-only against the same original shots. Borderline maps (|EV| <= 0.35) and slevant keep 1.5.

| Map | `model_fill` | Character vs frame (EV) | Note |
| --- | --- | --- | --- |
| baltownr | 0.39 | -0.02 (1.5: -0.93) |  |
| bricksc | 0.86 | -0.23 (1.5: -0.80) |  |
| bricksc2 | 0.41 | -0.11 (1.5: -0.93) |  |
| bricksd | 0.1 | -0.66 (1.5: -1.45) | room light alone over-lights it (fill at the 0.1 floor) |
| chamber | 0.24 | -0.08 (1.5: -1.48) |  |
| commiteon | 1.5 (default) | +0.17 |  |
| crevice | 1.5 (default) | -0.26 |  |
| crevicelanding | 0.57 | +0.03 (1.5: -0.65) |  |
| doren | 1.5 (default) | +0.33 |  |
| fortressgrounds | 32 | -0.35 (1.5: +0.64; bias -2.9 → -2.6, frame +0.03) | weak fill response, see below |
| franks | 0.1 | -0.48 (1.5: -1.65) | room light alone over-lights it (fill at the 0.1 floor) |
| grumpos | 32 | +0.18 (1.5: +0.88) | weak fill response, see below |
| hephfactory | 0.1 | -0.58 (1.5: -2.10) | room light alone over-lights it (fill at the 0.1 floor) |
| hephlava | 1.5 (default) | -0.20 |  |
| hephpipes | 0.58 | -0.06 (1.5: -0.75) |  |
| hephpoor | 5.03 | +0.02 (1.5: +1.16) |  |
| hephtower1 | 1.5 (default) | -0.01 |  |
| hephtower2 | 1.11 | -0.25 (1.5: -0.44) |  |
| hive | 0.27 | -0.25 (1.5: -0.59) |  |
| hovel | 0.92 | -0.26 (1.5: -0.71) |  |
| krap2 | 1.08 | -0.30 (1.5: -0.47) |  |
| kraptonjail | 1.04 | -0.26 (1.5: -0.53) |  |
| kraptonmaze | 1.5 (default) | -0.18 |  |
| levant | 1.5 (default) | -0.12 |  |
| levant1 | 0.1 | -0.44 (1.5: -1.92) | room light alone over-lights it (fill at the 0.1 floor) |
| levant2 | 1.5 (default) | -0.10 |  |
| limbus | 1.14 | -0.28 (1.5: -0.40) |  |
| limbusdome | 0.25 | -0.09 (1.5: -1.25) |  |
| mburger | 1.5 (default) | +0.08 |  |
| mmuseum | 0.1 | +0.19 (1.5: -1.02) |  |
| mugpath | 0.25 | -0.11 (1.5: -1.30) |  |
| museum | 1.5 (default) | -0.18 |  |
| museumnight | 1.5 (default) | -0.21 |  |
| mystech2 | 1.5 (default) | -0.13 |  |
| onegate | 4.07 | -0.04 (1.5: +0.75) |  |
| onegatestn | 0.14 | -0.10 (1.5: -1.07) |  |
| orange | 1.09 | -0.28 (1.5: -0.46) |  |
| pay2pray | 0.14 | -0.35 (1.5: -1.04) |  |
| pillars | 0.1 | +0.11 (1.5: -1.36) |  |
| redlight | 1.5 (default) | +0.26 |  |
| routubes1 | 1.5 (default) | -0.03 |  |
| routubes2 | 4.34 | -0.04 (1.5: +0.54) | the fill spot shows on the tunnel wall behind the character |
| scommonnight | 1.5 (default) | +0.10 |  |
| senderss | 1.5 (default) | -0.05 |  |
| sendormitory | 0.1 | -0.56 (1.5: -1.05) | room light alone over-lights it (fill at the 0.1 floor) |
| servicetunnel | 1.5 (default) | -0.33 |  |
| sexmach | 1.5 (default) | -0.14 |  |
| slevant | 1.5 (default) | -0.60 | original orange haze missing (frame +1.36), not adjusted |
| slounge | 1.5 (default) | +0.31 |  |
| slutopia | 1.5 (default) | -0.04 |  |
| temple | 0.13 | -0.18 (1.5: -1.03) |  |
| tenements | 2.12 | +0.28 (1.5: +0.50) |  |
| tensil | 0.1 | -0.90 (1.5: -1.96) | room light alone over-lights it (fill at the 0.1 floor) |
| tours | 0.61 | -0.02 (1.5: -0.67) |  |
| tours2 | 6 | +0.07 (1.5: +1.15) |  |
| tubbys | 0.4 | -0.38 (1.5: -1.21) | green tube light on the coat; 0.22 gave a noisy +0.85 |
| vendomart | 5.68 | +0.07 (1.5: +0.96) |  |
| warshipbay | 1.5 (default) | -0.30 |  |
| waukees | 0.1 | -0.50 (1.5: -1.58) | room light alone over-lights it (fill at the 0.1 floor) |
| whacks | 1.5 (default) | +0.31 |  |

Seven maps stay 0.4–0.9 EV too bright at the lowest value (0.1): there the path-traced room light alone lights the
character more than the original's lightmap sample; less fill cannot fix that. fortressgrounds and grumpos respond only weakly to the fill (about 0.2 EV per doubling;
2026-10-26, Remix-only, character vs frame): fortressgrounds 0 / 1.5 / 8 / 32: +1.11 / +0.97 / +0.49 / -0.19,
grumpos +0.87 / +0.84 / +0.68 / +0.17. Boots stands with his back to the camera in front of bright surfaces (the
lit logo, ceiling lamps), autoexposure takes back part of the fill (fortressgrounds frame -0.23 → +0.31 at 32,
so its bias went -2.9 → -2.6). Both now `model_fill = 32`.

### Over-lit characters: legacy metallic (2026-10-26)

Remix shades textures without a replacement material (the characters: their skins are composed at runtime with
the eye and mouth frames, so their hashes change) with `rtx.legacyMaterial` (metallic 0.1, roughness 0.7), i.e.
a 0.04 dielectric specular lobe on top of the diffuse; the original shades models diffuse only. dxvk-remix
uses F0 = mix(0.04, albedo, metallic) (`calcBaseReflectivity`), so a higher metallic with roughness 1 trades
the grey sheen and part of the diffuse for a rough albedo-coloured lobe, which darkens characters.

A global `metallicConstant = 1` / `roughnessConstant = 1` (all 71 measured maps, Remix-only against the saved
original shots, measured as in `tools/ab_ev.py`) moved characters 0.8–1.5 EV darker on almost every map (median
character vs frame about +1.0 EV, Boots near black); the fill light cannot make up for it (tensil: `model_fill`
0.1 → 0.23 changed it by 0.1 EV). An earlier check (2026-10-25: tensil -0.78 → +0.02) had used luminance
without the sRGB/gamma handling of `ab_ev.py`, which hid this. So it is set per map in `[rtxconf.<map>]`
(default 0.1/0.7 in `[rtxconf.default]`) only on the seven maps above, at metallic 0.5, roughness 1, `model_fill`
0.1:

| Map | metallic 0.1 (before) | metallic 1 | metallic 0.5 |
| --- | --- | --- | --- |
| tensil | -0.90 | +0.59 | -0.23 |
| bricksd | -0.66 | +0.17 | -0.09 |
| hephfactory | -0.58 | +0.86 | +0.23 |
| sendormitory | -0.56 | +0.09 | -0.01 |
| waukees | -0.50 | +0.47 | +0.10 |
| franks | -0.48 | +0.62 | +0.12 |
| levant1 | -0.44 | +0.66 | +0.15 |

(character vs frame, EV; whole frames at metallic 0.5: -0.21 to +0.33 EV.) World textures without a pbr block on these maps
also get the rougher, slightly more metallic look (the franks door is a little glossier). Controls rowdys and
baltownr with the default material: -0.08 and +0.07, as calibrated.

## mmuseum views (2026-10-24)

The bias -1.1 was set on the start view only. Five more views in the start's PVS (`find_views.py`, three spots
and two views towards the ceiling), measured against the original at -1.1: start -0.20, sky0 -0.33, spot0 -1.06,
spot1 +0.09, spot2 -0.35 (median -0.34). At **-1.5**: start +0.19, sky0 0.00, spot0 -0.72, spot1 +0.47, spot2
+0.01 (median 0.00). sky1 (-2.36 → -2.06) looks at a ceiling lamp whose hotspot is brighter under path tracing;
that is a local lighting difference, not exposure. The character fill row for mmuseum above was measured at -1.1.

## bricksd views (2026-10-24)

bricksd had no per-map bias (global -2.0; its start view was +0.15 in the all-maps pass, before the neon signs
got emission). Views in the start's PVS against the original at -2.0: sky0 (the neon signs) -0.32, spot0 -0.40,
spot3 -0.54. At **-2.4**: -0.06, -0.09, -0.21. The start view gets 0.54 EV darker (Remix shot vs Remix shot;
the original start shot failed), so it is probably about +0.6 now; it is mostly Boots' coat. Not exposure:
spot2 (+2.2) looks at a tall cyan energy column (spiral) that the original draws brightly and Remix draws as dark
spiral trunks. spot1 and spot4 were rejected: the original renderer shot the previous view (camera not moved yet).

bricksd spot2 (the energy column in the shaft): the column is several additive (SRC_ALPHA, ONE) effect meshes that
Remix draws almost invisibly faint (+2.6 EV). `[rtxconf.bricksd] rtx.enableEmissiveBlendEmissiveOverride = True`
with `rtx.emissiveBlendOverrideEmissiveIntensity = 2.5` makes them glow (+0.13; 10 was -0.42 and white); sky0,
spot0 and spot3 stay at -0.06, +0.13, -0.21. Found with the game's `gl_log 1` (ref_gl logs every GL call to
`anoxdata/gl.log`) and a QindieGL debug log of additive draws with their Remix hashes.

## starport sky and background buildings (2026-10-26)

With the Numos sky (`rtx.skyMode = 1`) the city skyline in starport's skybox (blue spires, pink towers) was replaced
by clouds and a grey horizon, and its sun, in the direction the views look, left the background buildings
(`ob_s_building-*`, props lit by the model light in the original) as black silhouettes: building views +1.6 to
+2.0 EV against the original. Numos is now off on starport (start view +0.11 EV at bias -2.5, unchanged) and the
buildings' 29 skins (`background/*.tga`) emit at intensity 1 (`maps/model_emission.tsv`), which makes them as light
as in the original. Two of the four building views stay black under Remix for an unknown reason (camera at
-1182 287 152 and -1076 1318 240).

## Numos off on sunstrip, comhills, baltown; map sun direction (2026-10-26)

Four horizon views from each start (and the start views) against the original: the Numos sky replaced
sunstrip's city skyline, comhills' sunny desert sky and baltown's purple dusk (views +1.6 to +2.7 EV darker), so
Numos is off there as on starport; only baltownr keeps it. These maps had `sun_scale = 0` (Numos was to provide
the sun), now the map sun is back on. It was far too weak: Remix spreads a distant light's radiance over its
disc (2 degrees), so `_sun_light / 200` gave almost no light; the global `sun_scale` is now 12. The direction in
the .lights files (from the sun into the scene) is right; inverting it (#92, reverted in #93) lit the terrain from
below, which is why sun x64/x256 tests made with it showed nothing. Exposure before the sun fix, start view /
horizon views:

| Map | bias | start | horizon views |
| --- | --- | --- | --- |
| sunstrip | -4.3 → -2.4 | -0.09 | +1.20, -1.07, +0.28, -0.16 |
| comhills | -2.4 → -1.8 | +0.16 | +1.82, +1.15, +1.76, +1.45 (distant terrain too dark) |
| baltown | -0.5 → -1.8 | -0.02 | -0.10, -0.06, -0.06, -0.11 |
| starport | 0, autoexposure off | +0.19 | walkway +0.45 / +0.52, atrium -0.39 (2026-10-28, below) |

With `sun_scale = 12` comhills' terrain is sunlit as in the original. Its blue map fog tinted the sunlit ground
blue (`enableFogColorRemap = False` there) and the skybox was ~3 EV too dark against it (`skyBrightness = 24`,
bias -0.4): start view -0.23, horizon views +1.13, +0.40, +1.29, +0.55 (whole frame; terrain alone within
about ±0.7). baltown: start -0.62, views -0.12..+0.16. sunstrip's and starport's views do not change with the sun.


## baltownr (2026-10-27)

Usable views are only in the lower levels (`284 -3904 404` and `329 -2813 398`, pitch 10, four directions each, plus
the slime floor view at `354.7 -2687.8 450`): the start is a closed shaft room, spots near it put the camera in the
player model, and map light views are outside the original's PVS. With the global bias -2.0 they were -0.30 to
-3.6 EV (median -1.5, Remix brighter). Not the cause on its own: Numos (on/off identical), map light `scale = 0.36`
(s0 0.5 EV darker, s1 hardly changed), the green slime floor (`ballotine/slime01a`, intensity 15 from one light
2000 face on baltown; set to 2 in `maps/emissive_intensity.tsv`: the corridor views 0.5-0.7 EV darker, baltown's
views -0.23 to +0.17 afterwards). With slime 2 and bias -3.5: -2.13 to +1.09, median -0.35; bias set to **-3.8**
(verified: -1.72 to +1.34, median -0.07). Left: s1_1 (looking along the slime corridor) -1.7, s0_2/s1_3 +1.2/+1.3,
and the start shaft's sky (TODO).

Start shaft, after QindieGL #38 (`skipenclosingmodels`, 2026-10-27): the player starts at `344 -3850 1200` inside the
hill `ob_commhill02`, which is now skipped, so the night sky shows. The walls stayed nearly black: start view
(player's view) +2.35 EV, shaft view `344 -3850 1260` pitch 10 yaw 315 +2.48, upward view `344 -3850 1380` pitch -75
+2.94. The original lights the shaft with `_sun_ambient 15` and baked bounce from the orange `_sun2` (light 300);
only `_sun2` is a Remix light. `sun_scale = 48` on baltownr (4x): shaft +1.77, upward +2.60. A fill light just under
the opening (`maps/overrides/baltownr.override`: `add 344 -3850 1420 1 0.75 0.5 I 0`): I = 300 shaft +0.59; 1000
-1.83; **400**: shaft +0.01, start view **+0.54**. The lower-level views do not change (s0_0 -0.24, s0_2 +1.23,
s1_1 -1.76). The upward view stays about +3: the sky is 2-3x darker than in the original, and `rtx.skyBrightness = 3`
did not help (autoexposure takes it back in a frame that is mostly sky); not kept.

## starport city views (2026-10-27)

The seven rooftop views (`ob_s_building-*`, in the air west of the start; the two inside `ob_btrain` show the city
since QindieGL #38) are +2.4 to +2.8 EV (Remix darker) at bias -2.5; the start (an indoor corridor) is +0.13.
`rtx.skyBrightness = 3` changed them by about 0.1 EV: autoexposure brings bright outdoor and dim indoor frames to a
similar mean, while the original is about 4x brighter outdoors (mean 0.28 vs 0.07). A map bias cannot match both;
no change until there are views from places the player stands outdoors.

Follow-up (2026-10-28): views at path_corner spots the player and NPCs use, with the player moved next to each
(`goto`, so the original renderer's PVS covers it): the outdoor walkway east of the service-tunnel exit (beltway2
3960 -573 -422, beltway3 3475 -567 -419, yaw 0 / -22, pitch -10), the atrium with the skylight (pikachu 917 1378 345,
yaw -135), the café with the large window (mannberg4 -248 2718 -154, yaw 45) and a fixed view in the start corridor
(-1503 1767 158, yaw 90). The walkway is +3.22 / +2.64 EV (Remix darker), the atrium +1.50, the start +0.10.

Tried, one session per series, the ini rewritten and the map reloaded (QindieGL re-reads it on map load):
`rtx.autoExposure.evMaxValue` 3 / 1 / 0 and `evMinValue` -3 / -4 / -6 / -1 / 0 / 0.5 changed no view (images equal up
to noise); they are applied (QindieGL logs them) but do not take effect when set at runtime. `rtx.skyBrightness`
30 / 100: walkway +3.16..+2.08, atrium +0.44 / +0.11. `rtx.autoExposure.enabled = False` does take effect: with
`exposureBias = 0` the start is +0.19, the walkway +0.45 / +0.52, the atrium -0.39 (fresh start, settle < 0.05).
Kept: autoexposure off and bias 0 on starport (`enabled = True` in `[rtxconf.default]` so other maps get it back).
The café is -1.80 because Remix draws its window glass milky white instead of transparent (the original shows the
city through it); that is a glass problem, not exposure.

## Static-off emission for plain faces (2026-10-28)

`emissive_styles.py` now also lists plain faces (no SURF_LIGHT) whose texture is emissive elsewhere, with style 0
(QindieGL #41), so those faces no longer glow. Several map biases had been calibrated against walls that glowed;
start-view EV against the 2026-10-18 originals (old files / new files / new files with the new bias):

| map | old | new | new bias | bias |
|---|---|---|---|---|
| slounge | -0.07 | +3.68 | +0.41 | -3.7 -> 0.0 |
| hephtower2 | +0.03 | +1.73 | +0.31 | -4.8 -> -3.1 |
| mystech2 | -0.26 | +1.29 | +0.18 | -5.2 -> -3.9 |
| scommons | -0.12 | +0.41 | +0.08 | -2.8 -> -2.4 |
| tours | +0.03 | +0.40 | +0.04 | -1.3 -> -0.9 |

onegate, hive, senderss and kraptonmaze moved by at most 0.24 EV; ballotine and kraptonmaze give a black start frame
with both file sets. ms/frame is unchanged (A/B on the same ten maps, within 0.4 ms). slounge matches in mean but
not in distribution: the original lights the room evenly, Remix lights one wall and leaves the door dark.

## Follow-ups (2026-10-28)

**ballotine, kraptonmaze "black frame".** Not a rendering fault. `anoxcheck.py` waited for the map's
`MapLights: <map> CreateLight` line in QindieGL.log, but the log keeps earlier sessions, so an old line ended the wait
at once and the shots came `--settle` seconds after the window appeared. ballotine also shows "One moment..." for a
while after its lights are created. anoxcheck now reads only this run's part of the log and retakes a black first
shot (up to six times, 10 s apart). ballotine was +0.51 EV at the default bias: `[rtxconf.ballotine]` bias -1.5,
verified +0.07. kraptonmaze -0.48 (no change).

**slounge light distribution.** The room is lit by one light (index 86, `-984 1504 192`, light 200). Under Remix it
throws a hard-edged pool on the left wall and leaves the door dark; the original lights the room evenly. Moving it
down 24/48/96 units changed the start view by 0.2-0.8 EV but not the look; a radius of 16/48/96 only made it brighter
(-2.2 to -4.2 EV). It is the difference between a ray-traced point light and the baked lightmap; no override kept.

**starport café window.** The milky glass was `braintrain/glass-1b`, a translucent texture that is also emissive (a
SURF_LIGHT face elsewhere); with the static-off rows it is clear. Through it the city props show, but the skybox
behind them is a flat dark grey instead of the original's blue sky with spires. `rtx.skyBrightness` 10,
`rtx.skyProbeSide` 2048, `rtx.skyReprojectToMainCameraSpace`, `rtx.skyForceHDR`, `rtx.skyMode = 1` and hiding the
three glass textures (`rtx.hideInstanceTextures`) did not change it, and the skybox is complete in all eight
directions from the walkway. The cause was the volumetric fog (worldspawn `"fog" ".00014 .5 .5 .5"`), as on
labbuilding: `rtx.volumetrics.enableFogRemap = False` on starport shows the sky and spires as in the original.
Café +2.59 -> -0.55 EV, walkway (beltway2) +0.47 -> +0.36, atrium (pikachu) +0.67 -> -1.16, start +0.19 -> -0.15;
bias kept at 0. (The two diagnostic tests were suggested by DeepSeek; neither was the cause.)

**tours room, light on/off.** Re-measured after the new tours bias (-0.9), views c/d (the room's back), Remix vs
original: light on -0.74 / -0.31 EV, light off +1.49 / +3.09. Remix switches the room 3.5-4.7 EV, the original
1.2-1.3: with the light off the original still shows a bright patch on the far wall that Remix does not have (no
point light near it; light 209 at 948 -24 -112 is behind the camera), probably baked from a light-textured face.
Views a/b (towards the door) -1.6..-0.9 EV in both states. The original "on" shots have the console over them.

**baltownr upward view.** Like starport, autoexposure brought the sky-filled upward view of the start shaft down to
the indoor level. `rtx.autoExposure.enabled = False`, bias -0.5 (was autoexposure with -3.8): EV per view
(old -> new) shaft_h +0.01 -> -0.24, up_hi +3.05 -> +0.72, s0_0 -0.24 -> -0.80, s0_2 +1.23 -> -0.25,
s1_1 -1.76 -> -1.62, start +0.54 -> +0.34; median -0.24, spread 4.8 -> 2.3 EV.
