# anoxrtx

Current implementation/verification status: [STATUS.md](STATUS.md).
The [ordered implementation plan](https://github.com/felixarvid2/anoxrtx/blob/main/PLAN.md)
includes screenshot regression, event lighting, BSP/PVS, dynamic emission,
PBR classification, anchors, environment transitions and rain/wetness.
Capture/comparison tools and the startup map-light lifecycle correction are
now implemented; see the [controlled lighting report](https://github.com/felixarvid2/anoxrtx/blob/main/docs/startup-lighting-check.md)
and [capture workflow](https://github.com/felixarvid2/anoxrtx/blob/main/docs/screenshot-regression.md).
Other entries are planned extensions; remaining visual coverage is explicit
in the status table.

> **This is a fork of [vinevi1/anoxrtx](https://github.com/vinevi1/anoxrtx) by vinevi1**, an RTX Remix mod for
> Anachronox. It adds:
> - **Linux support**: runs under Steam + Proton with fixes in `rtx.conf` and `.trex/bridge.conf` (section 4) and
>   the Linux build of QindieGL ([felixarvid2/QindieGL](https://github.com/felixarvid2/QindieGL))
> - DLSS (DLAA by default) under Proton
> - map lights from the BSP files, with light styles, sun, spotlights, per-map settings and hand overrides
>   (`tools/bsp2lights.py`, `anox_customise.ini`), and the game's dynamic lights
> - HD skies, liquid and emissive materials, PBR materials (normal maps, roughness, glass) for the level textures
> - support for Chuncki's 4x level texture pack (texture hashes remapped)
> - HD model textures, with AI-redrawn posters (Real-ESRGAN + FLUX.1 via ComfyUI)
> - optional [Remix Plus](https://github.com/RemixProjGroup/dxvk-remix) runtime with a physical sky (Numos) on the
>   outdoor maps, and replaceable lava (procedural textures frozen by QindieGL)
> - tools: ADAT/BSP readers, offline Remix texture hashes, layer generators, a test rig (`tools/`)
>
> Game data (textures, generated DDS files) is not included; the tools build it from your own game files.

Documentation: [docs/README.md](docs/README.md) (map of all docs), [STATUS.md](STATUS.md) (current state),
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Quick install (Linux, Steam + Proton)

```
git clone https://github.com/felixarvid2/anoxrtx && cd anoxrtx
tools/install.sh --chuncki ~/Downloads/Chunckis_4x_AI_upscaled_Anachronox_textures_v.0.9.2.zip --steam
```
This builds everything from your own game files: QindieGL (cloned and built with
[llvm-mingw](https://github.com/mstorsjo/llvm-mingw), or `--qindiegl opengl32.dll`), the RTX Remix runtime
(`--remix stock`, default, or `--remix plus`), configs, map lights, HD skies/liquids/model textures (Real-ESRGAN,
downloaded), emissive and PBR materials, the lava material and mod.usda, and sets the Steam launch options
(`--steam`; select GE-Proton for the game yourself). Chuncki's pack has to be downloaded from ModDB first; without
it the level textures stay original and the PBR/lava layers are skipped. `--ge GraphicalEnhancements0.3.zip` also
installs that mod's model and sky textures (step 11 below). Steps can be run on their own, e.g.
`tools/install.sh lights mod`; `--help` lists them. Replaced files go to `<game>/anoxrtx-backup/`.
`tools/toggle.sh off|on` switches between RTX Remix and the plain game. Needs: python3 (venv), git, cmake, a
Vulkan-capable NVIDIA GPU; the first full run takes a while (texture upscaling).

The sections below describe what the installer does, step by step.


Notes:

1. For game to display correctly install:
https://github.com/whisperglen/QindieGL/releases/
Also add:
```
enable_camera_detection = 1
camera_detection_mode = 1
```
to QindieGL.ini that fixes post effects such as eye adaptation, fixes transforms when exporting captures.

2. Add the lines:
```
set r_nocull 1
set gl_cull 0
set gl_cleartoblack 1
```
to /anoxdata/CONFIGS/Default.cfg
That ensures culling is disabled as much as possible.
The last line prevents green background leaking through geometry.

3. The game relies a lot on id tech phong shading. So most character models have bad normals.
I raise roughness and metalicity of character materials to the max to mask the problem. 

4. Linux (Steam + Proton, tested with GE-Proton 11-9 and an RTX 5060):
   - `rtx.conf` disables DLSS frame generation (`rtx.dlfg.enable`, `rtx.dlfg.enablePresentMetering`); with it on,
     the Remix server hangs inside Present under Wine.
   - `rtx.useNewGuiInputMethod = False`: Remix' new GUI input method puts an invisible (alpha 0) layered window
     over the game. Wine/X11 shows it as an opaque white window, so the game looks white after the first frame.
   - Add `presentSemaphoreEnabled = False` to `.trex/bridge.conf`, and `clientChannelMemSize = 201326592`
     (192 MB; with the default 96 MB the bridge can deadlock while a map loads).
   - Use a QindieGL `opengl32.dll` built for Linux/MinGW (https://github.com/felixarvid2/QindieGL, see `linux/`)
     or the official one, and launch with `WINEDLLOVERRIDES="opengl32=n,b;d3d9=n,b" %command%`.

5. Map lights and per-map settings (QindieGL `maplights`): generate light files with
   `tools/bsp2lights.py <Anachronox>/rtx-remix/maplights <maps>/*.bsp`, set `remixapi = 1` and `maplights = 1` in
   `[game.anox]` of QindieGL.ini and `exposeRemixApi = True` in `.trex/bridge.conf`, and copy `anox_customise.ini`
   next to anox.exe. Its `[maplights.global]` / `[maplights.<map>]` sections set the light formula (scale,
   exponent, radius, sun_scale) and `[rtxconf.default]` / `[rtxconf.<map>]` set Remix variables per map. QindieGL
   rereads the file when it is saved, so light strength can be tuned while playing.
   With `bsp2lights.py --events` (the installer's default) lights keep their map style (1–63) and START_OFF
   lights are kept; QindieGL then follows the game's own light styles (flicker in sync, switches turn lights on
   and off; `event_lights` in the ini). In-game diagnostics: press F8 (or Alt+C) for the Anachronox panel
   (map, camera, lights, Remix API state, light styles). Format: [docs/event-light-format.md](docs/event-light-format.md).
   Hand fixes per light go in `rtx-remix/maplights/<map>.override` (also reloaded while playing): `N off`,
   `N scale S`, `N color R G B`, `N move DX DY DZ`, `N radius R`, `sun off`, `sun scale S`, and `add <light line>`
   for new lights (e.g. lamp objects without light data). To find N, save the file in the game and read
   "camera at X Y Z" in QindieGL.log (needs `dlights = 1`), then run
   `tools/lights_near.py rtx-remix/maplights/<map>.lights X Y Z`.
   With `dlights = 1`, muzzle flashes, explosions and spells also become Remix lights (`dlight_scale`,
   `dlight_radius` in the ini).

6. Chuncki's 4x AI upscaled level textures (ModDB, v0.9.2) together with this mod:
   - Install as its readme says (Steam version: rename `anoxdata/TEXTURES.dat` instead of `textures.pac`; the
     pack's patched `ref_gl.dll` keeps all exports, QindieGL's hooks keep working).
   - All level textures get new Remix hashes, so material overrides and texture lists in `mod.usda`,
     `liquids.usda` and `rtx.conf` must be rewritten to the new hashes:
     `python3 tools/rehash_textures.py apply maps/chuncki_texmap.tsv rtx.conf rtx-remix/mods/anoxrt/mod.usda rtx-remix/mods/anoxrt/liquids.usda`
     (the map was made with `tools/rehash_textures.py map anoxdata/TEXTURES.dat.orig anoxdata/textures ...`).
     Without this, e.g. the glowing light strips in Rowdy's bar go dark.
   - Note: Steam "verify files" restores TEXTURES.dat; rename it again afterwards.

7. Approximate PBR materials for the level textures (after 6, since the hashes come from the loose pack):
   `tools/pbr_layer.py rtx-remix/mods/anoxrt <Anachronox> <maps>/*.bsp` writes normal maps (from the texture's
   luminance), roughness/metallic per material class, and thin-walled glass for the
   `SURF_TRANS33/66` glass/window textures, as `pbr.usda`; add `@./pbr.usda@` to mod.usda's subLayers.
   The classes come from `tools/pbr_classify.py` with the reviewable rules in `tools/pbr_rules.json`
   (exceptions, BSP flags such as sky/liquid/light faces, name keywords). `tools/pbr_classify.py OUTDIR
   <maps>/*.bsp [--classes jev_classes.json]` (or `pbr_layer.py --report DIR`) writes `pbr_report.md`: class
   counts and the unclassified, weak, conflicting (rule vs Jev) and model-sourced textures, largest face count
   first. `--deepseek` asks DeepSeek (text only: texture paths and usage numbers; cached in
   `~/.cache/anoxrtx/deepseek_pbr.json`) for the textures the rules leave open; `pbr_layer.py --ai` applies
   those suggestions, marked as such in the report. `--deepseek-vision <Anachronox>` lets DeepSeek (`deepseek-flash`)
   look at the textures: 5x5 contact sheets of 128 px thumbnails plus path and usage numbers, one class per texture
   (about 0.12 USD for ~800 textures; cached in `~/.cache/anoxrtx/deepseek_vision.json`). With `--vision` (and in
   the installer, when that cache and the Jev classes exist) a strong name rule plus a high-confidence image answer
   overrule Jev ("rule+vision", 68 textures, e.g. `bricks2/bricksrock*` stone instead of metal); otherwise the image
   answers are only listed in the report.
   Better roughness/metallic: `tools/jev_classify.py <Anachronox> ~/.cache/anoxrtx/work/jev_classes.json
   <maps>/*.bsp --gemini` lets Gemini describe the textures (128 px contact sheets; free tier) and TypeSafe Jev
   decide material, roughness, metal and glow (about 0.12 USD for all textures; cached). `pbr_layer.py
   --classes` (and the installer, when that file exists) then uses those values instead of name keywords.
   `emissive_layer.py --classes` also makes the textures Jev rates as glowing (>= 0.7, not already SURF_LIGHT)
   emissive, bright parts only, in their own layer `emissive_jev.usda`.

8. Remix Plus (optional, tested with v1.5.1 x86 under GE-Proton 11-9): unzip
   `Remix_Plus_v1.5.1_x86_games_release.zip` over the game folder (replaces `d3d9.dll` and `.trex/`; keep a copy
   of the stock ones and of `.trex/bridge.conf`, which must be copied back). Needs the felixarvid2/QindieGL build
   from PR #15 or later; older builds crash at startup with it (its Remix API layout differs).
   - Its first start shows a "Welcome to RTX Remix" dialog that waits for a click, and crash/usage reporting to
     NVIDIA defaults to on. To decide up front, create
     `<prefix>/drive_c/users/steamuser/AppData/Local/NVIDIA/RTXRemix/user_settings/<xxh3 of "S:\steamapps\common\Anachronox">.conf`
     with `neverShowFirstUseGuide = True`, `allowCrashReporting = False`, `allowUsageTracking = False`.
     Do not use `rtx.automation.disableBlockingDialogBoxes`: it is for NVIDIA's CI and grants the consent.
   - The Numos sky (`rtx.skyMode = 1`) is off on every map: on the maps with an ArghRad sun it replaced the
     original skyboxes (sunstrip, starport, comhills, baltown) or made no visible difference (baltownr), so the
     map light sun lights them instead. It can be turned on per map in `anox_customise.ini` (`[rtxconf.<map>]`).
   - For testing, Steam launch options `%command% +map <name>` start straight into a map.

9. Lava (QindieGL `proctex = 1`; implemented, not yet seen in the game – see STATUS.md): the Levant lava is generated every frame, so Remix cannot replace it.
   QindieGL freezes it to a flat colour derived from its name; `tools/proctex_layer.py rtx-remix/mods/anoxrt
   <Anachronox>` writes `proctex.usda` with an emissive HD lava material for those hashes (add `@./proctex.usda@`
   to mod.usda's subLayers). QindieGL.log prints the hash when it freezes a texture; it should match the one the
   tool prints.

10. HD model textures (posters, characters, objects; MODELS.dat is not covered by the level texture pack):
   `tools/adat.py extract anoxdata/MODELS.dat <dir> '*.tga'` (and *.png, *.bmp), name each image by its
   Remix hash (`tools/remixhash.py`), upscale x4 (e.g. realesrgan-ncnn-vulkan -n realesrgan-x4plus),
   keep alpha channels separately, then
   `tools/hd_layer.py rtx-remix/mods/anoxrt models_hd <upscaled dir> <alpha dir>` and add
   `@./models_hd.usda@` to mod.usda's subLayers. (2112 textures, ~430 MB of DDS; not committed.)
   Tiny posters/signs (32x64) come out smeared from ESRGAN; redraw them with FLUX.1 img2img in a local
   ComfyUI before building the layer: `tools/flux_refine.py maps/posters_flux.tsv <upscaled dir> <flux dir>`
   (denoise 0.65, ~2 min per texture on an 8 GB GPU), then copy the results over the upscaled images.

11. Graphical Enhancements 0.3 (optional, ModDB `anachronox-graphical-enhancements`; installer: `--ge ZIP`):
   upscaled model and sky textures as loose files in `anoxdata/models` and `anoxdata/graphics`, which the game
   loads instead of the MODELS.dat / GRAPHICS.dat copies, plus an `entity.dat` that makes four billboards
   `charfly` instead of `noclip`. Its 12 level textures (`bricks/01comp`, `02comp`, the `sexmachine` bottles and
   glasses, all `#alphatest`) are the originals at the original size with a solid alpha instead of the grey one, so
   the game no longer cuts holes into them. Chuncki's 4x images keep the grey alpha; `tools/merge_alpha.py
   anoxdata/textures <GE>/anoxdata/textures anoxdata/graphical_enhancements_texmap.tsv` gives them GE's alpha
   (scaled up, originals kept as `*.orig`), and `rehash_textures.py add` with that map moves the overrides along
   (`textureinfo.dat` is identical to the game's and not needed). The loose textures have new Remix hashes:
   `tools/rehash_textures.py add maps/ge_texmap.tsv rtx.conf rtx-remix/mods/anoxrt/{mod,pbr,emissive}.usda`
   adds them next to the old ones (sky list, decals, the ship's emission, material overrides; some originals are
   identical and map to several GE files, which `add` all keeps), and
   `... add maps/ge_texmap.tsv rtx-remix/mods/anoxrt/models_hd.usda --only maps/posters_flux.tsv` keeps the
   FLUX posters. `models_hd.usda` / `hd_sky.usda` are otherwise not rehashed, so GE's own upscales show where it
   has one. To remove it, delete the files listed in `anoxdata/graphical_enhancements_manifest.txt` and rename
   the `anoxdata/textures/**/*.png.orig` files back.

## Test rig (Linux)

`tools/anoxrig.py` needs Python with `python-xlib` and Pillow. It defaults to the
nested X display `:7` (`ANOX_DISPLAY` overrides it). Follow `HANDOFF.md` to set up
the nested session and restore Steam's launch options afterwards.

For a dedicated environment:

```sh
python3 -m venv ~/.cache/anoxrtx/rig-venv
~/.cache/anoxrtx/rig-venv/bin/pip install python-xlib Pillow
```

Use that environment's `bin/python` for the commands below.

```sh
python tools/anoxrig.py start 90
python tools/anoxrig.py key Escape
python tools/anoxrig.py list-saves
python tools/anoxrig.py load-save steamuser/1
python tools/anoxrig.py hold 2 w
python tools/anoxrig.py hold 1 w a
python tools/anoxrig.py shot movement-check
python tools/anoxrig.py stop
```

`start` waits for a mapped game window with visible, nonuniform content for at
least one second. This works with Remix Plus even when it emits no `Camera cut`
message. The output distinguishes visible content from a confirmed camera; it
does not prove that a level has finished loading. Old camera messages cannot
confirm a new run, and the rig no longer deletes logs. A timeout exits nonzero
with the observed window state; for an intro stuck on black, send `key Escape`
from another terminal. The default timeout is 180 seconds.

`key`, `chord`, and `hold` focus the game before sending XTest keyboard input.
Use `hold SECS KEY...` for movement (up to 60 seconds); `key` remains a short tap
and `chord` keeps the `ANOX_HOLD` duration override. Invalid keys are rejected
before any input is sent, and held keys are released on completion, Ctrl+C, or
SIGTERM. This fixes game movement; Remix overlay/capture hotkeys remain a
separate, unverified input path. `move` controls the mouse, not the player.

`list-saves` inspects local saves and prints each `PROFILE/SLOT`, description,
map, and SHA-256 fingerprint. `load-save PROFILE/SLOT [SECS]` restores a chosen
save in an already-running game (default timeout 120 seconds). Loading replaces
the current unsaved game state. It does not write or replace save files, alter
configs, restart Steam, or change launch options.

The rig opens the developer console using the game's Alt+Shift+F10 shortcut when
needed, submits `loadgame`, verifies a fresh console transcript, closes the
console so the saved camera can settle, and reports position/yaw. It restores
the previous developer-mode setting and removes its temporary console dumps.
The console key defaults to raw X keycode 49; set `ANOX_CONSOLE_KEY` if needed.
Recognition targets this game's default gold-text console and build footer;
custom fonts/layouts can require adjustment. If recognition fails, no load
command is sent. Wait for initial material loading to finish before trying it.

Console text uses the game's US physical key positions, resolved from XKB key
names with `xkbcomp`. This also works when Xwayland reports Swedish symbols;
symbol-based typing can turn `_`, `;`, and `/` into `?`, `<`, and `&` in the
game. The rig does not change your keyboard layout. Console input requires
`xkbcomp`, `xset`, and enabled X autorepeat; unavailable key positions or repeat
settings are rejected before editing the prompt.

The installed game build prints `LoadGame2: Aborted` even after restoring a
save, so that line alone is not a failure. The rig checks the requested filename,
restored save lumps, fresh read errors, a visible scene, and settled `viewpos`.
Map-light reload messages alone cannot prove a save loaded, especially when
reloading the same map. See [repeatable test locations](docs/test-locations.md)
for baseline selection and before/after captures.

Regression checks, without Steam or a running X server:

```sh
python -m unittest discover -s tools -p 'test_anoxrig.py'
python -m unittest discover -s tools -p 'test_pbr_classify.py'
```


Automatic in-game check: `tools/anoxcheck.py OUTDIR MAP... [--ab LAYER]` starts each map (`+map`), takes two
screenshots and checks Remix crash, black/white frames, Remix log errors about mod files, map-light
load/create/draw results and light styles. With `--ab LAYER` every map is run with the layer on and off
(mod.usda restored afterwards) and `OUTDIR/compare_<map>.png` shows on, off and the difference. Writes
`report.md`/`report.json`; exit status 1 when a check fails. About 2 minutes per map and run.
`--views FILE` shoots chosen views per map through QindieGL's rig camera (`rtx-remix/rigcam.txt`; lines
`MAP NAME X Y Z PITCH YAW` from `tools/find_views.py MAP.bsp TEXTURE[,…]`, which places the camera in open space
in front of surfaces using that texture), so surfaces the player cannot reach in the rig can be checked;
`--ab-cfg "set CVAR VALUE"` A/B-tests a config line and reports frame times. Culling result:
[docs/culling-check.md](docs/culling-check.md). `--ab-original` compares with the original rasterised renderer; exposure was matched
to it per map: [docs/exposure-match.md](docs/exposure-match.md).