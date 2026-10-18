# More ideas from other RTX Remix projects (round 2, October 2026)

> Historical idea survey. Implementation status and ordering were reconciled
> on 2026-10-18 in [STATUS.md](STATUS.md), [TODO.md](TODO.md) and
> [PLAN.md](PLAN.md). Several proposals below are already implemented; source
> project capability descriptions are historical, not newly verified claims.


A second sweep of RTX Remix projects on GitHub, looking for things that can be brought to Anachronox
(QindieGL + Remix 1.5.2 under Proton). [IDEAS.md](IDEAS.md) covers the first sweep (QuakeRTX,
DeusExEchelonRenderer, q3-rtx-demo, whisperglen's repos); this file only lists what is new.

Effort: **S** = config/script only, **M** = QindieGL change or new tool, **L** = large new subsystem.
Status of what already exists is in [TODO.md](TODO.md) and [RESULTS.md](RESULTS.md).

## Sources

| Project | Game / engine | What we can learn from it |
|---|---|---|
| [xoxor4d/gta4-rtx](https://github.com/xoxor4d/gta4-rtx) | GTA IV | game lights -> Remix lights with an override file, Remix variables driven by game state, marker meshes, installer, separate base mod + AutoPBR mod |
| [xoxor4d/p2-rtx](https://github.com/xoxor4d/p2-rtx), [l4d2-rtx](https://github.com/xoxor4d/l4d2-rtx), [remix-comp-projects](https://github.com/xoxor4d/remix-comp-projects) | Source, Bioshock, SWAT 4, FEAR … | **per-map Remix config files**, keyframed lights on events, anchor meshes, anti-culling |
| [xoxor4d/gta4-rtx-autopbr-mod](https://github.com/xoxor4d/gta4-rtx-autopbr-mod) | GTA IV | automatic PBR materials generated from the game's own textures |
| [mmdanggg2/D3D9DrvRTX](https://github.com/mmdanggg2/D3D9DrvRTX) | Unreal Engine 1 (UT, Unreal, Deus Ex, Undying …) | tunable light formula, **stable "hash textures" for procedural textures**, per-level properties, animated anchors, translucent hack |
| [gebdag/gta2-rtx-remix](https://github.com/gebdag/gta2-rtx-remix) | GTA2 | **lights generated from game events** (explosions, fire, gunfire) via the Remix API |
| [gebdag/carmageddon2-rtx-remix](https://github.com/gebdag/carmageddon2-rtx-remix) | Carmageddon 2 | sun as a Remix distant light, car/street lights via the Remix API, emissive maps shipped as a Remix mod |
| [RemixProjGroup/dxvk-remix](https://github.com/RemixProjGroup/dxvk-remix) ("Remix Plus") | runtime fork | Numos sky/weather/time of day, 8 tonemappers, FSR 3.1, skinning fixes, plugin APIs |
| [NVIDIAGameWorks/ComfyUI-RTX-Remix](https://github.com/NVIDIAGameWorks/ComfyUI-RTX-Remix) | toolkit | run tagged ComfyUI workflows from the Remix Toolkit (texture in, PBR maps out) |
| [BlueAmulet/SourceRTXTweaks](https://github.com/BlueAmulet/SourceRTXTweaks) | Source | binary patches for frustum/vis/backface culling (light leaks, missing shadows) |
| [OpenRenderCollective/OpenRemix](https://github.com/OpenRenderCollective/OpenRemix) | runtime alternative | Remix-API-compatible path tracer with native Linux builds (young, AI-generated code) |
| [Ekozmaster/NFSU2-RTX-Remix](https://github.com/Ekozmaster/NFSU2-RTX-Remix), [Xenthio/RTXLauncher](https://github.com/Xenthio/RTXLauncher) | NFSU2, Garry's Mod | mod repo with git LFS for assets; one-click installer/launcher |

## 1. Lights

### 1.1 Dynamic lights from the game (`dlights`) through the Remix API — M, high value
*From gta2-rtx-remix (explosions, fire, gunfire) and gta4-rtx (all game lights translated).*
Quake 2 renderers get the frame's dynamic lights in `refdef_t` (`num_dlights`, `dlights[]`: origin,
colour, intensity) through `R_RenderFrame`, which `ref_gl.dll` hands to the game in its `GetRefAPI`
table. QindieGL already hooks `ref_gl.dll!ref_SetMapName`; hooking `R_RenderFrame` the same way gives
every muzzle flash, explosion and spell effect as a real path-traced light.
- Create/destroy Remix sphere lights per frame (reuse a pool, like `maplights` styles do).
- Replaces the flashblend approach in QindieGL PR #6, which only draws blended sprites.
- First step: confirm Anachronox's `refdef_t` layout (it is a modified Q2 renderer) by logging the
  struct in a battle.

### 1.2 Tunable light formula in the ini — S/M, high value
*From D3D9DrvRTX: `brightness * (radius / LightRadiusDivisor) ^ LightRadiusExponent * LightMultiplier`.*
Our brightness swings (too dark at light²/300, too bright with linear falloff) came from having to
regenerate `.lights` files for every experiment. Store the raw BSP values (`light`, `_cone`, style) in the
`.lights` files and let QindieGL compute intensity and radius with `maplights_multiplier`,
`maplights_radius_divisor` and `maplights_exponent` from `QindieGL.ini`. Calibrating becomes an ini edit
and a map reload.

### 1.3 Light overrides and hot reload — S/M
*From gta4-rtx (override position/colour/intensity of translated lights) and p2-rtx (per-map light setup).*
- `rtx-remix/maplights/<map>.override`: move, recolour, scale or delete a generated light by index, and add
  hand-placed ones (lamp objects such as `ob_streetlight1` that have no light data, see TODO.md §2).
  Generated files stay reproducible; hand fixes survive regeneration.
- Reload `.lights`/`.override` when the file's mtime changes, so tuning does not need a map restart.

### 1.4 Keyframed / event lights — M
*From p2-rtx (spawn and animate lights on events with keyframes).*
Switchable lights (`targetname` + `spawnflags START_OFF`) are static in Remix today. The game sends
light style strings for switchable lights through `lightstyles` in `refdef_t` too; reading them in the
`R_RenderFrame` hook (1.1) turns those lights on and off and also drives the existing styles 1-11
from the game instead of our own timer.

## 2. Remix settings per map and per situation

### 2.1 Per-map Remix config — M, high value
*From p2-rtx, Black Mesa, Delta Force (xoxor4d) and D3D9DrvRTX `level_properties`.*
On `ref_SetMapName`, QindieGL reads `rtx-remix/mapconf/<map>.conf` (falling back to `default.conf`) and
applies each line with the Remix API's `SetConfigVariable`. Use it for:
- exposure / `rtx.tonemap.*` for maps that are much darker or brighter than Rowdy's,
- fog density and colour (72 maps have `fog` in worldspawn, TODO.md §2),
- `maplights_scale` per map (TODO.md §1),
- per-map sky settings.
Needs `exposeRemixApi = True`, which we already have.

### 2.2 Remix variables driven by game state — M
*From gta4-rtx (variables follow the game's timecycle) and Delta Force (night vision configs).*
Same mechanism as 2.1, but triggered by state QindieGL can see: cutscenes (letterbox bars / camera
detection), menus, underwater (`RDF_UNDERWATER` in `refdef_t.rdflags`). For example, darken exposure
in cutscenes or turn on underwater fog.

## 3. Textures and materials

### 3.1 Stable hashes for procedural textures — M
*From D3D9DrvRTX `EnableHashTextures`.*
UE1 swaps procedurally generated textures for a generated texture with a fixed hash, so they can be
replaced. The same fixes our two `proc_lava*` textures (TODO.md §2): when QindieGL sees a texture being
re-uploaded every frame with `glTexSubImage2D`, give Remix a fixed proxy texture whose hash is derived
from the GL texture name, and log it. `liquids.usda` can then give lava a proper emissive material.

### 3.2 AutoPBR for the level textures — M
*From gta4-rtx-autopbr-mod (normal/specular maps converted to Remix normal/roughness via scripts).*
Anachronox has no normal or specular maps, but we have every texture offline and know its Remix hash
(`remixhash.py`, `chuncki_texmap.tsv`). A `tools/pbr_layer.py` could:
- make a normal map from luminance (height) with a Sobel filter,
- set roughness/metallic per material class guessed from the texture path (`metal/`, `bricks/`,
  `glass/`, `wood/` …) with a small table in the repo,
- write `pbr.usda` like `hd_layer.py` does.
This also covers TODO.md §3 "PBR materials" and gives a base to tune by hand.

### 3.3 AI tools in the Remix Toolkit pipeline — S
*From ComfyUI-RTX-Remix.*
Our FLUX poster workflow (`tools/flux_refine.py`) runs against plain ComfyUI. Tagging the same workflow
with the RTX Remix nodes would let it run from the Remix Toolkit too, and the pack has nodes for
PBR map generation that could replace 3.2's heuristics for important textures. Low priority as long as
the Toolkit does not run under Linux.

### 3.4 Translucent non-solid surfaces — S
*From D3D9DrvRTX `NonSolidTranslucentHack`.*
BSP texinfo flags tell us which surfaces are `SURF_TRANS33/66` (windows, grates, force fields). Generate
translucent material overrides for those textures, like `emissive_layer.py` does for `SURF_LIGHT`, so
light passes through windows instead of being blocked.

## 4. Geometry and culling

### 4.1 Anchor meshes — M
*From gta4-rtx (marker meshes), p2-rtx and D3D9DrvRTX (animated anchors).*
QindieGL draws a small unique mesh at positions listed per map (`rtx-remix/anchors/<map>.txt`). In the
Remix Toolkit, replacements and lights can be attached to that mesh, because its hash is stable. Uses:
- lights and glow models on lamp objects that have no light data,
- an extra sky dome or clouds outdoors,
- new set dressing without editing BSP files.

### 4.2 Anti-culling check list — S
*From SourceRTXTweaks (`c_frustumcull`, `r_forcenovis`, `r_frustumcullworld`) and SWAT 4 (force BSP
surfaces near the player).* IDEAS.md §1 already has `r_novis`/`r_nocull`. If those console variables
are not enough in Anachronox, the same approach applies to `ref_gl.dll`: patch `R_CullBox` to return
false and `R_MarkLeaves` to mark every leaf. Do it as an opt-in QindieGL patch, like the Heretic 2
patches.

## 5. Runtime and image

### 5.1 Try Remix Plus — S to try
*RemixProjGroup/dxvk-remix.* A drop-in runtime with a physical sky, clouds, weather and time of day,
more tonemappers and FSR 3.1. Worth testing on outdoor maps (Sunder, Democratus), where our HD
skyboxes cannot give a sun or clouds. Check our Linux fixes (`rtx.dlfg.enable`,
`rtx.useNewGuiInputMethod`, present semaphore) against it first, and keep the stock runtime as the
default.

### 5.2 Newer DLSS — S, experimental
gta4-rtx and p2-rtx ship custom runtimes with DLSS 4.5 Ray Reconstruction 2 and optional DLSS 5
(the player supplies `nvngx_dlssnr.dll`). Since DLSS already works under GE-Proton, try one of
those runtimes for better ray reconstruction. Low priority; it means following a forked runtime.

## 6. Packaging and workflow

### 6.1 Installer and toggle script — S
*From gta4-rtx (installer/updater, `_toggle-gta4-rtx.bat`) and RTXLauncher.*
`tools/install.sh` copies QindieGL, Remix, `.trex/bridge.conf`, `rtx.conf`, map lights and the generated
layers, sets the Steam launch options and the Proton version, and `tools/toggle.sh` switches between
Remix and the original renderer (rename `opengl32.dll`, adjust `WINEDLLOVERRIDES`). Combines with
TODO.md §6 "Packaging".

### 6.2 Assets as a build, not a download — S
gta4-rtx splits code, a base mod and an AutoPBR mod; NFSU2-RTX-Remix keeps assets in git LFS. We cannot
publish the game's textures or AI versions of them, so our "base mod" should stay a script:
one command that runs `adat.py` → hashes → ESRGAN/FLUX → `hd_layer.py`/`emissive_layer.py` →
`mod.usda`, from the player's own game files.

## Suggested order

1. **1.2 tunable light formula** and **2.1 per-map Remix config**: small QindieGL changes, and they
   directly address the brightness problems we have had.
2. **1.1 dynamic lights from `refdef_t`**: the biggest visible gain in battles; can replace PR #6.
3. **1.3 overrides + hot reload** and **4.1 anchors**: needed to fix lamp objects and individual
   rooms by hand.
4. **3.2 AutoPBR** and **3.4 translucent surfaces**: material quality across all maps.
5. **3.1 procedural texture hashes**: fixes the lava.
6. **5.1 Remix Plus** test on an outdoor map.
7. **6.1/6.2 packaging** once the above has settled.
