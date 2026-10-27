# Event-aware map lights

`tools/bsp2lights.py --events OUTDIR MAP.bsp...` opts into the event-aware
map-light format. Install these files only alongside the paired QindieGL
event-lighting implementation. Older wrappers can ignore the new marker and
incorrectly illuminate lights authored to start off. The new wrapper still
accepts existing `.lights` files.

The default command and `--legacy` retain their existing generated file
contents: they export timer styles 1–11 and omit START_OFF lights. `--events`
and `--legacy` cannot be combined. The installer uses `--events` (it installs a QindieGL build with the
paired wrapper support, QindieGL #27).

Event-aware files use the existing `format raw` header and brightness/radius
calibration. A sphere row has eight numeric fields; a spotlight adds four
numeric fields. Optional tokens follow in this order:

```text
x y z r g b intensity radius [dx dy dz cone_degrees] [style N] [startoff]
sun dx dy dz r g b intensity angle_degrees
```

Styles are integer indices from 0 through 63. Style 0 is implicit and is not
written as a token. Event export preserves authored styles 1–63, including
named/switchable lights using style 32 and above. It does not invent a style
from a target name: only the actual BSP `style` is exported. Invalid indices
or malformed style values produce a diagnostic and no style token.

`startoff` records `spawnflags & 1`. All retained START_OFF rows are appended
after the existing non-off light rows and the sun, in original BSP order.
This preserves existing `.override` indices for previously exported lights,
including the sun. New off lights therefore have indices at the end; their
position in the BSP entity lump is not their override index. A changed style
token does not change a row's index.

Without usable live game data, START_OFF lights stay off. An implicit style 0
START_OFF light has no exported event binding and remains conservatively off;
the exporter reports this case. Invalid-style START_OFF lights use the same
fallback. Retaining an entity does not prove that its switch can drive it:
the wrapper must validate the game's live lightstyle layout and observe the
authored style. Target names alone are insufficient for that mapping.

Spotlight direction/cone, strongest-sun selection, brightness conversion,
supported entity class (`light`) and per-map names retain their existing
behavior. No BSPs, generated light files, or game assets belong in commits.

Run the synthetic format checks with:

```sh
python3 -m unittest discover -s tools -p test_bsp2lights.py
```

These tests validate export and compatibility properties, not the renderer
hook, in-game switch behavior, save restoration, or visual lighting.

## Styled emission (`<map>.estyles`)

`tools/emissive_styles.py` (installer step `estyles`) writes `rtx-remix/maplights/<map>.estyles` for QindieGL's
`styledemission` and `emissive_styles.usda` for the mod:

```
# hash x y z style
0xAC52D1DF17CABCA6 -920.0 -299.5 -276.0 11
```

One line per SURF_LIGHT face whose lightmap has a non-zero style (`dface_t.styles`, first one used): the
texture's Remix hash as in `emissive.usda`, the face centre (average of its vertices) and the style. QindieGL
matches a drawn polygon by hash and centre (within 2 units) and, for style factor level 0..2
(`round(factor * 3)`), draws it with a copy of the texture whose mip-0 byte 0 is XORed with level + 1.
`emissive_styles.usda` gives each copy's hash the texture's materials from the other layers with the emission
scaled by level / 3 (off at 0). Faces of moving brush entities are drawn in local coordinates and do not match.
