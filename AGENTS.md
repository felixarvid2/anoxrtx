# Agent instructions: anoxrtx

## Project and context

This fork provides the Anachronox RTX Remix mod: configs, USD material layers,
asset generators, installer, and a Linux/Proton test rig. The companion
[felixarvid2/QindieGL](https://github.com/felixarvid2/QindieGL) fork supplies the
OpenGL-to-D3D9 wrapper and game hooks.

Start with `HANDOFF.md`, `README.md`, `TODO.md` and the doc map `docs/README.md` (architecture and
troubleshooting are in `docs/`); consult `RESULTS.md` and
`PLAN.md` for history and intended verification. For wrapper work, also read
QindieGL's `CLAUDE.md`, `AGENTS.md`, and `linux/README.md`.

Read `STATUS.md` for the reconciled implementation/verification snapshot and
`PLAN.md` for the ordered roadmap. `TODO.md` tracks those deliverables; older
`RESULTS.md`, `IDEAS.md`, `IDEAS2.md` and dated reports preserve history.
Distinguish implemented, tested in the game, and still unverified; do not mark
a visual task complete just because its generator or DLL builds. Keep README,
STATUS, HANDOFF and task status consistent when completing a milestone.

Startup device-replacement lighting is corrected and capture/comparison tools
are implemented; see `docs/startup-lighting-check.md` and
`docs/screenshot-regression.md`. Next work is Anachronox overlay diagnostics,
then game-driven event lighting. Timer styles
1–11, static emission, approximate PBR and the generic overlay already exist.
Keep model-routing proposals (#28 / QindieGL #23) separate from feature work.

Check branch and working-tree status in both repositories before cross-repository
work. QindieGL has multiple worktrees; verify which contains the required code.
Preserve unrelated changes. Use English for code and normal repo documentation;
the existing TODO, plan, and results are Swedish. Follow the user's language in
conversation; the handoff records Swedish as their usual preference.

## How to use agents

Use the role division from QindieGL's `CLAUDE.md` and `.claude/agents/`:

| Role | Assign it | Expected result |
| --- | --- | --- |
| Explore | Read-only searches through tools, configs, layers, and wrapper integration | Relevant `path:line` references, concise findings, and unknowns |
| Mechanic | Exact renames, config substitutions, or other fully specified edits | Minimal diff and check results; escalate design questions |
| Implementer | A specified generator, installer, material, or rig change | Focused implementation, relevant verification, and remaining visual checks |
| Architect / main agent | Unknown rendering failures, hash/API compatibility, or design across both repos | Evidence, options, and the smallest justified fix |

The original Claude models are Haiku for Explore/Mechanic, Sonnet for
Implementer, and Opus for Architect/main. Other agent tools should retain the
responsibilities using available capabilities, without assuming those model
names exist.

- Give Explore a question and scope. Give Implementer a clear behavior, file
  ownership, constraints, and verification target; give Mechanic an exact edit.
- Run independent tasks in parallel when useful, with separate file ownership.
  Serialize edits to shared config/layers and all use of the game, Steam launch
  settings, GPU, and test display.
- The main agent owns decisions, cross-repo compatibility, diff review, and final
  validation. Require each subagent to report changed files, checks actually run,
  uncertainties, and what still needs testing.
- Subagents do not commit, push, or merge unless explicitly assigned. Inspect
  their diffs and check output before accepting or shipping changes.

## Model routing and Gemini triage

For Codex work, use this model split requested by Felix:

| Work | Model |
| --- | --- |
| Read-only summaries of selected logs, documentation comparisons, fact extraction from supplied excerpts | Gemini `gemini-3.1-flash-lite` through the local `gemini-triage` skill |
| Routine exploration, validation orchestration, documentation, and exact mechanical edits | GPT-6 Luna |
| Substantial implementation, difficult debugging, and focused final review when needed | GPT-6.1 Sol |
| Disabled for this project unless Felix explicitly changes this preference | GPT-6 Astra |

After usage-limit feedback on 2026-10-17, prefer Gemini and Luna for bounded
work before escalating a concrete unresolved question to Sol. Keep returns
concise and evidence-based. Reuse verified results when inputs are unchanged;
repeat broad captures or reviews only when a new change or failure warrants it.

Gemini is an external API helper, not a native Codex subagent. It receives only
explicitly selected public project excerpts or sanitized logs, has no tools or
write access, and cannot validate builds. Codex reviews its findings and checks
source references before acting. Use local search for simple lookups.

The owner's local helper is
`~/.codex/skills/gemini-triage/scripts/triage.py`; consult that skill's `SKILL.md`
for invocation. At the 2026-10-18 documentation update, that local skill/helper
was absent from this environment; check availability before using it and fall
back to local work when missing. No Gemini request was made for the update.
The credential stays in `~/Documents/gemini-api.md`, outside the
repos, and must never appear in prompts, command arguments, URLs, logs, or git.
Do not upload game assets or private data as context. Free-tier data handling
follows Google's applicable terms.

Felix confirmed the API project uses the Free tier with billing disabled on
2026-10-17. Free pricing depends on that project setting; the API has no
per-request free-only flag. Do not enable billing. Pin the selected model, keep
requests bounded, and stop on quota errors; never silently retry or switch to a
paid service/model. If the helper or quota is unavailable, use the existing
Codex roles. The helper is a local installation, not a repo dependency.

## Boundaries and compatibility

- Keep reusable logic in `tools/`, settings in `rtx.conf` and
  `anox_customise.ini`, and wrapper behavior in QindieGL. Trace both sides of any
  map-light, procedural-texture, hash, or Remix API change.
- Never commit game data, extracted textures, DDS files, BSPs, generated asset
  layers, credentials, or built DLLs. Keep generators reproducible from the
  user's own game files. Preserve existing tracked mod assets.
- Texture hashes depend on mip 0 in D3D format (BGRA, opaque alpha where needed).
  Chuncki's texture pack changes hashes; use `tools/rehash_textures.py` and the
  mapping workflow documented in README rather than guessing replacements.
- Preserve the documented Wine fixes: frame generation and present metering
  disabled, old GUI input, NRC disabled with `rtx.integrateIndirectMode = 0`, and
  `presentSemaphoreEnabled = False` in `.trex/bridge.conf`. API lights require
  `exposeRemixApi = True`. Verify exact keys in current configs when editing.
- Keep Remix Plus Numos sky settings per map. Preserve the owner's disabled
  crash/usage reporting; do not bypass the first-use dialog with
  `rtx.automation.disableBlockingDialogBoxes`, which grants consent.

## Verification and runtime work

Choose checks that exercise the changed behavior: representative BSP/texture
inputs for generators, generated USD parsing when applicable, and installer
step/output checks for installation changes. Use existing tests when available.
Syntax checks alone do not establish correct hashes, materials, or installation.
Documentation-only edits need diff and link/path review.

For QindieGL code changes, follow its Linux build and 385-export checks. Report
MSVC and in-game verification separately from the cross-build result.

Follow `HANDOFF.md` for game paths and `tools/anoxrig.py` usage. Run game tests through
`tools/rigsession.sh` (it prepares the nested display/Steam and always restores them; workflow in
`.claude/skills/anox-game-test/SKILL.md`). Confirm those
local paths and tools still exist rather than relying on its temporary venv.
Use the nested Xwayland test display, back up game files before replacement, and
restore launch options, display settings, and Steam after every test, including
failures. Shut Steam down before editing its `localconfig.vdf`.

Never use `PROTON_ENABLE_WAYLAND` outside the nested session. Do not run the
Remix game alongside ComfyUI/FLUX on the documented 8 GB GPU. Use checked PIDs or
safe bracket patterns instead of a broad `pkill -f` that can kill its own shell.

Record map/view, runtime version, settings, screenshots, and relevant
`QindieGL.log` / Remix log evidence for visual changes. The rig's input and camera
timeout limitations are documented in the handoff; a timeout alone does not
prove the game crashed. Lava, combat lights, sun direction, PBR rims, and light
brightness outside Rowdy's still need the specific visual checks recorded there.

Update task status only with evidence, retaining the Swedish backlog's
implemented-but-unverified distinction. Follow the handoff's branch/PR workflow
when shipping implementation work, with final review and integration owned by
the main agent.
