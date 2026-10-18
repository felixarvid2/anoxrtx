# Map-light reload investigation — 2026-10-17

> Historical test record. Follow [current status](../STATUS.md) and
> [the implementation plan](../PLAN.md) for present priorities. Console input
> was subsequently fixed and accepted in [PR #27](console-input-check.md);
> the later [startup lighting check](startup-lighting-check.md) records the
> device-lifecycle reproduction and correction.


Reusing an API light identity after destroying it prevented visible updates on
the installed Remix Plus runtime. Giving every creation a fresh identity fixes
the reproduced existing-light edit and restores visible scale changes. No
brightness defaults or material layers were changed.

## Evidence

The [earlier saved-view check](rowdys-material-check.md) showed no clear change
between map-light scales 0, 0.75, and 1. This follow-up tested the API boundary
with a diagnostic QindieGL build in nested Xwayland `:7`, GE-Proton 11-9, RTX
5060 Laptop, and 1920 × 1107 captures.

Installed `d3d9.dll`, `.trex/d3d9.dll`, `.trex/NvRemixBridge.exe`, and
`NvRemixLauncher32.exe` all matched their SHA-256 values in the local
`Remix_Plus_v1.5.1_x86_games_release.zip`. This establishes the deployed release
more precisely than its generic `remix-main` startup string.

Bounded diagnostics showed 71 successful `CreateLight` calls, 71 nonzero
handles, and 8,520 successful `DrawLightInstance` calls across the first 120
measured frames. Those return codes alone did not establish visible rendering.

A save-load attempt failed its nonce transcript check during initial console
input, and cleanup could not confirm console closure. No save restore was
claimed. The comparison instead used the stationary startup hallway, with the
console closed and logged `refdef` view origin `(1480, 203, 118)`. These are
not additional verified captures of the two saved views. Camera motion was not
commanded; NPC animation continued.

## Reproduction and fix

1. After initial loading, change map-light strength through
   `[maplights.rowdys] scale` and wait for a logged reload. Before the fix,
   scales 0, 100, and even 10,000 produced no clear room-lighting change.
2. Temporarily append `add 1480 203 118 1 0 0 3000 16` to
   `rtx-remix/maplights/rowdys.override`. This newly identified red sphere
   illuminates the hallway strongly, proving the API path can reach rendering.
3. Remove that addition. Make existing file light 0 match the same descriptor:

   ```text
   0 move 164 -1333 -226
   0 color 1 0 0
   0 radius 16
   0 scale 225
   ```

   Light 0 starts at `(1316, 1536, 344)`, raw intensity 200. With default
   exponent 2 and reference 300, its radiance is `200² / 300`; the override
   scales that result by 225 to 30,000, matching the added raw-intensity-3000
   sphere. This existing identity failed to show the red edit despite accepted
   client calls. Setting `isDynamic` alone did not fix the reproduction.
4. QindieGL now assigns each actual creation a process-lifetime serial in a
   dedicated `0x4D4C` namespace. It never resets the serial during map reloads
   or reuses it for style updates. Identity exhaustion fails rather than wraps.
   Disabled style factors do not allocate identities. Static flags, brightness
   calculations, override indices, and added-light counts remain unchanged.
5. Repeat step 3: the existing light now produces the same strong red lighting.
   Remove the override, then test scales 0, 100, and 1. All changes visibly take
   effect. A further reload with unchanged scale 1 retains working lights.

Mean grayscale output values from three frames per case illustrate the change:

| Map-light scale | Before: reused identities | After: fresh identities |
| --- | ---: | ---: |
| 0 | 26.65 | 26.65 |
| 100 | 26.66 | 133.19 |
| 1 | 26.65 | 53.49 |

These are descriptive sRGB image statistics, not physical luminance or a quality
score. The high scale and red sphere are diagnostic controls, not proposed
defaults. The original first-pass scale-1 frame files were overwritten by a
later repeat; its numeric record remains, and the local JSON flags those files
as unavailable. The fixed-build captures are retained separately.

## Interpretation and limits

The observed failure boundary is destruction/recreation with a reused identity.
The public [Remix Plus API source](https://github.com/RemixProjGroup/dxvk-remix/blob/main/src/dxvk/rtx_render/rtx_remix_api.cpp)
defers light destruction, which is consistent with a lifecycle aliasing issue.
That source is current `main`, not a verified source revision for the installed
1.5.1 binaries; the exact internal ordering responsible is not established.
The fix avoids identity reuse rather than depending on that ordering.

API hashes now identify individual creations. Use file indices in `.override`
files for persistent edits; do not treat the API hashes as stable map IDs.
The light formula and default scale remain unchanged. Calibrating the two saved
views should be repeated with the corrected wrapper. Outdoor brightness,
animated styles, dynamic combat lights, stock Remix, and MSVC were not verified
by this test. Dynamic combat lights use a separate implementation.

## Validation and local artifacts

- Linux cross-build passed; the DLL retained 385 exports.
- Visual regression: existing red-light edit failed before and passed after.
- Zero/high/default scale changes and a same-value reload were visually checked;
  API summaries continued to show 71 valid handles and no measured draw errors.
- Both guarded sessions restored their DLL/config/layer backups, all five save
  fingerprints, original Steam launch options, and the desktop session. Final
  independent checks confirmed restoration and closure of X7. The temporary
  `.override` file was removed.

Evidence remains local in ignored `tools/shots/maplight-api-2026-10-17/` and
`tools/shots/maplight-api-fixed-2026-10-17/`: scripts, captures, API log excerpts,
runtime logs, and the tested DLL fingerprint. Game data, built DLLs, generated
layers, and screenshots are not committed.
