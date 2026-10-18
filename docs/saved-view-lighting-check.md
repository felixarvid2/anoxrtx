# Saved-view map-light check with the fixed wrapper — 2026-10-17

> Historical test record. Follow [current status](../STATUS.md) and
> [the implementation plan](../PLAN.md) for present priorities. Console input
> was subsequently fixed and accepted in [PR #27](console-input-check.md);
> the later [startup lighting check](startup-lighting-check.md) records the
> device-lifecycle reproduction and correction.


The fixed QindieGL build shows a visible map-light scale contribution in both
verified Rowdy's saves. At scale 0, their nearby map-light illumination is
absent; returning to scale 1 restores it. The default
light formula and settings were restored after the check.

## Method

The test used RTX Remix Plus 1.5.1, GE-Proton 11-9, a nested Xwayland `:7`
session, and the installed `opengl32.dll` with SHA-256
`ae9c2ac5b15d2958ed33431437525a2de009e91d44d07669019f456cc25df32b`. The
game window was 1920 × 1107 on a 1920 × 1200 nested display. The startup scene
was left idle until it had visible rendered content, then allowed at least 30
more seconds for initial material loading.

Each save load was accepted only after the rig's fresh nonce-bounded console
transcript named the requested save, reported parsed savegame lumps, and
confirmed the settled camera. The saves' SHA-256 values were checked against
their fingerprints before and after the load. Captures used the same saved
camera, an eight-second settle after each load or light-scale reload, and three
frames two seconds apart. The rig stores screenshots at 960 pixels wide.

The normal console input pass did not yield a confirmed load for
`steamuser/1`; no image from that attempt was treated as a saved-view result.
An isolated temporary rig copy held Backspace for autorepeat and used 120 ms
key holds and gaps. That pass completed the nonce and pose checks for both
saves. The tracked rig was not changed.

## Results

The values below are the rig's mean RGB values from each captured frame. They
describe these screenshots and are not calibrated luminance measurements.

| Save and verified camera | Scale condition | Three-frame mean RGB | Observation |
| --- | --- | --- | --- |
| `steamuser/1`, `(1168, 1235, 336)`, yaw 9 | Default scale 1 after load | `[45,47,46]`, `[45,48,47]`, `[45,48,47]` | Captured as requested; this initial set was as dark as scale 0 and is not a reliable scale-1 comparison. |
| `steamuser/1`, same view | Scale 0 | `[45,47,46]`, `[45,48,47]`, `[45,48,47]` | Nearby map-light contribution was absent. |
| `steamuser/1`, same view | Scale 1 after explicit reload | `[74,77,75]` in all three frames | The room and wall textures brightened clearly. |
| `steamuser/2`, `(756, 1289, 8)`, yaw 11 | Default scale 1 after load | `[67,72,70]`, `[67,72,70]`, `[67,73,70]` | The scale-1 contribution was already visible. |
| `steamuser/2`, same view | Same-value scale-1 reload | `[67,72,70]` in all three frames | No meaningful brightness change from the initial scale-1 frames. |
| `steamuser/2`, same view | Scale 0 | `[45,48,48]`, `[45,48,48]`, `[45,49,48]` | The counter area and surrounding surfaces darkened clearly. |
| `steamuser/2`, same view | Scale 1 after reload | `[67,72,70]` in all three frames | The illumination returned to the initial scale-1 appearance. |

The save transcripts confirmed these fingerprints:

- `steamuser/1`: `514b5e01fba112fff82830eb6bbd4cba1ce4c0a8080eb0ced825a491d903124f`.
- `steamuser/2`: `1447411179f7d3bed0a457242a5ef3d14bcf129efd5f40f678ca456db294af6c`.

Each scale reload logged the same rounded camera location as the save, within
one unit on X/Y, and used the same Rowdy's light file. The fixed wrapper logged
71 successful `CreateLight` calls, 71 nonzero handles, and 8,520 successful
draws by frame 120, with zero failed draws and 71 live handles. In the second
view, the bartender and a nearby character are visible; the bartender moves
partly out of view across the three scale-1 frames while the saved camera stays
fixed. Changes between consecutive frames also include temporal rendering, so
the images are not pixel-identical.

## Limits

The initial scale-1 frames for the first save were nearly identical in mean
brightness to scale 0. An explicit scale-1 reload brightened that view, while a
same-value scale-1 reload in the second view did not change it. This test
therefore confirms that scales 0 and 1 visibly affect both saved views, but it
does not establish why the first view's initial scale-1 capture was dim or
prove that behavior across every save/load sequence. No arbitrary tuning was
performed, and the default scale remains 1.

The captured session log contains Remix Plus API-layout and D3D/context setup
messages at startup. It contains no new API-layout, Direct3D initialization, or
context-creation entry at the later save-2 restore or scale reloads. This
observation does not identify an internal API lifecycle root cause. The Remix
log also contains the known Wine NRC initialization failure and its fallback to
importance-sampled indirect illumination; no map-light draw failures occurred.

## Local evidence and cleanup

Screenshots, verified load transcripts, runtime logs, the relevant save-2
initialization excerpt, input helper, and configuration/save fingerprints are
in the ignored local directory
`tools/shots/saved-views-fixed-2026-10-17/`. The evidence manifest is
`evidence.json`; full `QindieGL.log`, `remix-dxvk.log`, `bridge32.log`, and
`save2-api-context.log` are retained there. These local game artifacts are not
tracked by Git.

The guarded cleanup restored all six recorded game-file fingerprints, all five
local save fingerprints, the original Steam launch options, and closed nested
Xwayland `:7`. A post-cleanup check confirmed those values and the installed
fixed DLL SHA-256 above. No game data, settings, saves, or screenshots were
committed.
