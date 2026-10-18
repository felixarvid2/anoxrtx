# Startup device replacement and map lighting — 2026-10-18

The dim initial Rowdy's view is reproducible with the previous installed DLL.
After startup replaces its graphics device, the wrapper retains map-light
handles without rebuilding them. Reloading unchanged settings restores the
light contribution. The corrected lifecycle releases lights before device
teardown and schedules the existing delayed rebuild on the replacement device.
Light formulas, material values and runtime settings are unchanged.

## Reproduction and source evidence

The original DLL, SHA-256
`ae9c2ac5b15d2958ed33431437525a2de009e91d44d07669019f456cc25df32b`, creates
71 Rowdy's lights on the initial graphics device and reports successful API
draws. The game then deletes that context and creates a replacement device.
There is no intervening light recreation before the first saved view. A
same-value configuration reload creates fresh handles and visibly brightens it.

`D3DGlobal_Cleanup` already calls `rmx_deinit_device` before releasing the old
device, but that callback previously only deinitialized ImGui. The matching
initialization callback also only initialized ImGui. Map-light handles and
pending state therefore outlived the device. The API interface itself can
remain initialized across replacement, so the absence of a second API-layout
log does not establish that the device remained unchanged.

QindieGL now connects those callbacks to static/dynamic light cleanup and a
delayed rebuild for the retained map name. Repeated cleanup is harmless; map
name and process-lifetime light identity serial survive. It retains the
120-frame delay before changing map config and creating lights. In-place
device Reset is a separate path and was not changed.

The test DLL SHA-256 is
`5f5c14395ce1038017a37a1de3e2727be552cb5fc5ee8650544eca1fbf051095`.
Its log records device 1 releasing 71 map lights before teardown, device 2
ready/scheduling a rebuild, and device 2 creating/drawing 71 lights before any
manual reload. This closes the observed lifecycle gap without changing light
strength. It does not claim to inspect Remix's internal resource tables.

## Method

- RTX Remix Plus 1.5.1, GE-Proton 11-9, RTX 5060 Laptop, nested Xwayland `:7`.
  External power was checked before and during testing; GPU use was serialized.
- The original and patched DLLs use the same runtime, configs, map-light data,
  mod asset contents and full-resolution screenshot geometry (1920 × 1107).
- `anoxcapture.py` loads a save with the rig's normal 120-second waiting budget,
  requires the fresh verified load receipt and expected position/yaw, restores
  developer mode, and rejects visible console/menu frames. The waiting budget
  is not a hard command wall-clock limit.
- Each condition settles eight seconds, then captures three frames two seconds
  apart. Captures and reports use new directories and preserve raw frames/logs.
- Same-value reloads touch the customise file without changing its bytes.
  Scale controls append an explicit Rowdy's scale 0 or 1. Fresh reload logs
  must confirm the camera within two units of the saved position; no camera
  input is sent between conditions. Their manifests retain the original
  verified yaw and record this distinct pose-evidence source.
- `anoxcompare.py` compares temporal medians. Default limits are per-pixel
  maximum RGB-channel difference >12, at most 2% changed pixels, and mean
  absolute RGB error at most 2. Values are encoded screenshot RGB, not
  calibrated luminance. NPC animation and temporal rendering continue.
- Fingerprints are strict by default. Deliberate scale controls explicitly
  waive config differences; original/patched DLL comparisons explicitly waive
  only the DLL difference. Reports record each waiver. Same-value comparisons
  require no waiver. See [tool workflow](screenshot-regression.md).

## First saved view

`steamuser/1`: position `(1168, 1235, 336)`, yaw 9, save SHA-256
`514b5e01fba112fff82830eb6bbd4cba1ce4c0a8080eb0ced825a491d903124f`.

| Comparison | Changed pixels | Mean absolute RGB error | Result |
| --- | ---: | ---: | --- |
| Original initial → unchanged-value reload | 52.83% | 29.19 | Clear lighting difference, reproduced defect |
| Original scale 1 → repeated scale 1 | 0.91% | 1.15 | Pass, unchanged lit reference |
| Original scale 1 → scale 0 | 52.85% | 29.19 | Fail, expected lighting-loss control |
| Original initial → patched initial | 52.52% | 29.05 | Clear intended correction |
| Original unchanged-value reload → patched initial | 1.23% | 1.32 | Pass, matches repaired reference |
| Patched initial → unchanged-value reload | 1.16% | 1.28 | Pass, manual reload no longer repairs a dark view |
| Patched initial → scale 1 | 1.02% | 1.20 | Pass, intended contribution already present |
| Patched initial → scale 0 | 52.57% | 29.08 | Fail, expected lighting-loss control |
| Patched initial → initial repeat, before reload | 0.09% | 0.75 | Pass, unchanged initial reference |

