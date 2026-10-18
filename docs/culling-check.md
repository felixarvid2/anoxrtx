# Culling check: PVS (r_novis) under RTX Remix — 2026-10-18

Question (ROADMAP item 4): does the game's own visibility culling hide geometry that the path tracer needs
(shadows, reflections, light from off-screen surfaces), and what would drawing the whole map cost?

Setup: GE-Proton 11-9, Remix Plus 1.5.1, RTX 5060 Laptop, `r_nocull 1` and `gl_cull 0` already set (no frustum
or back-face culling). A/B with `tools/anoxcheck.py --ab-cfg "set r_novis 1" --views` (the line appended to
`Default.cfg` for the "on" run, restored afterwards); views from `tools/find_views.py`, rendered through
QindieGL's rig camera. Frame times from QindieGL's `Perf:` log lines.

| View | Changed pixels (novis on vs off) | ms/frame novis on | ms/frame off |
| --- | --- | --- | --- |
| levant1 lava | 0.0 % | 20.6 | 20.6 |
| votowne g-stuff2 | 0.6 % | 33.8 | 21.2 |
| votowne bardrink-s3 | 0.1 % | 33.8 | 21.2 |
| museum sign3c | 0.2 % | 21.6 | 20.9 |
| museum sign5c | 0.1 % | 21.6 | 20.9 |
| rowdys (player view) | 0.5 % | 23.7 | 22.9 |

The changed pixels are moving characters and path-tracing noise; no shadow, reflection or lighting difference
from geometry outside the PVS was found. Drawing the whole map costs up to 60 % more frame time on the
largest map (votowne). The black area in the votowne bardrink view is present with and without `r_novis`, so
it is not caused by PVS culling.

Decision: keep the game's PVS (`r_novis 0`). Revisit per map if a light leak or missing off-screen shadow is
seen; `r_novis 1` can then be tested with the same command. Not covered: outdoor maps with large open
areas, and light leaking through walls (would need views placed at known leaks).

Note: the levant1 lava view renders as a uniform brown-grey in both runs (the map's dense fog, or a camera
position in the lava volume); the lava material check needs a different view.
