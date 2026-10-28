# Baked light that Remix cannot reproduce — 2026-10-28

Goal: find places where the original's lightmaps are clearly brighter than what the Remix lights can give, because
the source of that light is not a Remix light. `tools/baked_light_gaps.py` estimates this from the BSP and the
installed `.lights`/`.override`/ini; nothing here was checked in the game yet.

## Method

- **Baked:** the Quake 2 lighting lump, per face at `lightofs`, one `w*h` RGB block per entry in `dface_t.styles`
  (luxel grid: `floor(min s / 16) .. ceil(max s / 16)` from the texinfo vectors). Anachronox faces mostly carry two
  style-0 blocks; the renderer adds all blocks, so they are summed. Styled blocks are left out unless `--styled`.
  Luxels are sampled on 2x2 blocks (32 units), 2 units off the surface, pulled towards the face centre when an edge
  luxel lies in the neighbouring wall.
- **Remix estimate (direct light only, luminance):** `.lights` rows with the `.override` applied, radiance
  `scale * ref * (light / ref) ^ exponent` (QindieGL `rmx_maplights.cpp`, `[maplights.*]` from the ini) and
  `E = radiance * pi * r^2 * cos / d^2`; spots within their cone; `startoff` rows off, styled rows only with
  `--styled`; the sun line where the luxel sees a SURF_SKY face; every non-sky SURF_LIGHT face with value > 0 as an
  area light (`E = Le * A * cos_e * cos / d^2` per 64-unit patch), `Le` = the `emissive.usda` intensity
  (`clamp(value / 100, 1, 15)` over all maps, or `maps/emissive_intensity.tsv`) times the texture's mean linear
  luminance (`--textures`, else 0.5). Visibility is a BSP trace (world model, CONTENTS_SOLID only).
- **Gap:** per map `K` = area-weighted median of baked / E over the bright luxels (top 40 %, at least 24) that get
  direct light, so the map's exposure and a uniform share of Remix's bounce cancel. A luxel is a gap when
  `baked > 4 * K * E`. Gap luxels are joined into clusters (64-unit cells); `excess = sum(area * (baked - K * E)) / 255`.
- **Likely source** per cluster, from the brightest luxel: *masked emitter* (see below), *styled light* (> 50 % of
  the baked light in styled blocks), *falloff* (point lights explain it with Quake's linear `(light - d) * cos`: the
  light exists in Remix but inverse-square falls off sooner), *surface light* (SURF_LIGHT faces dominate),
  *sky light* (the luxel sees SURF_SKY faces with a light value: qrad's sky emission), *ambient* (sky in view and
  worldspawn `_sun_ambient`/`_ambient`/`_minlight`), else *bounce*.
- **Candidate:** `add X Y Z R G B LIGHT 0` in front of the dominant surface light or off the bright surface (distance
  half the cluster size, 48–256), colour from the lightmap, `LIGHT` from the missing irradiance at the anchor
  inverted through the ini formula; plus a camera view `X Y Z PITCH YAW` (Quake angles, pitch > 0 down) found with
  `find_views.py`'s helpers. The views are not checked against the spawn's PVS.

```sh
python3 tools/baked_light_gaps.py MAPS/*.bsp --lights-dir GAME/rtx-remix/maplights --ini GAME/anox_customise.ini \
    --textures GAME/anoxdata/textures --jobs 8 --overrides /tmp/OUT --json /tmp/OUT/all.json   # [--styled]
python3 -m unittest discover -s tools -p test_baked_light_gaps.py
```

All 98 maps take several minutes with 8 processes (pure Python; tours alone about 100 s). Candidate files (`<map>.candidates.override`, never
installed) and the reports of this run are outside the repo.

## Known spots

**slounge start booth.** Found (default run, cluster 5, *masked emitter*). The booth (`-1156..-1040, 1504`, the player
starts at `-1080 1504 24`) is lit by one SURF_LIGHT face, `sendormitory/celight2` value 3000 at `-1111.5 1503.5 125`,
the bottom of a hanging lamp. Light 86 (`-984 1504 192`) is behind the booth wall and does not reach it. The lamp's
top face (same texture, not a light, centre `-1111 1503.5 127`) is listed with style 0 in `slounge.estyles`, and
QindieGL's `qdx_estyles_match` accepts any entry within 2 units per axis of the drawn polygon's centre (`dz` is
exactly 2.0): the light face is drawn with the emission-off variant too. So the booth has no light under Remix, which
matches the dark start view after the static-off change. The same collision switches off **108 light faces on 13
maps** (vendomart 31, krap2 12, scommons 11, scommonnight 11, kraptonmaze 11, sphere3 8, tours2 8, sexmach 5,
hephlava 4, routubes1 4, ballotine, servicetunnel, slounge 1 each). Fix belongs in `emissive_styles.py` (do not list a
style-0 face within the tolerance of an unstyled light face with the same texture) rather than in overrides.

