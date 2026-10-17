# anoxrtx

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

5. Chuncki's 4x AI upscaled level textures (ModDB, v0.9.2) together with this mod:
   - Install as its readme says (Steam version: rename `anoxdata/TEXTURES.dat` instead of `textures.pac`; the
     pack's patched `ref_gl.dll` keeps all exports, QindieGL's hooks keep working).
   - All level textures get new Remix hashes, so material overrides and texture lists in `mod.usda`,
     `liquids.usda` and `rtx.conf` must be rewritten to the new hashes:
     `python3 tools/rehash_textures.py apply maps/chuncki_texmap.tsv rtx.conf rtx-remix/mods/anoxrt/mod.usda rtx-remix/mods/anoxrt/liquids.usda`
     (the map was made with `tools/rehash_textures.py map anoxdata/TEXTURES.dat.orig anoxdata/textures ...`).
     Without this, e.g. the glowing light strips in Rowdy's bar go dark.
   - Note: Steam "verify files" restores TEXTURES.dat; rename it again afterwards.

6. HD model textures (posters, characters, objects; MODELS.dat is not covered by the level texture pack):
   `tools/adat.py extract anoxdata/MODELS.dat <dir> '*.tga'` (and *.png, *.bmp), name each image by its
   Remix hash (`tools/remixhash.py`), upscale x4 (e.g. realesrgan-ncnn-vulkan -n realesrgan-x4plus),
   keep alpha channels separately, then
   `tools/hd_layer.py rtx-remix/mods/anoxrt models_hd <upscaled dir> <alpha dir>` and add
   `@./models_hd.usda@` to mod.usda's subLayers. (2112 textures, ~430 MB of DDS; not committed.)