The first original capture used a USD-definition-only inventory while the
capture tool was being developed. It remains local but is excluded from these
comparisons. The original initial-repeat was captured before any reload using
the final complete mod-asset inventory, and is the initial reference above.

## Second saved view and moving actors

`steamuser/2`: position `(756, 1289, 8)`, yaw 11, save SHA-256
`1447411179f7d3bed0a457242a5ef3d14bcf129efd5f40f678ca456db294af6c`.

Whole-image unchanged comparisons fail the strict defaults: the initial repeat
changes 3.52% of pixels (mean error 2.63), and the same-value reload changes
2.91% (2.43). The difference images show the moving bartender and other actors,
plus animated signage. An initial actor exclusion ending at normalized X=0.8
does not cover the bartender's path and also fails. These diagnostic reports
are retained; thresholds were not relaxed or raw captures replaced.

The fixed static-room region is normalized `(0.02, 0.02, 0.72, 0.43)`, covering
the upper left walls/ceiling and excluding actors and the animated bar sign.
The same region and default thresholds are used for positive and negative
controls. This narrower acceptance tests the light contribution in that
scenery; it does not claim an unchanged entire scene or validate actor shading.

| Patched initial compared with | Changed pixels in static region | Mean absolute RGB error | Result |
| --- | ---: | ---: | --- |
| Initial repeat before reload | 0.14% | 0.90 | Pass |
| Same-value reload | 0.15% | 0.91 | Pass |
| Scale 0 | 51.93% | 22.20 | Fail, expected lighting-loss control |
| Scale 1 | 0.24% | 0.95 | Pass |

## Fresh start, repeated restore and reverse order

There were three controlled launches: one with the original DLL and two with
the patched DLL. The original run loaded save 1. The first patched run loaded
save 1 then save 2, each before their reload controls. The second patched run
loaded save 2 first, restored save 2 again, then loaded save 1. All six loads
passed the normal rig receipt, fingerprint, position/yaw and console-closure
checks. The three later loads had no manual config reload between them.

| Comparison against first patched capture of that save | Region | Changed pixels | Mean error | Result |
| --- | --- | ---: | ---: | --- |
| Fresh-start save 2 loaded first | Static room region above | 0.15% | 0.90 | Pass |
| Same save 2 restored again | Same static region | 0.14% | 0.90 | Pass |
| Save 1 after the two save-2 restores | Full image | 0.13% | 0.77 | Pass |

The second patched startup again logs release of 71 device-1 lights and
successful creation/drawing of 71 device-2 lights, before any reload controls.
This is bounded repeat evidence for these two indoor views, not every save
or device-reset path.

## Scope and local evidence

Source review and the Linux cross-build passed; the DLL retains 385 exports.
All 61 Python tests pass, including capture preflight, immutable outputs,
metadata/cadence rejection, temporal noise and lighting-loss comparisons.
Stock Remix, MSVC, other maps, combat dlights and in-place device Reset remain
separate verification work. Neither successful API returns nor a screenshot
score proves those cases.

Raw images, manifests, logs, comparison reports and the persistent recovery
guard live under `~/.cache/anoxrtx/lighting-startup-2026-10-18/session1/`.
They contain local game artifacts and are not committed. The build log is in
the parent directory. Configs, saves, game assets and DLLs remain outside Git.

The evidence manifest records 21 capture sets / 63 frames and 22 comparison
reports, including the retained early inventory capture and unsuccessful
whole-image/actor-mask comparisons. The surrounding guard restored all 37
recorded game files, including the original DLL and five saves, restored the
exact original launch options, closed `:7`, and restarted desktop Steam.
An independent post-cleanup check confirmed every item and stopped game/bridge
processes, with no restoration errors.

After restoration, the tested lifecycle DLL was installed with the previous
DLL retained at `session1/backup/opengl32.dll`. Its SHA-256 was checked again;
the other 36 recorded files remained unchanged. Installation/backup details
are in `~/.cache/anoxrtx/lighting-startup-2026-10-18/installed-fix.json`.
