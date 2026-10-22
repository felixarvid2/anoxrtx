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
| Skybox far too dark on a sunlit outdoor map (looks like a night sky) while the ground matches the original | Autoexposure adapts to the bright path-traced ground; the skybox has a fixed radiance (commbase/commiteon: 4–7 EV too dark) | `[rtxconf.<map>] rtx.skyBrightness` (140 there), then re-match `exposureBias`; measure sky and ground regions separately |
| Whole scene tinted purple (or another colour the original lacks) on a map with bright coloured fog | The worldspawn `fog` colour remapped to volumetric fog (waukees/greattree: yellow-white `.94 .996 .76`) | `[rtxconf.<map>] rtx.volumetrics.enableFogRemap = False` |
| Rig-camera view is completely black under Remix but fine in the original | The view is at the player start: the camera is inside the player model, which Remix path-traces around it | Move the view away from the spawn (`find_views.py --sky`/`--spots` skip spots within 96 units of it for `--sky`) |
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
| Steam ignores edited launch options | Steam rewrites `localconfig.vdf` while running | `steam -shutdown` before editing; restore afterwards |
| A background job or the shell disappears | `pkill -f` pattern matched the running command | Use `[x]` bracket patterns or checked PIDs |
| Jobs killed for low memory, ComfyUI slow | Game (~5 GB bridge) and ComfyUI/FLUX on 14 GB RAM / 8 GB GPU | Do not run them together; stop ComfyUI before game tests |
| Typed console text corrupted (Swedish symbols) | Keyboard layout mapping | Fixed in anoxrtx #27 (physical US key positions); see [console-input-check.md](console-input-check.md) |
| `+map <name>` hangs on "One moment" (e.g. whitecaves-b) | Map needs a scripted entry | Use a save from [test-locations.md](test-locations.md) instead |
