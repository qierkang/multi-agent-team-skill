# Multi-Agent Team Skill v2

<p align="center">
  <a href="../README.md">简体中文</a> · <a href="./README_zh-tw.md">繁體中文</a> · <a href="./README_en.md">English</a>
</p>

<p align="center"><img src="../assets/social-preview.png?v=2" alt="Multi-Agent Team Skill" width="100%" /></p>

Version 2.0.0 makes the main task a `control-plane-only` coordinator. It may inspect, split, queue, dispatch, monitor, accept, report, and write managed orchestration state, but it does not edit production code.

![Two-lane orchestration](../assets/architecture/en/team-orchestration-overview.png)

## Inspect first

Users only need to ask the Skill to initialize, upgrade, or check a project. They do not need to choose internal orchestrator or lane terms.

```bash
python3 scripts/inspect_team.py --project <project-root>
```

| Route | Safe default |
|---|---|
| `new` | dry-run initialization |
| `existing-project` | non-invasive dry-run installation |
| `existing-team:v1` | deterministic schema-1 to schema-2 migration |
| `existing-team:v2-upgrade` | transactional managed 1.x to 2.0.0 upgrade |
| `existing-team:v2` | doctor and runtime health |
| `existing-team:audit` | read-only audit; unknown schemas fail closed |

## Fast lane and project lane

| Lane | Use | Lifecycle | Packet and review |
|---|---|---|---|
| fast | ordinary bounded work | one-shot agent, released on completion | minimal packet for light work; review on failure |
| project | multi-day or durable domain work | create or reuse a long-running domain task | full packet; fresh reviewer for high risk |

The only supported hierarchy is main control plane -> project task -> one-shot agent. A project task cannot create another project task.

The queue is unbounded, while active execution is capped at six and active writers at two. Dependencies, ancestor path ownership, heartbeat, timeout, status, handoff, revision CAS, and evidence are persisted in `.codex/team/`.

## Model routing and replacement

| Tier | Default | Typical work |
|---|---|---|
| fast | `gpt-5.6-luna` | exploration and light mechanical work |
| standard | `gpt-5.6-terra` | implementation, debugging, and testing |
| advanced | `gpt-5.6-sol` | architecture, security, migration, and fresh review |

A running instance never changes models. Two failures with the same fingerprint require a saved handoff, termination of the old instance, and a new higher-tier instance. `replace` records generation and `replaces_instance_id`.

High and critical risk always use a fresh read-only reviewer. Light low-risk work uses the [minimal dispatch packet](../templates/project/docs/最小派发包.template.md) and switches to the [full task packet](../templates/project/docs/任务包.template.md) on failure or scope growth.

## Commands

```bash
# Inspect first
python3 scripts/inspect_team.py --project <path>

# Initialize or upgrade: dry-run by default
python3 scripts/team_init.py --project <path> --profile auto
python3 scripts/team_upgrade.py --project <path>

# Apply only after review and explicit intent
python3 scripts/team_init.py --project <path> --profile auto --apply
python3 scripts/team_upgrade.py --project <path> --apply
python3 scripts/team_upgrade.py --project <path> --thread-mode controlled-auto --apply

# Static and runtime checks
python3 scripts/team_doctor.py --project <path>
python3 scripts/thread_orchestrator.py health --project <path>
python3 scripts/runtime_smoke.py --project <path> --explorer-evidence artifacts/explorer-smoke.log --apply
python3 scripts/runtime_smoke.py --project <path> --reviewer-evidence artifacts/reviewer-smoke.log --apply

# Plan, queue, and bind a client instance
python3 scripts/thread_orchestrator.py plan --project <path> --task-json task.json
python3 scripts/thread_orchestrator.py enqueue --project <path> --task-json task.json --task-id TASK-001 --apply
python3 scripts/thread_orchestrator.py dispatch --project <path> --task-id TASK-001 --instance-id <id> --apply
```

Keep Codex `agents.max_depth=1`: managed registry depth 2 means the main control plane dispatches a one-shot Agent on behalf of a project task, not recursive Agent spawning. Runtime smoke remains `pending` without real client output, becomes `partial_done` with one role's non-empty evidence, and reaches `runtime_validation_done` only with both explorer and fresh-reviewer evidence.

An explicit v2 `--thread-mode controlled-auto` upgrade updates both the manifest and project state; it never waives approval for publishing, production writes, paid actions, or credential changes. Model-tier reconfiguration returns `replacement_required` without writes when an active or resumable instance exists. Every completion or smoke evidence path must be project-relative, traversal-free, existing, non-empty, and non-symlinked. A blocked task can resume only with prior dispatch metadata, a real handoff artifact, and fresh dependency/ownership/capacity admission.

See the [runtime contract](../references/runtime-orchestration.md), [migration rules](../references/schema-migration.md), and [completion gate](../references/completion-gate.md).

## Safe installation and migration

New projects receive managed role, policy, ledger, and runtime files. Existing projects keep business files, build tools, technology choices, existing docs, and unrelated configuration. Managed changes are backed up and transactionally written. Unknown schemas, customized managed roles, symlink escapes, ignored managed paths, and configuration conflicts fail closed.

![Safe existing-team upgrade](../assets/architecture/en/safe-existing-skill-upgrade.png)

## Verification

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
python3 scripts/check_readme_links.py
bash scripts/verify_assets.sh
```

The deep gate covers inspect, init, upgrade, doctor, health, orchestration, new/existing/runtime regressions, optimized Python execution, README links, and registered visual references. If an official Skill validator is installed, run its `quick_validate.py` as an additional gate.

- [v2 regression evidence](../examples/regression-evidence-2026-07-18-v2.md)
- [production scorecard](../governance/PRODUCTION-SCORECARD.md)
- [changelog](../CHANGELOG.md)
- [security](../SECURITY.md)

Templates are deployable sources of truth; assets are static visuals only. Templates contain no customer identity, business-specific project names, machine-local absolute paths, or credentials. External publishing, production writes, paid actions, and credential changes always require separate explicit approval.

Author: `xyqierkang@gmail.com` · [GitHub](https://github.com/qierkang)
