# Architecture

How the pieces fit together at run time and at build time. Current status and gaps are in
[STATUS.md](../STATUS.md); machine specifics in [HANDOFF.md](../HANDOFF.md).

## Run time

```
anox.exe (32-bit, Quake 2 engine derivative)
 ├─ gamex86.dll, anoxgfx.dll (texture manager: TEX_*, ATD procedural textures)
 └─ ref_gl.dll (renderer; Chuncki's patched copy when the texture pack is installed)
      └─ opengl32.dll  = QindieGL (this project's fork), OpenGL 1.x -> Direct3D 9
           ├─ hooks: ref_SetMapName (map changes), R_RenderView (refdef: camera, dlights),
           │         anoxgfx TEX_BindTexture/TEX_GetTexName (texture names), ChangeDisplaySettings*
           ├─ Remix API (remixapi_*): map lights, dynamic lights, SetConfigVariable
           └─ d3d9.dll = RTX Remix bridge client (32-bit)
                └─ .trex/NvRemixBridge.exe + .trex/d3d9.dll = Remix runtime (64-bit, Vulkan path tracer)
                     reads rtx.conf, rtx-remix/mods/anoxrt/mod.usda (+ sublayers)
```

- **QindieGL** turns the game's GL calls into D3D9 fixed-function calls that Remix understands (camera
  detection, smooth normals, fog states). Anachronox-specific code lives behind `[game.anox]` options in
  `QindieGL.ini`: `maplights`, `dlights`, `proctex`, `smoothnormals`, `remixapi`, `untexturedadditive`,
  `polyblendoverlay`, `styledemission`, `skipenclosingmodels`.
  Main files: `code/rmx_maplights.cpp` (map/dynamic lights, per-map settings, reload), `code/rmx_gen.cpp`
  (Remix API init, `[rtxconf.*]` variables), `code/d3d_texture.cpp` (procedural texture freeze),
  `idtech3_mixup/hooking.cpp` (Detours hooks), `code/win_imgui.cpp` (overlay).
- **Remix API layout**: stock Remix and Remix Plus fill different `remixapi_Interface` layouts; QindieGL
  initialises into a buffer and maps functions by layout (`code/d3d_global.cpp`).
- **Per-map behaviour** comes from `anox_customise.ini` next to anox.exe: `[maplights.global|<map>]` (light
  formula), `[rtxconf.default|<map>]` (Remix variables such as Numos sky, fog remap). QindieGL rereads it,
  the map's `.lights` and `.override` files when they are saved.
- **Map lights**: `rtx-remix/maplights/<map>.lights` (from the BSP) + optional `<map>.override` become Remix
  sphere/distant lights; light styles animate them. Lights are released before a D3D device is destroyed and
  rebuilt afterwards (the game replaces its device during startup/save loading).
- **Texture identity**: Remix identifies a texture by XXH3_64 of mip 0 in its D3D format (BGRA, opaque alpha
  where the image has none). Every material override in the mod is keyed by that hash (`mat_<HASH>`).

## Build time (this repository)

All generators read the user's own game files; nothing generated is committed.

| Output | Generator | Input |
| --- | --- | --- |
| `rtx-remix/maplights/*.lights` | `tools/bsp2lights.py` | `MAPS.dat` BSP entities (light, style, _cone, worldspawn sun) |
| `hd_sky.usda`, `liquids.usda` | `tools/make_layers.py` | `GRAPHICS.dat` sky faces, `TEXTURES.dat` warp textures, Real-ESRGAN x4 |
| `emissive.usda` | `tools/emissive_layer.py` | BSP `SURF_LIGHT` textures |
| `pbr.usda` | `tools/pbr_layer.py` | texture pack images (normal from luminance), roughness/metal per class from `tools/pbr_classify.py` + `tools/pbr_rules.json` |
| `proctex.usda` | `tools/proctex_layer.py` | names of frozen procedural textures (hash computed from the name) |
| `models_hd.usda` | `tools/hd_layer.py` (+ `flux_refine.py`) | `MODELS.dat` images, Real-ESRGAN x4, optional FLUX posters |
| `mod.usda` (hand-made materials) | repo file + `tools/rehash_textures.py` | `maps/chuncki_texmap.tsv` (original → pack hashes) |
| everything above | `tools/install.sh` / `install.py` | runs the steps in order, backs up replaced files |

Shared helpers: `tools/adat.py` (ADAT archives), `tools/bspinfo.py` (IBSP v38), `tools/remixhash.py` (hashes),
`tools/make_layers.py` (`dds()` writer with mips, USD header/footer).

## Test rig

`tools/anoxrig.py` runs the game in a nested Xwayland (`:7`) with Steam launch options prefixed by
`DISPLAY=:7`, loads saves or `+map <name>`, takes screenshots; `tools/anoxcapture.py` and
`tools/anoxcompare.py` record and compare views. See [docs/screenshot-regression.md](screenshot-regression.md)
and [docs/test-locations.md](test-locations.md). The rig changes Steam settings and must restore them.
