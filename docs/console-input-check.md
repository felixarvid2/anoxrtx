# Console input investigation, 2026-10-17

Status: draft implementation; complete save loading remains unverified.

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

## Runtime result

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
in a persistent worktree and tested offline. No further game launch was made.

## Recovery and remaining checks

Only the test `DISPLAY=:7` prefix and `+map rowdys` suffix were removed from
Steam's app launch options after shutting Steam down. The write was verified
and desktop Steam was requested to restart. The installed DLL and both test
save fingerprints still match the prior recorded values. Other config files
cannot be claimed byte-for-byte restored because their temporary pre-test
backups were lost. Recovery notes and the post-reboot Steam config backup are
kept locally under `~/.cache/anoxrtx/recovery/`, outside git.

Before considering this fixed, reproduce the compound-command failure with
small commands, confirm received input, verify developer-state cleanup, then
load both saved views using the normal timeout. Check a full stale prompt and
disabled-repeat behavior. Keep runtime backups and worktrees on persistent
storage so a restart cannot remove the recovery material.
