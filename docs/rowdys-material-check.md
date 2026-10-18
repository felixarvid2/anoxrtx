# Rowdy's lighting and material check — 2026-10-17

> Historical test record. Follow [current status](../STATUS.md) and
> [the implementation plan](../PLAN.md) for present priorities. Console input
> was subsequently fixed and accepted in [PR #27](console-input-check.md);
> initial post-save-load lighting remains a separate open investigation.


This check covers two stationary indoor save views, not the outdoor, water,
lava, combat-light, or sun-direction tasks. See [test locations](test-locations.md)
for the save workflow and remaining location coverage.

## Setup and method

- RTX 5060 Laptop, driver 595.104.02, GE-Proton 11-9, nested Xwayland `:7`.
  The installed runtime is recorded in the handoff as Remix Plus 1.5.1; its
  startup log identifies `DXVK_Remix: remix-main`, without proving a release number.
- Captured game-window geometry: 1920 × 1107. Both views use the same runtime,
  texture pack, output geometry, and baseline configs.
- QindieGL: `remixapi`, `maplights`, `dlights`, `proctex`, and `smoothnormals`
  enabled; wrapper `maplights_scale = 100`. Customise defaults: scale 1,
  exponent 2, reference intensity 300, radius 4. Fog and fog-color remapping on.
- Remix: graphics preset 2, two path bounces, DLSS upscaler with DLAA quality,
  `integrateIndirectMode = 0`, frame generation off, fallback light off.
- Each case restores `steamuser/1` at `(1168, 1235, 336)`, yaw 9, and
  `steamuser/2` at `(756, 1289, 8)`, yaw 11. A fresh nonce-bounded console
  transcript verifies each load. The saved positions/yaw must agree before
  comparison; pitch is not reported by the rig.
- After console closure, wait eight seconds, then take three frames two seconds
  apart. Repeat the initial baseline to estimate ordinary frame variation.
  NPCs, animation, exposure, and temporal rendering are not frozen.
- Restore baseline files before each diagnostic. `light075` is hot-reloaded
  with explicit QindieGL log confirmation; `light0` and material diagnostics restart the game
  and wait 30 seconds after visible startup before loading the test saves.

The save fingerprints are:

```text
steamuser/1  514b5e01fba112fff82830eb6bbd4cba1ce4c0a8080eb0ced825a491d903124f
steamuser/2  1447411179f7d3bed0a457242a5ef3d14bcf129efd5f40f678ca456db294af6c
```

Baseline SHA-256 fingerprints:

```text
anox_customise.ini  d65fdd9943ce8e19385587f9c32e3265d5daf5bd2808cbc395272bcaa187a5fc
rtx.conf            103df0f11303c72d0902ed4a49b508f7801c0ef5b75dc274471fa4d3d6a6549b
pbr.usda            8d23bdeb583ef42fa5cdf832e16ad370b25d9e96a8d8a3fb5ef0dd3e7307d20e
emissive.usda       48b58beed63d73a7512a00e5cd46ecef0fa0e86615f8ac35557e3ea0a6a19070
```

## Diagnostics

Each diagnostic changes one property family:

1. `light075`: append `[maplights.rowdys] scale = 0.75`; QindieGL confirms 71
   lights loaded at scale 0.75.
2. `normals-off`: remove the 3,407 `inputs:normalmap_texture` opinions from the
   installed PBR sublayer. Keep roughness, metallic, glass, emission, and other
   layers unchanged. Parse the modified USDA and inspect composed attributes.
3. `sign-emission-off`: disable only `inputs:enable_emission` for the five
   Rowdy's sign materials below. Keep their normal maps and other properties.
   This is a test of these signs, not every emissive fixture in the room.
4. `light0`: use `[maplights.rowdys] scale = 0` after a fresh launch as a
   stronger control for map-light contribution.

| Texture | Hash | Baseline emissive intensity |
| --- | --- | ---: |
| `+0bigjim` | `5CEF37287353BBDA` | 2.5 |
| `+1bigjim` | `8B15A798476DF1DA` | 2.5 |
| `blbrew` | `C7B92F8B1F377239` | 2.25 |
| `rowdysign` | `5B1E046F7EDA458C` | 6.5 |
| `stout` | `8079E7F268286839` | 2.5 |

## Local evidence

Captures, per-case JSON (poses, fingerprints, timing, frame metrics), baseline
config copies, diagnostic scripts, and QindieGL/Remix logs remain in ignored
`tools/shots/rowdys-2026-10-17/` in the owner's main checkout. Game data,
generated layers, and screenshots are not committed.

Three diagnostic frames contain an NPC passing close to the camera:
`normals-off-slot2-0`, `sign-emission-off-slot2-2`, and `light0-slot2-0`.
Keep them in the evidence, but exclude them
from numeric comparisons and use unobstructed frames to inspect the room.
Early baselines also contain a small developer entity label at the lower left;
it is absent after restarting. Do not attribute differences in that text to
lighting or materials.

Image metrics are descriptive sRGB statistics, not physical luminance or a
quality score. Whole-image averages cannot prove that a small material detail
improved. Visual comparison and verified configuration changes take precedence.

## Results and decision

Fourteen verified save loads produced 42 comparison frames. All reported the
same saved positions/yaw. The final fresh-launch baseline (`baseline-c`) restored
the original four recorded config/layer fingerprints and reproduced the room's
appearance. The zero-light and final baseline cases used the default 120-second
load budget successfully.

| Diagnostic | Observed result | Decision |
| --- | --- | --- |
| Generated normal references removed | Walls and floor become visibly flatter; bright fixture faces remain | Retain generated normals; targeted close-up bright-edge checks remain |
| Five sign emissions disabled | Sign lettering/faces become dimmer while normal-map detail remains | Retain sign emissions; this does not verify every emissive material |
| Map-light scale 0.75 | No clear room-lighting improvement over baseline variation | Retain scale 1 |
| Map-light scale 0, fresh launch | No clear room-lighting change in either saved view | Investigate actual API-light rendering before further calibration |

A fixed wall crop, `(0, 250)` to `(500, 740)` in frame 1, avoids the developer
label and foreground NPCs. Mean absolute RGB differences against baseline A
(0–255 channel values, averaged across channels) were:

| Case | Save 1 | Save 2 |
| --- | ---: | ---: |
| Baseline B | 0.819 | 0.354 |
| Light scale 0.75 | 0.820 | 0.349 |
| Generated normals removed | 8.475 | 0.782 |
| Five sign emissions disabled | 0.827 | 0.352 |
| Light scale 0 | 0.827 | 0.352 |
| Final baseline C | 0.824 | 0.352 |

These crops support the limited wall-lighting observation; they do not measure
sign emission or overall quality. An additional six frames at save 2 changed
scale from 0 to 1 **after** loading, without another save restore. Fresh reload
logs confirmed both values; no clear room-lighting change was visible there
either. Moving NPCs prevent a whole-image equality claim.

This does not prove map lights never contribute or identify a root cause. Earlier
Rowdy's lighting comparisons used a different runtime. Inspect actual API-light
rendering on the current installation before selecting new brightness defaults.
No material or lighting defaults were changed.

The session exposed dropped console characters at the former 30 ms hold / 20 ms
gap. Increasing those to 80 / 40 ms completed the 14 verified loads; nonce
validation remains mandatory. All 26 existing rig tests passed. This is evidence
for the tested load, not a guarantee for every frame rate or keyboard layout.

The cleanup guard reported restoration of original game configs/material layers
and Steam launch options, closure of the nested session, and desktop Steam
restart. The separate final restoration-verification command was not executed:
automatic approval review hit an account usage limit. Independent post-cleanup
fingerprint verification was pending at publication. A follow-up on 2026-10-17
verified that all five guarded game files and five save fingerprints matched
their backups, the original Steam launch options were restored, and nested X7
was closed.

The subsequent [API investigation](maplight-api-check.md) reproduced failed
updates when destroyed light identities were reused and verified a wrapper fix.
Repeat saved-view brightness calibration with that corrected build.
