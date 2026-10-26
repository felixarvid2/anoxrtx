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
the sun), now the map sun is back on, but it has no visible effect: comhills' horizon views are pixel-identical
with `sun_scale` 0, 1 and 256 and with the direction inverted (an earlier reading that the direction was inverted
came from animation noise in the start view and was reverted). QindieGL creates and draws the distant light
without errors. Exposure after the change, start view / horizon views:

| Map | bias | start | horizon views |
| --- | --- | --- | --- |
| sunstrip | -4.3 → -2.4 | -0.09 | +1.20, -1.07, +0.28, -0.16 |
| comhills | -2.4 → -1.8 | +0.16 | +1.82, +1.15, +1.76, +1.45 (distant terrain too dark) |
| baltown | -0.5 → -1.8 | -0.02 | -0.10, -0.06, -0.06, -0.11 |
| starport | -2.5 | +0.11 | (building views as above) |

comhills' distant terrain stays dark because nothing lights it (no working sun; the original also has ArghRad's
`_sun_ambient 30`): fog remap off made it darker, `rtx.skyBrightness` 3/6/12 mostly brightens the sky (terrain
only ~0.3 EV).

