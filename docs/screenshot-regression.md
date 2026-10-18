# Screenshot capture and regression

`tools/anoxcompare.py` compares immutable capture manifests and at least three
RGB screenshots per capture. It does not drive the game, accept baselines, or
prove the manifest metadata is true. Live capture automation must verify the
save, pose and installed environment before writing metadata.

Use Python with Pillow and numpy (the rig environment needs both):

```sh
~/.cache/anoxrtx/rig-venv/bin/python tools/anoxcompare.py compare \
  /path/to/baseline/manifest.json /path/to/candidate/manifest.json \
  --out /path/to/new-report
```

The output directory must be new and outside both capture directory trees.
The tool writes `report.json`, median-composited `side-by-side.png` (baseline
left), and a 4x absolute RGB `diff.png` (excluded pixels black). Exit codes are
0 for pass, 1 for visual failure, 2 for invalid input/output, and 3 for incompatible
capture metadata. Invalid/incompatible comparisons do not write a report.

## Capture a verified saved view

Start the game in the guarded nested session from HANDOFF first. This command
loads the chosen save, verifies its nonce-bounded receipt and expected pose,
restores developer mode, and captures three full-resolution frames after the
console closes:

```sh
~/.cache/anoxrtx/rig-venv/bin/python tools/anoxcapture.py \
  --save steamuser/1 --expected-pose 1168 1235 336 9 \
  --out ~/.cache/anoxrtx/captures/rowdys-before
```

The output directory must not exist. The producer writes `manifest.json`, the
load receipt, raw PNG frames, and copies of game/Remix logs. It fingerprints
runtime binaries, the installed wrapper, configs, per-map light/override data
and every file in the installed mod directory before/after capture; it rejects
a changed environment or save. Original loose game textures outside the mod
directory are not inventoried, so keep that installation fixed between runs.
It records full screenshot geometry and uses an eight-second settle with
two-second frame intervals by default. Pitch is not exposed by the rig; the
same save and expected position/yaw are required. `start` alone is not proof
that initial material loading finished.

The command operates on an already running test session. It does not change
Steam launch settings, restore the outer session, or automatically promote a
baseline. Invalid input/inventories are rejected before save loading. Runtime
failures may leave an incomplete output directory, which has no completed
manifest and must not be accepted as a baseline. A failed console cleanup still
requires the surrounding session guard to restore settings.

For deliberate same-pose reload controls, a controller may call
`capture_frames` with the prior verified load receipt only after independently
checking fresh wrapper camera evidence and preventing camera input. It must
record that evidence in `pose_source`; this is not a fresh save restore.

## Manifest version 1

Store this alongside the screenshots; image paths are relative to its directory.

```json
{
  "schema_version": 1,
  "save": {
    "selector": "steamuser/1",
    "map": "rowdys",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "pose": {"xyz": [1.0, 2.0, 3.0], "yaw": 359.5},
  "fingerprints": {
    "runtime": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "dll": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "config": {"rtx.conf": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "QindieGL.ini": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"},
    "layers": {"mod.usda": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "sublayer.usda": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}
  },
  "geometry": {"width": 1920, "height": 1200},
  "settle_seconds": 10,
  "interval_seconds": 2,
  "images": ["frame-0.png", "frame-1.png", "frame-2.png"]
}
```

Save SHA256 is lowercase 64-character hex. Runtime and DLL fingerprints must also be lowercase 64-character SHA-256 hex.
Configuration and layer inventories must be nonempty dictionaries of nonempty
path strings to lowercase SHA-256 digests.
Fingerprint values are compared exactly; producers must include all relevant
runtime binaries, configs and recursively used layers. Inventory ordering does
not affect dictionary equality. Unknown fields are allowed for capture evidence
such as timestamps, original window geometry, pose source, logs and phase.

Save selector/map/hash, fingerprints, screenshot geometry, and settle time must
match exactly, as must the positive finite `interval_seconds` frame cadence.
Position permits at most 2 game units Euclidean distance; yaw
permits 1 degree circular distance (359.5 and 0.5 match). Every frame must have
RGB mode and the recorded dimensions. Frames must be distinct file paths,
not absolute paths, traversal paths, or symlinks outside the capture directory.
Do not duplicate frames to meet the three-frame minimum.

`--allow-config-change` and `--allow-dll-change` explicitly waive only those
fingerprint differences for deliberate diagnostic controls or before/after
fix comparisons. The report records each waived mismatch in `pose_delta`.
All other fingerprints remain exact. Such comparisons establish a diagnostic
visual difference; they are not an unchanged-environment regression baseline.
Keep the real fingerprints in each manifest.

## Metrics and masks

Each capture is composited by the per-channel temporal median. The default
changed-pixel metric is maximum absolute RGB channel difference (`--metric max`);
`--metric mean` uses mean absolute channel difference per pixel instead. Default
limits, in 8-bit encoded RGB, are:

- `--pixel-threshold 12`: a pixel changes when its difference is greater than 12.
- `--max-changed-fraction 0.02`: at most 2% of selected pixels may change.
- `--max-mean-error 2`: mean absolute channel error may be at most 2.

Both fraction and mean-error conditions must pass. Mean-only comparisons can
hide local lighting loss and are not accepted: pixel threshold must be below
255 and changed-fraction limit below 1. These initial defaults tolerate modest
noise; they require calibration with real repeated captures and known lighting
loss controls. A passing score does not itself prove physically correct lighting.

`--roi 0,0,1,0.8` limits the selection to a normalized rectangle.
Repeat `--exclude x0,y0,x1,y1` to remove HUD, animated signage or other justified
areas. Bounds must be finite within [0,1], with positive width and height.
Pixel bounds round outward; exclusions win. Empty selections are rejected.
All selected pixels count equally, with no alignment, exposure correction,
rescaling, or perceptual weighting that could conceal a lighting regression.

Temporal medians reduce transient sampling noise, but moving geometry,
animated lights, fog and camera drift still cause differences. Use identical
capture cadence and settling; avoid masking the lighting under investigation.
Retain raw frames and logs so a reviewer can distinguish failures from timing
noise. Screenshots and game assets remain local, outside git.

## Manual baseline promotion

Review the report, raw frames, runtime/log evidence, masks and known negative
controls. Only after an explicit human decision, copy the entire approved
capture directory to a separately named baseline directory and record its source,
reason and fingerprints. Retain the previous baseline. Do not replace just the
images or edit fingerprints to make a comparison pass. There is deliberately no
baseline update or auto-accept command.

Synthetic checks:

```sh
~/.cache/anoxrtx/rig-venv/bin/python -m unittest discover -s tools -p test_anoxcompare.py
```
