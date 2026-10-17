# Agent instructions: anoxrtx

## Project and context

This fork provides the Anachronox RTX Remix mod: configs, USD material layers,
asset generators, installer, and a Linux/Proton test rig. The companion
[felixarvid2/QindieGL](https://github.com/felixarvid2/QindieGL) fork supplies the
OpenGL-to-D3D9 wrapper and game hooks.

Start with `HANDOFF.md`, `README.md`, and `TODO.md`; consult `RESULTS.md` and
`PLAN.md` for history and intended verification. For wrapper work, also read
QindieGL's `CLAUDE.md`, `AGENTS.md`, and `linux/README.md`.

`TODO.md` contains older open items that later documentation describes as
implemented, including DLSS, light styles, emissive/PBR materials, fog, and
packaging. Reconcile these with the current code and handoff before choosing
work. Distinguish implemented, tested in the game, and still unverified; do not
mark a visual task complete just because its generator or DLL builds.

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

## Model routing and external helpers

Use external models as the default workers to reduce Codex usage:

| Work | Model |
| --- | --- |
| Routine source exploration, log analysis, documentation and small patch proposals | NVIDIA `z-ai/glm-5.3-flash` |
| Substantial implementation, difficult debugging and design proposals | NVIDIA `z-ai/glm-5.3` |
| Focused review of substantial changes and alternative failure explanations | NVIDIA `deepseek-ai/deepseek-v4.1-flash` |
| Bulk summaries and simple fact extraction | Gemini `gemini-3.1-flash-lite` |
| Local tools, applying reviewed patches, tests and Git operations | GPT-6 Luna |
| Concrete unresolved questions and consequential final review | GPT-6.1 Sol |
| Disabled unless Felix explicitly changes this preference | GPT-6 Astra |

The local NVIDIA helper and instructions are in
`~/.codex/skills/external-models/SKILL.md`; Gemini uses
`~/.codex/skills/gemini-triage/SKILL.md`. These are external API helpers,
not native Codex subagents. They propose patches or findings; local execution
retains control of files, game sessions, Steam and Git. Never accept a model's
claim that checks ran without running them locally.

Felix authorized selected project code, unpublished changes and relevant logs
as external context. Send task-relevant excerpts, not the conversation history
or entire repositories. Credentials stay in `~/Documents/glm-nvidia.md`,
`~/Documents/deepseek-nvidia.md` and `~/Documents/gemini-api.md`; never include
them in prompts, arguments, logs or git. Keep game assets, saves and unrelated
private files outside task packets.

NVIDIA usage is free-only: verify the configured endpoint/model before activation;
never enable billing, purchase credits or route to paid partner endpoints.
The API has no per-request free-only flag. Gemini's project was confirmed on
2026-10-17 to have billing disabled. Stop a provider for the task on quota,
authentication or unavailable-model errors; do not rotate keys to bypass limits.
Try another verified free helper, then Luna if needed; no automatic Sol escalation.

Keep full responses locally and return concise summaries, artifact paths and
actual check results. Default packets are at most 64 KB; analysis output is
capped at 2,000 tokens and patch output at 8,000. Limit a bounded task to three
NVIDIA generation requests across models. Reuse successful results when task,
model and inputs are unchanged. Review substantial changes with DeepSeek when
useful; do not duplicate reviews or repeat checks without a concrete reason.
Report measured provider usage; do not invent Codex savings percentages.

Keep task artifacts, worktrees and runtime recovery backups on persistent
storage. The 2026-10-17 laptop restart was caused by battery depletion, as
confirmed by Felix. Check external power before game tests, keep runtime
ownership serialized and restore the owner's settings on exit.

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

Follow `HANDOFF.md` for game paths and `tools/anoxrig.py` usage. Confirm those
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
