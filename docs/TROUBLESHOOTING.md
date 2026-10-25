# Troubleshooting

Symptom → cause → fix, for problems already met in this project (Linux, Steam + GE-Proton, RTX Remix through
QindieGL). Logs: `<game>/QindieGL.log`, `<game>/rtx-remix/logs/{remix-dxvk,bridge32,bridge64}.log`; a Remix crash
shows as "The RTX Remix Runtime has encountered an unexpected issue" in `bridge32.log`. Background for the Wine
items: QindieGL [linux/REMIX-NOTES.md](https://github.com/felixarvid2/QindieGL/blob/master/linux/REMIX-NOTES.md).

## Start-up and display

| Symptom | Cause | Fix |
| --- | --- | --- |
| Game freezes on the loading screen (or stays black with `+map`), `Data Queue overwrite condition triggered` without "resolved" in `bridge32.log` | Remix bridge deadlock: the client waits for room in the data ring while the server, idle, waits for the next command. The chance rises as the ring gets smaller (servicetunnel: 48 MB 10/10, 96 MB default 3–5/10, 192 MB 0/10 loads) | `clientChannelMemSize = 201326592` in `.trex/bridge.conf` (the installer writes it) |
| Game hangs, `Still waiting on the Present semaphore` | DLSS frame generation under Wine | `rtx.dlfg.enable = False`, `rtx.dlfg.enablePresentMetering = False` in `rtx.conf`; `presentSemaphoreEnabled = False` in `.trex/bridge.conf` |
| Window turns white after the first frame | Remix' new GUI input overlay window is drawn opaque under Wine/X11 | `rtx.useNewGuiInputMethod = False` |
| Fullscreen image offset to the left | Wine's other-process window rendering in a changed display mode | QindieGL `BorderlessFullscreen = 1` (`[Settings]`) |
| Desktop session crashes on launch | `PROTON_ENABLE_WAYLAND=1` | Never set it outside the nested test display |
| Game crashes at start with Remix Plus, crash in `mINI` / `opengl32.dll` | QindieGL older than the Remix Plus API support writes past `remixapi_Interface` | Use a QindieGL build with the layout mapping (QindieGL #15 or later); `QindieGL.log` shows "Remix API: Remix Plus function layout" |
| Remix Plus shows a "Welcome to RTX Remix" dialog and ignores the game | First-use guide | Answer it once, or write the per-game settings file (README section 8); never `rtx.automation.disableBlockingDialogBoxes` (it grants data-collection consent) |
| Image blurry | Upscaler at a low quality mode | DLSS works under GE-Proton: `rtx.upscalerType = 1`, `rtx.qualityDLSS = 5` (DLAA) |

## Remix crashes while playing

| Symptom | Cause | Fix |
| --- | --- | --- |
| Crash about 2 s after a map loads or an ini is saved, `[N] common device objects were not disposed of` | NRC cannot start under Wine; a runtime `SetConfigVariable` re-enables it | Keep `rtx.integrateIndirectMode = 0` in `rtx.conf` |
| A per-map Remix variable is never applied | Key missing from `[rtxconf.default]` (map sections can only change keys listed there) | Add the key with its normal value to `[rtxconf.default]` in `anox_customise.ini` |

## Lighting and materials

| Symptom | Cause | Fix |
| --- | --- | --- |
| A glowing effect of the original (e.g. bricksd's cyan energy column) is missing or a faint dark shape | Textured additive draws (blend SRC_ALPHA, ONE) come out very faint under Remix | Per map: `rtx.enableEmissiveBlendEmissiveOverride = True` and `rtx.emissiveBlendOverrideEmissiveIntensity` (bricksd 2.5) in `[rtxconf.<map>]`. It changes every additive effect of that map. To find the draw: console `gl_log 1;wait;wait;gl_log 0` writes every GL call to `anoxdata/gl.log`; check `rtx.ignoreTextures` for the texture's hash |
| Skybox far too dark on a sunlit outdoor map (looks like a night sky) while the ground matches the original | Autoexposure adapts to the bright path-traced ground; the skybox has a fixed radiance (commbase/commiteon: 4–7 EV too dark) | `[rtxconf.<map>] rtx.skyBrightness` (140 there), then re-match `exposureBias`; measure sky and ground regions separately |
| Whole scene tinted purple (or another colour the original lacks) on a map with bright coloured fog | The worldspawn `fog` colour remapped to volumetric fog (waukees/greattree: yellow-white `.94 .996 .76`) | `[rtxconf.<map>] rtx.volumetrics.enableFogRemap = False` |
| Rig-camera view is completely black under Remix but fine in the original | The view is at the player start: the camera is inside the player model, which Remix path-traces around it | Move the view away from the spawn (`find_views.py --sky`/`--spots` skip spots within 96 units of it for `--sky`) |
| A prop model is nearly black under Remix but evenly lit in the original | The original lights it with the model light (`entity.dat` lighting 1 = renderfx 0x800 `RF_DIRLIGHT`, like characters), which path tracing lacks; QindieGL's fill light only covers characters near the camera | Add its textures to `maps/model_emission.tsv` (emission from the texture itself, ~0.5; crevicelanding ship) and rerun the emissive step. `rtx.worldSpaceUiTextures` makes it flat and too bright |
| A black box around an object (e.g. the pay2pray prayer pod), black panels in the air (temple) | A `func_fog` local fog volume: drawn untextured and additive (SRC_ALPHA/ONE), which Remix renders as dark geometry | QindieGL `untexturedadditive = 1` in `[game.anox]` (set by the installer): the box becomes translucent. To make it glow: `rtx.enableEmissiveBlendEmissiveOverride = True` per map (pay2pray, vendomart, onegate, temple, fortressgrounds, hephfactory: intensity 8; hive: 20). Needs QindieGL #34: the solid texture must have texcoords, or Remix treats the draw as untextured and ignores the override. Boxes black again only after visiting other maps (e.g. after labbuilding): the colour cache was full; needs QindieGL #35 |
| Screen turns flat grey during fades, damage flashes, under water or briefly at every map start; the original tints the view | ref_gl's R_PolyBlend draws the tint as an untextured quad 10 units in front of the camera; Remix path-traces it as an opaque lit plane | QindieGL #36 `polyblendoverlay = 1` in `[game.anox]` (set by the installer) draws it as a UI overlay; its texture hash `0x722A202F07A4B313` must be in `rtx.uiTextures` (`rtx.orthographicIsUI` is off, so UI is by texture hash only). Test: console `setblend 1 0 0 0.5 0`, reset with `setblend 0 0 0 0 0` |
| A hazy window looks like clear glass (labbuilding's haze over the city is missing) and the room reflects in it | `tools/pbr_layer.py` makes SURF_TRANS33/66 textures named glass/win/clear into clear `AperturePBR_Translucent` glass; some are haze sheets whose light texture the original blends over the view | Add the texture to `HAZE_GLASS` in `tools/pbr_layer.py` (labbuilding: `sunder/sun_glass3`) and rebuild `pbr.usda`; without a material Remix keeps the blended look |
| Laser beams (commbase sentinels) grey or faint where the original has bright yellow lines | Untextured additive quad strips; with `untexturedadditive` they get a solid texture but stay faint, and on a sunlit map the exposure is so low that indoor intensities do nothing | QindieGL #34 and per map `rtx.enableEmissiveBlendEmissiveOverride = True`, `rtx.emissiveBlendOverrideEmissiveIntensity = 150` (commbase; 40 is still orange and faint) |
| Sky behind a window or opening is opaque grey (only distant emissive surfaces show through), while the original shows the skybox | The map's worldspawn `fog` is turned into Remix volumetric fog, which fills the view to the sky (labbuilding) | `[rtxconf.<map>] rtx.volumetrics.enableFogRemap = False` in `anox_customise.ini` |
| Map lights missing | `remixapi`/`maplights` off, or no API | `[game.anox]` `remixapi = 1`, `maplights = 1`; `.trex/bridge.conf` `exposeRemixApi = True`; `QindieGL.log` "MapLights: loaded N lights" |
| Lights dim right after loading a save, fine after a reload | Lights created before the game replaced its D3D device | Fixed in QindieGL #25 (lights rebuilt after device replacement); update QindieGL |
| Scene far too dark or too bright | Light formula | Tune `scale`/`exponent`/`radius` in `[maplights.global]` or `[maplights.<map>]` while playing; per-light fixes in `<map>.override` (`tools/lights_near.py` finds indices) |
| Materials/emission missing after installing Chuncki's pack | The pack changes every level texture hash | `tools/rehash_textures.py apply maps/chuncki_texmap.tsv rtx.conf mod.usda liquids.usda` (the installer's `mod` step does this) |
| Remix warns that replacement DDS files have no mips | DDS written without a mip chain | Generate with the repo tools (`make_layers.dds()` writes full mips) |
| Starry skies lose their stars | Upscaler wipes fine points | Dark skies are excluded by `make_layers.is_dark()` |
| Space/city skies replaced by a daytime sky | Numos sky (`rtx.skyMode = 1`, Remix Plus) enabled globally | Keep it per map in `[rtxconf.<map>]` |
| Shots/explosions give double light | QindieGL `flashblendlights` and `dlights` both on | Use `dlights` only |
| Lava never logs "frozen", texture 16x16 | The texture pack's upscaled `textures/levant/proc_lava/` sources: anoxgfx needs a palette exactly 256 px wide and falls back to a 16x16 default | `tools/install.sh proctex` restores the originals from `TEXTURES.dat(.orig)` |
| Lava stays animated / flat teal-cyan | `proctex` off, or its hash differs from `proctex.usda` | `[game.anox] proctex = 1`; compare the "ProcTex: ... Remix texture hash" line in `QindieGL.log` with `tools/proctex_layer.py` output |

## Test rig and machine

| Symptom | Cause | Fix |
| --- | --- | --- |
| `start timeout after 180s: no game window on :7` on every run, anox.log not updated, Steam log shows `Fontconfig error: ... out of memory` | `/dev/shm` full: each Steam restart leaves its 25 MB `u1000-Shm_*` segments (409 files, 7.2 GB after a day of tests) | `rigsession.sh` now deletes the segments no process maps; by hand: `du -sh /dev/shm`, remove only unmapped `u$UID-Shm_*` files |
| Steam ignores edited launch options | Steam rewrites `localconfig.vdf` while running | `steam -shutdown` before editing; restore afterwards |
| A background job or the shell disappears | `pkill -f` pattern matched the running command | Use `[x]` bracket patterns or checked PIDs |
| Jobs killed for low memory, ComfyUI slow | Game (~5 GB bridge) and ComfyUI/FLUX on 14 GB RAM / 8 GB GPU | Do not run them together; stop ComfyUI before game tests |
| Typed console text corrupted (Swedish symbols) | Keyboard layout mapping | Fixed in anoxrtx #27 (physical US key positions); see [console-input-check.md](console-input-check.md) |
| `+map <name>` hangs on "One moment" (e.g. whitecaves-b) | Map needs a scripted entry | Use a save from [test-locations.md](test-locations.md) instead |
| After `anoxrig.py console map NAME` from inside another map: PAUSE screen, no world drawn, shots unusable | The game pauses while the console is up during the load and stays paused | After the load, `anoxrig.py console pause` (Escape opens the main menu; the console key only reopens the console) |
