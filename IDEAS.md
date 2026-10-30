# Ideas for improving RTX Remix in Anachronox

> Historical idea survey. Implementation status and ordering were reconciled
> on 2026-10-18 in [STATUS.md](STATUS.md), [TODO.md](TODO.md) and
> [PLAN.md](PLAN.md). Several proposals below are already implemented; source
> project capability descriptions are historical, not newly verified claims.


Collected from other RTX Remix projects on id Tech 2 / id Tech 3 (and two other engines with very
relevant renderer work), compared with what we have seen running Anachronox through QindieGL + Remix 1.5.2.
Each idea says where it comes from and roughly how much work it is.

Legend: **effort** S = config only, M = QindieGL change, L = binary patch of the game / new code.

## Sources

| Project | Engine / game | Type | What is useful |
|---|---|---|---|
| [whisperglen/QindieGL](https://github.com/whisperglen/QindieGL) | many (Q2, Heretic 2, RTCW, FAKK2, Alice, JK2) | OpenGL->D3D9 wrapper, Remix-oriented | camera detection, per-game profiles, Remix API lights, Heretic 2 binary patches |
| [mstewart248/QuakeRTX](https://github.com/mstewart248/QuakeRTX) | Quake 1 (Quakespasm) | native D3D9 fixed-function backend for Remix | static buffers, per-vertex model normals, real skybox, lightmaps off |
| [onnoj/DeusExEchelonRenderer](https://github.com/onnoj/DeusExEchelonRenderer) | Deus Ex (Unreal 1) | fixed-function renderer for Remix | game lights -> Remix lights, stable hashing, sky in the same pass, `rtx.conf` |
| [PPBWoodBoy/q3-rtx-demo](https://github.com/PPBWoodBoy/q3-rtx-demo) | Quake III (Quake3e) | mod | required in-game settings (vertex lighting, no dynamic lights, HQ sky) |
| [whisperglen/RTCW-files](https://github.com/whisperglen/RTCW-files), [heretic2-files](https://github.com/whisperglen/heretic2-files) | RTCW, Heretic 2 | mod/config repos | layout of a Remix mod repo for a QindieGL game |
| Quake II RTX Remix ([ModDB](https://www.moddb.com/rtx/view/quake-2)) | Quake 2 | mod, uses the QindieGL fork | console vars `r_nocull`, `r_novis`, `r_clear`, polyblend (search snippet only, page not readable) |
| Jedi Outcast RTX Remix demo ([ModDB](https://www.moddb.com/mods/star-wars-jedi-knight-ii-jedi-outcast-rtx-remix)) | id Tech 3 | mod via QindieGL | "heavy config customisation", proof that QindieGL + Remix works for whole levels |
| [xoxor4d/remix-comp-base](https://github.com/xoxor4d/remix-comp-base) | D3D9 games | compat framework | patterns for Remix API usage and per-frame Remix variables |

Verified directly: QuakeRTX cvars `d3d9_modelnormals`, `d3d9_lightmaps`, `d3d9_skybox` and the comment in
`Quake/d3d9_backend.h` about `D3DUSAGE_DYNAMIC` buffers; the DeusExEchelonRenderer `rtx.conf` lines below;
QindieGL's game profiles in `msvc/QindieGL.ini`. The ModDB pages could not be read (HTTP 403).

## 1. Quick wins (effort S)

1. **Copy QindieGL's Quake 2 / Heretic 2 profile options into `[game.anox]`.**
   Today `[game.anox]` only has `enable_camera_detection = 1` and `camera_detection_mode = 1`. The Quake 2
   and Heretic 2 profiles also use:
   ```ini
   orthoskipuntextureddraws = 1  ; untextured 2D quads (cutscene bars, damage flashes) are not drawn
   depthOffDisablesWrites = 1    ; helps Remix detect UI when the game turns depth off for 2D
   ```
   Anachronox has letterbox bars in cutscenes and a lot of 2D dialog UI, so both are worth testing.
   (`remixapi = 1` only helps once something feeds lights to QindieGL, see 3.1.)

2. **Game console settings, like the Quake 2 and Quake 3 Remix mods.** Already in the README: `r_nocull 1`,
   `gl_cull 0`, `gl_cleartoblack 1`. Add and test:
   - `r_novis 1`: draw the whole map, not just the PVS. Otherwise path-traced light and reflections leak or
     disappear at PVS borders.
   - Dynamic lights off (`gl_flashblend`/`gl_dynamic 0` in Quake 2 terms; check which cvar Anachronox uses).
     The Quake 3 remaster requires this, because GL dynamic lights are drawn as extra blended passes that
     Remix sees as unstable geometry.
   - Polyblend / screen blends off (`gl_polyblend 0`): full-screen colour flashes confuse the tonemapper.
   - Vertex lighting / lightmaps: QuakeRTX turns baked lightmaps **off** (`d3d9_lightmaps 0`) so Remix gets
     flat albedo and computes lighting itself. The mod already marks many lightmap textures
     (`rtx.lightmapTextures`); check if Anachronox can skip the lightmap pass (`gl_lightmap`/`gl_fullbright`-
     style cvars) so it is not drawn at all.

3. **`rtx.conf` keys from DeusExEchelonRenderer worth trying.** Verify each against
   [RtxOptions.md](https://github.com/NVIDIAGameWorks/dxvk-remix/blob/main/RtxOptions.md):
   ```ini
   rtx.viewModel.enable = True          ; separate first-person/held models (Anachronox has few, but cutscene close-ups)
   rtx.suppressLightKeeping = True      ; don't keep lights from earlier frames alive
   rtx.skyAutoDetect = 0                ; DeusEx: sky drawn at same depth as world confuses auto-detect
   d3d9.maxEnabledLights = 65000        ; only matters once fixed-function lights are sent (3.1)
   ```
   We already have `rtx.zUp = True` (matches Quake units). `rtx.sceneScale` is worth tuning: Quake units are
   ~2.5 cm, so lights/volumetrics may look oversized at the default.

4. **Fix the overexposed intro.** In our tests the Eidos/Ion Storm logos turn into blown-out white glows.
   Logos are emissive/additive geometry with no lights around them. Options: mark those textures as UI
   (`rtx.uiTextures`) so they skip path tracing, or clamp exposure (`rtx.autoExposure.evMinValue`,
   DeusEx uses `3`).

5. **Linux specifics (from our own debugging, see `README.md`).** Keep `rtx.dlfg.enable = False`,
   `rtx.useNewGuiInputMethod = False`. DLSS/NGX does not load under Wine by default (`NGXLoadFromPath failed`
   in the log). Try `PROTON_ENABLE_NGX_UPDATER=1` / `PROTON_ENABLE_NVAPI=1`; otherwise set an explicit
   non-DLSS upscaler so quality does not depend on a failing fallback. NRC ("Neural Radiance Cache")
   also fails to initialise under Wine and Remix falls back to importance sampling; that's fine, but the
   NRC settings in `rtx.conf` then do nothing.

## 2. QindieGL-level improvements (effort M)

1. **Stable geometry hashes for world surfaces.** QuakeRTX's rule: geometry streamed through dynamic
   buffers "rehashes every frame and cannot be replaced". QindieGL feeds Remix from its immediate-mode /
   vertex-array buffers (`DrawCallFastPath`), so the same wall may get a different hash as the PVS or draw
   order changes. whisperglen already does "stabilising geometry hashes" for FAKK2/CoD/Alice (beta).
   Port that idea to Anachronox: hash on vertex positions/UVs of each world surface, keep static surfaces in
   persistent vertex buffers keyed by that hash. This is what makes mesh/material replacement in the
   `mod.usda` reliable.

2. **Smooth model normals.** The README says character models have bad normals (Phong-shaded in the original
   engine). QuakeRTX solves the same Quake 1 problem with per-vertex normals from the model's normal index
   (`d3d9_modelnormals 1`: without it "Remix faceted the models for you"). QindieGL has smooth-normal code for
   Heretic 2 (`tests/` contains the normals recalculation test code and visualiser; Heretic 2 commit
   "fixes for smooth normals calc code"). Options:
   - compute smooth normals in QindieGL for entity draws (average face normals per position) and pass
     them as `D3DFVF_NORMAL`;
   - then the mod no longer needs maxed roughness/metalness on characters to hide faceting.
   Note: changing the vertex layout changes the hashes, so do this before authoring more replacements.

3. **Real skybox.** QuakeRTX draws the sky as a proper skybox (`d3d9_skybox 1`) because Quake's own sky
   "cannot be classified" by Remix, and drawing brush sky surfaces "kills the traced image whenever sky is in
   view". The mod already lists `rtx.skyBoxTextures`; check in the Remix debug view that sky is detected in
   every map. If not, a QindieGL option that recognises the sky draw (texture hash or depth range) and
   re-emits it as a cube around the camera would help.

4. **Lights through the Remix API.** QindieGL already has the plumbing: `remixapi = 1`,
   `code/rmx_light.cpp` with `qdx_light_add(type, ..., position, direction, color, radius)`, dynamic light /
   flashlight / corona types, and per-light overrides by hash. In Quake 2 the game itself (whisperglen's
   Quake 2 fork) calls this API; in Heretic 2 it is done by binary patches (`h2_refgl.cpp`). DeusExEchelon
   does the same for Unreal (`lightmanager.cpp` turning game lights into Remix lights).
   For Anachronox we have no engine source, so: hook ref_gl's dynamic light setup (`R_PushDlights`-style
   function, find it with a pattern like the `[game.fakk2dx]` entries) and call `qdx_light_add` for each
   dlight. That gives muzzle flashes, explosions and scripted lights real Remix lights instead of blended
   GL passes. Needs `exposeRemixApi = True` in `.trex/bridge.conf`.

5. **Port the Heretic 2 patch techniques to Anachronox.** `h2_refgl.cpp` patches "entity nocull and static
   entities backlerp", world draw calls, water and unloading of client effects. Anachronox is also a
   Quake 2-derived ref_gl, so the same targets exist. Note: `h2_refgl.cpp` is currently compiled out in our
   Linux build (it byte-copies MSVC naked functions); an Anachronox version should be written with
   position-independent asm from the start.

## 3. Game patches / content (effort L)

1. **Particles (Anachronox has its own particle system and editor, `particleman.exe`).** The mod lists
   `rtx.particleTextures` and `rtx.beamTextures`. Next step: check which particle draws come through as
   camera-facing quads and whether Remix's particle handling (`rtx.particleSoftnessFactor` is already set)
   gives stable results, or if some particles should be emissive lights instead.
   Inventory (2026-10-30, `tools/apd_textures.py`): the *.apd definitions use about 100 particle textures, 15 of
   them tagged (14 particle, 3 of these also hidden; 1 ignored). Generators draw additively by default; `genblend :
   0x0302 : 0x0303` makes them alpha-blended (e.g. `burst_04`, `smoke_01`, `water_fall`, `shell_casing_01`),
   the candidates for QindieGL's `additive_textures`. A blend trace at the spawns of 14 maps saw only four
   untagged ones (`magical_08` sunstrip, `smoke_03` hephpipes, `sewage` sewagic1a, `flare_01a` rowdys, which is
   in `ignoreTextures`). Tagging all 62 hashed untagged ones as particles changed nothing at the spawns of
   sewagic1a, rowdys and sunstrip, and on hephpipes removed a dark layer over the floor (+0.17 EV brighter, away
   from the original); not kept. Next: check `smoke_03` alone on hephpipes in a view without the console, and
   the hidden `_default`/`expon_64`/`flare_01` (drawn on hephpipes and rowdys) against the original.

2. **Water.** The Quake 2 Remix mod notes that water-heavy maps cost a lot of frame rate. Water in Quake 2
   engines is drawn with warped UV per vertex every frame, so its hash changes. Options: Heretic 2-style
   water patch (fixed UVs, let Remix animate), or tag the water textures and replace them with a Remix water
   material in `mod.usda`.

3. **Texture replacement pipeline.** Like the Quake 3 remaster (27 levels with PBR textures) and the RTCW
   files repo: keep captures and replacement textures in this repo (or a release zip), one folder per map,
   with `mod.usda` layering per area so work can be split up.

4. **Camera detection check per map.** In our Linux tests Remix reported `rejected an invalid camera`
   until QindieGL's idTech2 camera detection kicked in (`Camera cut detected on frame 12`). Anachronox
   has a scripted cinematic camera ("AnoxCam") that differs from stock Quake 2. Log camera cuts per map
   and cutscene; if detection drops out during cutscenes, extend `d3d_matrix_detection.cpp` for that path.

## Suggested order

1. Section 1 items 1-4 (config only; test one at a time, compare in the same spot of the same map).
2. Stable hashes (2.1) and smooth normals (2.2), before authoring more replacements.
3. Remix API dynamic lights (2.4).
4. Water / particles / content (section 3).
