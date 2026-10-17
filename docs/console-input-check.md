# Console input investigation, 2026-10-17

Status: console input and both saved views verified on 2026-10-18. The earlier
failed attempt and recovery record are retained below as history.

The previous saved-view check succeeded with an isolated copy of the rig
using held Backspace and 120 ms key holds/gaps. The tracked rig still used
1,024 zero-duration Backspace taps and 80/40 ms typing. Each tap synchronized
with X twice, requiring more than 2,000 round trips just to clear the prompt.

The proposed change holds Backspace through the existing key-release helper,
then types with 120 ms holds and gaps. It checks global and per-key autorepeat,
reads the server rate using a time-bounded `xset q`, and budgets enough time
for a previous 240-character rig command. The test display reported a 600 ms
delay and 25 Hz repeat rate, giving a 10.7-second clear budget. This cannot
guarantee delivery when the game stalls; nonce validation remains required.

## Runtime result, 2026-10-17 (historical)

A guarded nested `:7` run started Rowdy's with the previously verified fixed
QindieGL DLL. `load-save steamuser/1 240` failed after approximately four
minutes with `console did not close; developer-mode restoration needs
inspection`. A screenshot showed `unknown command "toggleconsole;set"`.
A later nonce-based `viewpos` probe returned `(1480 202 118) : 121`, the
startup position rather than save 1's expected `(1168 1235 336) : 9`.
This was not a successful save load. Whether command parsing, received
characters, or another console state caused the failure remains unresolved.
The normal 120-second timeout and a full-length stale prompt were not verified.

The owner then reported a computer restart. The restart removed the temporary
worktree, guard backups, and screenshots. Felix confirmed the laptop ran out of battery;
the test did not request a reboot. The candidate was reconstructed
in a persistent worktree and tested offline. No further game launch was made
before the follow-up below.

## Recovery and remaining checks at that handoff

Only the test `DISPLAY=:7` prefix and `+map rowdys` suffix were removed from
Steam's app launch options after shutting Steam down. The write was verified
and desktop Steam was requested to restart. The installed DLL and both test
save fingerprints still match the prior recorded values. Other config files
cannot be claimed byte-for-byte restored because their temporary pre-test
backups were lost. Recovery notes and the post-reboot Steam config backup are
kept locally under `~/.cache/anoxrtx/recovery/`, outside git.

The remaining acceptance checks were to reproduce the compound-command failure
with small commands, confirm received input and developer-state cleanup, load
both saved views using the normal timeout, and check a full stale prompt and
disabled-repeat behavior. Runtime backups and worktrees must stay on persistent
storage so a restart cannot remove the recovery material.

## Follow-up diagnosis, 2026-10-18

A new nested session reproduced malformed commands with the 120 ms timing.
The game received `echo a?b<c&d` when the rig requested `echo a_b;c/d`.
It also received `toggleconsole<set debug 0`, which reproduced the cleanup
failure. These observations identify incorrect characters, rather than a
demonstrated inability to parse semicolon-separated commands.

With the X server reporting Swedish symbols, explicitly using the physical
US positions produced `echo raw_begin;echo raw_end`; both echoes executed
separately and `condump arprobe.txt` succeeded. The game therefore interprets
these keys as US physical positions regardless of the server's symbol layout.
An additional controlled Swedish-to-US XKB switch confirmed that Python Xlib
also retains cached symbol mappings until MappingNotify events are handled.
Reading the current symbol map alone was tested and still failed in game;
it cannot correct the game's physical-key interpretation.

The fix resolves XKB physical key names using a bounded `xkbcomp` query and
maps printable ASCII to the game's US key positions. It does not alter the
server layout or rely on fixed evdev keycode numbers. Missing key positions
and unreadable maps fail before any prompt editing. The existing held-clear,
typing intervals, and nonce validation remain in place.

The offline regression reproduces the incorrect Swedish symbol bindings,
requires the physical positions for `_;/`, and checks alternate XKB keycode
assignments, missing Shift/keys, and keymap-query failure before input.
Runtime acceptance and final restoration are recorded below.

### Save-load acceptance

Both saved views passed with the default 120-second waiting budget. Each
load verified a fresh nonce-bounded transcript with the requested filename
and restored savegame lumps, followed by the expected settled camera. The
console closed, and a subsequent reopen required enabling developer mode,
confirming that its original disabled state had been restored. The diagnostic
reopen was also returned to the disabled state.

| Save | Verified position / yaw | Load command wall time, including cleanup |
| --- | --- | ---: |
| `steamuser/1` | `(1168, 1235, 336)` / `9` | 123.22 s |
| `steamuser/2` | `(756, 1289, 8)` / `11` | 123.14 s |

The timeout remains a waiting budget, not a hard wall-clock limit. The extra
post-load developer-state probes are excluded from these command timings.
The saves retain their previously recorded SHA-256 fingerprints. Captured
images show both distinct Rowdy's views with the console closed.

### Input boundaries

A 240-character command (`echo ` plus 235 `x` characters) was submitted and
its complete payload verified in a console dump. Recalling it from history
created the full stale prompt. The held clear then allowed a fresh
nonce-bounded `echo cleared` transcript to succeed.

Disabling global autorepeat on the nested display caused the rig to reject
input before editing the prompt; the original setting was restored. Separate
CLI children held Backspace and received SIGINT or SIGTERM after X's key-state
query confirmed the key was down. Each exited with the expected status and
the key-state query confirmed release. The console closed afterward.

The 33 offline tests cover unreadable/disabled repeat settings, keymap query
failures, missing physical keys, save/transcript checks, and key-release paths.
No wrapper code or lighting/material defaults changed. Initial post-load
lighting, other maps, and later-game visual checks remain separate work.

### Evidence and restoration

The follow-up used nested Xwayland `:7`, the existing Remix Plus/Proton setup,
and the previously verified wrapper DLL, SHA-256
`ae9c2ac5b15d2958ed33431437525a2de009e91d44d07669019f456cc25df32b`.
External power was confirmed before testing and during the session.

Local artifacts are retained under
`~/.cache/anoxrtx/console-runtime-2026-10-18/`: the incorrect-symbol and
physical-key transcripts, controlled keymap comparison, screenshots, accepted
save transcripts, input-boundary results, runtime logs, and recovery backups.
The completed session is `session3`; its `acceptance.json`, `boundaries.json`,
`manifest.json`, and `independent-restoration.json` summarize the checks.
They are outside the repository and contain no committed game assets.

Before cleanup, all 36 recorded game-file fingerprints, including all five
saves, were unchanged. The guard stopped the game/bridge, shut Steam down,
restored configuration backups and the original launch options, closed the
nested display, and restarted desktop Steam. A separate post-cleanup check
confirmed all 36 fingerprints, the five `.sav` files, unchanged wrapper DLL,
exact original launch options, closed `:7`, stopped game/bridge, and running
desktop Steam. All restoration checks passed.
