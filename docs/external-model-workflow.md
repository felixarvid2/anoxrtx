# External model workflow

Felix requested external-first delegation to reduce Codex usage. The routing
table in `AGENTS.md` applies to this repository and QindieGL. The installed
helpers are local tools, not project dependencies or native Codex subagents.

## Local installation

- NVIDIA helper: `~/.codex/skills/external-models/SKILL.md`
- Gemini helper: `~/.codex/skills/gemini-triage/SKILL.md`
- Persistent task packets, responses and usage: `~/.cache/anoxrtx/external-models/`

The NVIDIA helper reads the configured GLM and DeepSeek credential files
directly and only uses `https://integrate.api.nvidia.com/v1`. Generation
availability must be checked; successful model listing alone does not prove
generation access. Free model access can change. Do not switch to a paid
partner, purchase credits or change billing settings.

## Bounded tasks

Collect relevant code, changes and evidence with local searches. Give the
external worker a specific question, labeled context and an expected result.
Project context, including unpublished changes, is authorized for GLM,
DeepSeek and Gemini. Keep credentials, game assets and unrelated files out
of prompts. Only local execution may apply patches, run checks or control
the game, Steam and Git.

Example after checking the endpoint:

```sh
python3 ~/.codex/skills/external-models/scripts/assist.py \
  --provider glm --model z-ai/glm-5.3-flash --kind analysis \
  --job console-investigation \
  --task ~/.cache/anoxrtx/external-models/task-packets/task.txt \
  --context ~/.cache/anoxrtx/external-models/task-packets/context.txt
```

Use the same job identifier for follow-ups on one bounded task. Up to three
generation requests share a persisted budget. Per-request caps are 2,000
output tokens for analysis and 8,000 for patch proposals; the cumulative
reservation ceiling defaults to 24,000. Combined input is at most 64 KiB.
Successful unchanged requests are cached. Full content stays in artifacts;
only paths and usage metadata are printed. Read the relevant result once,
then pass concise findings and actual verification results to the coordinator.

Do not duplicate a completed external analysis in a native agent. Use focused
review for substantial changes, rather than routinely asking every model.
Stop a provider on authentication, model or quota errors. Use another verified
free helper or Luna when useful; Sol requires a concrete unresolved question.

## Evidence and recovery

Measure provider usage from the recorded `usage.jsonl` entries. Missing token
counts remain unknown; do not infer a percentage reduction in Codex usage.
Validate proposed patches and test claims locally. Keep task artifacts and
runtime backups on persistent storage. Before game testing, check external
power and serialize ownership of Steam, the GPU and the nested test display.

The first migration task is draft PR #27's console-input investigation.
Changing model routing does not establish that the rig is fixed; retain
its existing draft status until the documented game checks pass.
