# PBR conflict review (2026-10-28)

Review of the textures where the name rule (`tools/pbr_rules.json`) and Jev (`jev_classes.json`) disagree on the
PBR class, roadmap item 6. Inputs: the maps in `~/.cache/anoxrtx/event-lighting-2026-10-18/maps`, Jev classes,
the DeepSeek thumbnail cache (`--vision`), no `--ai`.

## Method

- `tools/pbr_classify.py OUTDIR <maps>/*.bsp --classes jev_classes.json --vision deepseek_vision.json` listed
  237 conflicts (236 rule vs Jev, plus `tensil/rope-ladder`, two name rules, already an exception).
- DeepSeek (`deepseek-flash`) adjudicated them from 5x5 contact sheets of 128 px thumbnails (the approved
  thumbnails only), with the texture path, face count, the rule's class, Jev's class, Gemini's description from
  `jev_classes.json` and the earlier thumbnail answer as text: 10 requests, 20 k input / 57 k output tokens,
  about 0.02 USD (balance 9.76 -> 9.74 USD). Answers are cached in `~/.cache/anoxrtx/deepseek_conflicts.json`.
- Every sheet was then reviewed by eye (larger crops for the unclear ones); that review decided. DeepSeek and the
  review agreed on most; the review overruled it where the image says otherwise, e.g. `bricks/windowplain`
  (DeepSeek: stone; review: dark window glass with smudged reflections on the city facades) and the bar menu
  displays (DeepSeek: sign; review: Jev's screen kept).

## Result

205 exceptions in `tools/pbr_rules.json` (reason ends with "DeepSeek vision + review"); conflicts 237 -> 31.
An exception now also clears a rule-vs-rule conflict, and when it names the material Jev chose, Jev's per-texture
roughness/metallic are kept (`pbr_classify.py`), so most exceptions only confirm the installed values.

Main groups:

| decision | examples |
| --- | --- |
| glass: facades with window panes, dark window glass | `bricks/windowplain`, `bricks/window2`/`3b`/`3c`/`4`/`1f`, `senderloung/window2a`, `roberg/windows`, `baltown/door-201top` |
| metal: "window"/"cabinet"/"bar"/"chair" textures that show bare metal | `bricks/windowshit*`, `senderstation/win1h`, `*/cabinet04*`, `senderloung/chair1`, `tantasol/roof`, `stax/crate*`, `hive/comp_pan*` |
| tech: computer housings, control panels, bezels | `commbase/compside-*`, `bricks/compctrls`, `sunder/monitor-btm1`/`4`, `votowne/z-comp-1`/`3` |
| screen / sign | `sunder/bardrink-*` (menu displays), `votowne/elevator*`, `hep2/eco_bar`, `sexmachine/+Nsandm`, `bricks/01comp` (graffiti) |
| light | `senderloung/columface1c`, `fatroom/fr_bar`, `commbase/beam`, `tantasol/barlight` |
| stone | `dome/panel0*` (painted reliefs), `tensil/trim*`, `limbus/door1`, `doren/ventwall` |
| wood / fabric / organic | `limbus/door4`/`5`, `whitendon/in_rafter*`, `tensil/window01` (shutters), `bricks2/couch`, `doren/woods01`, `levant/lev_fruitbox3` |

## Left open (31)

Genuinely ambiguous; they keep Jev's values and stay in the report's conflict list.

| texture | faces | rule | Jev | why open |
| --- | --- | --- | --- | --- |
| `baseanox/clear` | 28302 | glass | screen | black thumbnail; translucent (TRANS33) on water/window brushes, so the class does not change the output |
| `sunder/clear` | 4427 | glass | screen | black thumbnail; translucent (TRANS33), class does not change the output |
| `routubes/clear` | 1868 | glass | screen | black thumbnail, opaque |
| `gaberella/clear` | 1557 | glass | screen | black thumbnail, opaque |
| `roberg/clear` | 1135 | glass | screen | black thumbnail, opaque |
| `limbus/clear` | 998 | glass | screen | a white letter E on black, named clear |
| `limbus/pilr_1` | 888 | stone | metal | carved relief: bronze or stone |
| `limbus/pilr_1a` | 689 | stone | metal | carved relief: bronze or stone |
| `ballotine/column05` | 677 | stone | metal | wood grain on a framework the other ballotine columns show as metal |
| `ballotine/column04` | 330 | stone | metal | wood grain on a framework the other ballotine columns show as metal |
| `pileohunks/column04alpha` | 249 | stone | metal | wood grain on a framework the ballotine columns show as metal |
| `bricks/cabinet04d` | 177 | wood | metal | metal cabinet frame with books |
| `sunder/barstool-side` | 150 | wood | metal | padded or metal stool side |
| `ballotine/scaff05` | 96 | metal | stone | black thumbnail |
| `sunder/barstool-sidea` | 64 | wood | metal | padded or metal stool side |
| `limbus/pilr_2` | 54 | stone | metal | carved relief: bronze or stone |
| `detta/end_trim` | 44 | tech | organic | rippled metal or organic trim |
| `senderloung/columside1c` | 29 | stone | metal | ornamental cutouts, metal or plaster |
| `whitendon/in_window02` | 29 | glass | stone | brick base + window grille |
| `bricks/bed1` | 26 | fabric | polished | composite: light + tiles |
| `bricks/cabinet04c` | 25 | wood | metal | metal cabinet frame with books |
| `braintrain/seatcushion3d` | 21 | fabric | metal | white plastic seat or cushion |
| `republic/deskside` | 16 | wood | metal | featureless dark brown |
| `votowne/windpillr2` | 15 | glass | metal | dark smooth panel, glass or metal |
| `levant/grate4` | 14 | metal | stone | featureless dark noise |
| `sunder/barmugs-1a` | 7 | wood | metal | glass mugs on a metal shelf |
| `limbus/pilr_3` | 6 | stone | metal | carved relief: metal or stone |
| `orange/couchend` | 6 | fabric | wood | leather/fabric or wood |
| `sendormitory/tilebro` | 6 | polished | metal | brown tile or bronze panel |
| `fortress/wine` | 5 | glass | organic | liquid (wine) |
| `sendertrans/grid1` | 1 | metal | stone | featureless grey |

The `*/clear` textures need a look in the game (what they are drawn on) rather than at the thumbnail; the limbus
pillars and ballotine columns need a close-up in their maps.

## Effect on the installed layer

Regenerated with `pbr_layer.py` (same inputs as the installer: `--classes`, `--vision`): 3417 materials, the
normal maps unchanged. Against the classification before this review, 67 textures change roughness/metallic
(62 change class; the other 5 are earlier exceptions that now keep Jev's finer values: `tensil/door02`/`03`,
`senderstation/curtainrods`, `baltown/doorwall-101top`, `tensil/rope-ladder`). The rest of the 205 exceptions
confirm Jev and change nothing. Note that Jev's "metal" often comes with a metal probability below 0.5 (painted
or rough metal), which gives metallic 0; confirming exceptions keep that (e.g. `senderstation/curtainrods` now
0.895/0 instead of the metal class's 0.45/0.6).

| texture | faces | class | roughness | metallic |
| --- | --- | --- | --- | --- |
| `bricks/windowplain` | 4359 | stone -> glass | 0.943 -> 0.25 | 0 -> 0 |
| `senderloung/columface1c` | 267 | metal -> light | 0.375 -> 0.35 | 0.54 -> 0 |
| `commbase/compside-1` | 262 | metal -> tech | 0.253 -> 0.5 | 0.67 -> 0.3 |
| `whitendon/in_chair` | 242 | metal -> wood | 0.305 -> 0.6 | 0.52 -> 0 |
| `fatroom/fr_bar` | 201 | metal -> light | 0.145 -> 0.35 | 0.75 -> 0 |
| `bricks/window2` | 171 | metal -> glass | 0.292 -> 0.25 | 0.55 -> 0 |
| `whitendon/in_rafter01` | 144 | metal -> wood | 0.247 -> 0.6 | 0.51 -> 0 |
| `bricks/window3b` | 122 | metal -> glass | 0.828 -> 0.25 | 0 -> 0 |
| `tensil/bars` | 122 | metal -> wood | 0.815 -> 0.6 | 0 -> 0 |
| `pileohunks/window3_sm` | 118 | metal -> glass | 0.575 -> 0.25 | 0.56 -> 0 |
| `whitendon/in_rafter02` | 115 | metal -> wood | 0.24 -> 0.6 | 0.58 -> 0 |
| `commbase/compside-2` | 112 | metal -> tech | 0.247 -> 0.5 | 0.71 -> 0.3 |
| `whitendon/in_table` | 102 | metal -> wood | 0.573 -> 0.6 | 0 -> 0 |
| `bricks/compctrls` | 91 | metal -> tech | 0.5 -> 0.5 | 0 -> 0.3 |
| `senderstation/curtainrods` | 90 | metal -> metal | 0.45 -> 0.895 | 0.6 -> 0 |
| `senderloung/wintrans2` | 84 | metal -> glass | 0.18 -> 0.25 | 0 -> 0 |
| `bricks2/computer` | 76 | metal -> tech | 0.372 -> 0.5 | 0.6 -> 0.3 |
| `bricks/window3c` | 60 | metal -> glass | 0.843 -> 0.25 | 0 -> 0 |
| `bricks2/couch` | 56 | metal -> fabric | 0.31 -> 0.95 | 0 -> 0 |
| `tensil/rope-ladder` | 54 | fabric -> fabric | 0.95 -> 0.815 | 0 -> 0 |
| `senderloung/table2` | 40 | metal -> glass | 0.32 -> 0.25 | 0 -> 0 |
| `senderloung/window2a` | 40 | metal -> glass | 0.21 -> 0.25 | 0.5 -> 0 |
| `bricks/window3b_sm` | 33 | metal -> glass | 0.835 -> 0.25 | 0 -> 0 |
| `rowdy01/barcrap` | 33 | screen -> wood | 0.98 -> 0.6 | 0 -> 0 |
| `whitendon/in_rail1` | 32 | stone -> wood | 0.258 -> 0.6 | 0 -> 0 |
| `commbase/compside-3` | 29 | metal -> tech | 0.25 -> 0.5 | 0.71 -> 0.3 |
| `fatroom/fr_shelf` | 27 | metal -> tech | 0.237 -> 0.5 | 0.61 -> 0.3 |
| `senderloung/columbase1a` | 26 | metal -> light | 0.352 -> 0.35 | 0.5 -> 0 |
| `bricks/02comp` | 24 | stone -> sign | 0.815 -> 0.5 | 0 -> 0 |
| `commbase/beam` | 24 | screen -> light | 0.41 -> 0.35 | 0 -> 0 |
| `fatroom/fr_bed` | 23 | metal -> fabric | 0.16 -> 0.95 | 0.73 -> 0 |
| `roberg/windows` | 23 | polished -> glass | 0.21 -> 0.25 | 0 -> 0 |
| `whitendon/in_bed` | 23 | stone -> fabric | 0.98 -> 0.95 | 0 -> 0 |
| `hep2/eco_bar` | 20 | screen -> sign | 0.62 -> 0.5 | 0 -> 0 |
| `sunder/monitor-btm1` | 20 | metal -> tech | 0.905 -> 0.5 | 0 -> 0.3 |
| `senderstation/comput1a` | 18 | metal -> tech | 0.23 -> 0.5 | 0.72 -> 0.3 |
| `commbase/tenttop-3` | 16 | metal -> fabric | 0.245 -> 0.95 | 0.79 -> 0 |
| `sunder/monitor-btm4` | 16 | metal -> tech | 0.91 -> 0.5 | 0 -> 0.3 |
| `bricks/01comp` | 14 | stone -> sign | 0.807 -> 0.5 | 0 -> 0 |
| `levant/lev_fruitbox4` | 11 | screen -> wood | 0.545 -> 0.6 | 0 -> 0 |
| `votowne/z-comp-3` | 10 | metal -> tech | 0.728 -> 0.5 | 0 -> 0.3 |
| `tensil/door02` | 8 | wood -> wood | 0.6 -> 0.863 | 0 -> 0 |
| `sunder/+0monitext1` | 6 | glass -> screen | 0.247 -> 0.2 | 0 -> 0 |
| `sunder/+2monitext1` | 6 | glass -> screen | 0.247 -> 0.2 | 0 -> 0 |
| `tensil/door03` | 5 | wood -> wood | 0.6 -> 0.86 | 0 -> 0 |
| `baltown/doorwall-101top` | 4 | glass -> glass | 0.25 -> 0.245 | 0 -> 0 |
| `baltown/roof-201` | 4 | metal -> light | 0.573 -> 0.35 | 0 -> 0 |
| `bricks/window4` | 4 | metal -> glass | 0.42 -> 0.25 | 0.55 -> 0 |
| `votowne/z-comp-1` | 4 | metal -> tech | 0.655 -> 0.5 | 0.5 -> 0.3 |
| `sunder/+0monitext4` | 3 | glass -> screen | 0.245 -> 0.2 | 0 -> 0 |
| `sunder/trim-1` | 3 | glass -> tech | 0.258 -> 0.5 | 0 -> 0.3 |
| `votowne/elevator` | 3 | screen -> sign | 0.645 -> 0.5 | 0 -> 0 |
| `bricks2/barton` | 2 | screen -> sign | 0.287 -> 0.5 | 0 -> 0 |
| `fatroom/fr_shelf2` | 2 | metal -> tech | 0.863 -> 0.5 | 0 -> 0.3 |
| `senderstation/vent1a` | 2 | stone -> metal | 0.955 -> 0.45 | 0 -> 0.6 |
| `sexmachine/+0sandm` | 2 | screen -> sign | 0.69 -> 0.5 | 0 -> 0 |
| `sexmachine/+1sandm` | 2 | screen -> sign | 0.655 -> 0.5 | 0 -> 0 |
| `sexmachine/+2sandm` | 2 | screen -> sign | 0.66 -> 0.5 | 0 -> 0 |
| `sunder/bardrink-s4ba` | 2 | metal -> screen | 0.22 -> 0.2 | 0.62 -> 0 |
| `sunder/compctrls` | 2 | metal -> tech | 0.5 -> 0.5 | 0 -> 0.3 |
| `bricks/window1f` | 1 | metal -> glass | 0.97 -> 0.25 | 0 -> 0 |
| `tantasol/barlight` | 1 | screen -> light | 0.655 -> 0.35 | 0 -> 0 |
| `votowne/elevator-2` | 1 | screen -> sign | 0.575 -> 0.5 | 0 -> 0 |
| `votowne/elevator-3` | 1 | screen -> sign | 0.667 -> 0.5 | 0 -> 0 |
| `votowne/elevator-4` | 1 | screen -> sign | 0.585 -> 0.5 | 0 -> 0 |
| `votowne/elevator-5` | 1 | screen -> sign | 0.627 -> 0.5 | 0 -> 0 |
| `bricks/window6` | 0 | metal -> glass | 0.448 -> 0.25 | 0.66 -> 0 |