**tours room.** Not a style-0 gap: with the light `explosion` off, every surface of the room has a style-0 lightmap
of 2 (the floor under the light too); the bright patch is in the style-32 block (floor 29–77 there). Found with
`--styled` as cluster 0 (*styled light*, 95 % of the baked light in styled blocks, at `1296 26 -76`). So the original
does not take that style to 0 when the light is "off", while Remix (light and emission) does; the 1.2 EV vs 3.5–4.7 EV
switch in `exposure-match.md` fits a residual style value, not a missing source. Worth checking the style's off
value in the game (QindieGL #39 logs the levels) before adding any light.

## Maps by gap

Default run (style 0). `gap` = sum of excess, share = of the bright baked light. The outdoor maps lead because the
estimate has no Remix sky/indirect light at all; their *sky light* clusters mostly reflect qrad's emitting sky,
which Remix replaces with the skybox, sun and per-map exposure. Treat them as low confidence. *bounce* clusters with
Remix 0.0 far from any light (sphere, cinedem, hivebay) are often geometry outside the playable area.

| Map | Gap, share | Cluster at | Likely source | Baked / Remix (K·E) | View |
| --- | --- | --- | --- | --- | --- |
| braintrain | 18.1M, 35% | -2697 920 -2222 | sky light | 201 / 9.6 | `-2697 1080 -2094 38.7 -90` |
| starport | 6.8M, 42% | 3928 -486 -510 | sky light | 178 / 6.0 | `3928.5 -646 -382 38.7 90` |
| scommons | 6.2M, 57% | 380 2420 -30 | surface light `senderstation/win2` 50 | 174 / 4.1 | `540 2420 98 38.7 180` |
| sphere | 5.5M, 36% | 3400 -1718 2216 | bounce | 155 / 0.0 | `3400 -1558 2232 5.7 -90` |
| braintrain-b | 4.5M, 36% | 3513 -2841 -2887 | surface light `sunder/sun_gt11` 50 | 156 / 1.6 | `3353 -2841.4 -2796.1 29.5 0` |
| commiteon | 4.0M, 67% | 2080 -1312 57 | sky light | 218 / 0.4 | `2080.2 -1152.1 184.3 38.5 -90` |
| commbase | 4.0M, 25% | 659 3084 206 | bounce | 183 / 1.4 | `498.7 3084.3 332.6 38.3 0` |
| cinedem | 3.9M, 60% | -2360 2832 3826 | bounce | 172 / 0.0 | `-2360 2992 3954 38.7 -90` |
| sunstrip | 3.7M, 23% | 2644 1854 -946 | sky light | 190 / 6.9 | `2644 2009.7 -890.7 19.4 -90` |
| sphere3 | 3.2M, 66% | -731 3153 2864 | sky light | 144 / 1.2 | `-874.9 3220.5 2893.7 10.5 -25.1` |
| votowne | 2.9M, 26% | -1662 -272 442 | surface light `votowne/toplamp1` 2500 | 123 / 8.2 | `-1502 -272 458 5.7 180` |
| onegatestn | 2.5M, 28% | 1800 -776 446 | surface light `bricks2/snoblight` 3000 | 156 / 9.5 | `1800 -616 318 -38.7 -90` |
| sexmach | 2.3M, 40% | -584 408 2 | surface light `sexmachine/lite3` 20000 | 104 / 8.9 | `-424 408 130 38.7 180` |
| cine1 | 2.2M, 12% | 2402 -718 2568 | surface light `routubes/litebar` 6000 | 184 / 23.7 | `2562 -718 2584 5.7 180` |
| crevice | 1.8M, 74% | -1253 -911 3919 | sky light | 156 / 0.0 | `-1306.6 -872.5 3963 33.7 -35.5` |
| baltown | 1.4M, 22% | 658 -2238 601 | surface light `ballotine/slime01a` 500 | 111 / 9.1 | `658 -2078 617 5.7 -90` |
| fortress2 | 1.2M, 7% | -1209 -175 -378 | surface light `naude/naude-blue-5` 4000 | 98 / 4.7 | `-1369 -175 -506 -38.7 0` |

Surface-light gaps by texture (sum over maps): `senderstation/win2` (50, scommons/scommonnight windows),
`votowne/toplamp1` (2500, 68 clusters), `sexmachine/lite3` (20000), `naude/naude-blue-5` (4000, fortress1/2),
`sunder/sun_light` (1000–2000, starport/braintrain-b), `routubes/litebar` (6000), `bricks2/snoblight` (3000),
`levant/hshoplit2` (10000, hephlava), `hive/lite4` (5000). Most have light values far above 1500, where the emissive
intensity is clamped at 15: qrad's surface light grows with the value, the Remix emission does not. A per-texture
intensity in `maps/emissive_intensity.tsv` (or a higher clamp) is an alternative to fill lights for these.

`--styled` adds *styled light* clusters: fortress2 (`detta/plasma`, -3288 -264 -390), tours (above), temple,
levant1, levant2.

## To test first

1. slounge booth: the `.estyles` collision (or the candidate `add -1112 1504 109 0.95 0.96 1.00 72 0`); view
   `slounge gap5 -1082 1512 104 12.5 180`.
2. vendomart, same lamp and collision: `add 38 192 109 0.95 0.96 1.00 108 0`; view `vendomart gap1 84 304 139.6 38.7 -90`.
3. votowne `toplamp1` street lamps: `add -1540 -316 559 0.70 0.95 1.00 868 0`; view `votowne gap0 -1502 -272 458 5.7 180`.
4. sexmach `lite3` (value 20000): `add -656 400 104 0.93 0.94 1.00 800 0`; view `sexmach gap0 -424 408 130 38.7 180`.
5. fortress2 `naude-blue-5`: `add -1312 272 -480 0.65 0.87 1.00 1047 0`; view `fortress2 gap0 -1369 -175 -506 -38.7 0`.

## Limits

Direct light only, no Remix bounce, sky or Numos; luminance only; brush entities (doors, func_wall) neither block
nor are traced; the emissive colour is the texture mean, while Remix uses the texture as a mask. The per-map `K` makes
the ratio relative: a map whose lighting is entirely one kind of gap is underestimated. The suggested intensities
assume a pool about as large as the cluster and are starting points only. Views are not checked against the PVS.
