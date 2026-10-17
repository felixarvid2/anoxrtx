# anoxrtx

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
> - tools: ADAT/BSP readers, offline Remix texture hashes, layer generators, a test rig (`tools/`)
>
> Game data (textures, generated DDS files) is not included; the tools build it from your own game files.

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
   - Add `presentSemaphoreEnabled = False` to `.trex/bridge.conf`.
   - Use a QindieGL `opengl32.dll` built for Linux/MinGW (https://github.com/felixarvid2/QindieGL, see `linux/`)
     or the official one, and launch with `WINEDLLOVERRIDES="opengl32=n,b;d3d9=n,b" %command%`.

5. Map lights and per-map settings (QindieGL `maplights`): generate light files with
   `tools/bsp2lights.py <Anachronox>/rtx-remix/maplights <maps>/*.bsp`, set `remixapi = 1` and `maplights = 1` in
   `[game.anox]` of QindieGL.ini and `exposeRemixApi = True` in `.trex/bridge.conf`, and copy `anox_customise.ini`
   next to anox.exe. Its `[maplights.global]` / `[maplights.<map>]` sections set the light formula (scale,
   exponent, radius, sun_scale) and `[rtxconf.default]` / `[rtxconf.<map>]` set Remix variables per map. QindieGL
   rereads the file when it is saved, so light strength can be tuned while playing.
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
   luminance), roughness/metallic by keywords in the texture name, and thin-walled glass for the
   `SURF_TRANS33/66` glass/window textures, as `pbr.usda`; add `@./pbr.usda@` to mod.usda's subLayers.

8. HD model textures (posters, characters, objects; MODELS.dat is not covered by the level texture pack):
   `tools/adat.py extract anoxdata/MODELS.dat <dir> '*.tga'` (and *.png, *.bmp), name each image by its
   Remix hash (`tools/remixhash.py`), upscale x4 (e.g. realesrgan-ncnn-vulkan -n realesrgan-x4plus),
   keep alpha channels separately, then
   `tools/hd_layer.py rtx-remix/mods/anoxrt models_hd <upscaled dir> <alpha dir>` and add
   `@./models_hd.usda@` to mod.usda's subLayers. (2112 textures, ~430 MB of DDS; not committed.)
   Tiny posters/signs (32x64) come out smeared from ESRGAN; redraw them with FLUX.1 img2img in a local
   ComfyUI before building the layer: `tools/flux_refine.py maps/posters_flux.tsv <upscaled dir> <flux dir>`
   (denoise 0.65, ~2 min per texture on an 8 GB GPU), then copy the results over the upscaled images.
