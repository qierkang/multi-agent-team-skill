# Multi-Agent Team Skill — English Guide

<p align="center">
  <a href="../README.md">简体中文</a> · <strong>English</strong>
</p>

<p align="center">
  <img src="../assets/social-preview.png?v=1" alt="Multi-Agent Team Skill" width="100%" />
</p>

`multi-agent-team-skill` is a reusable `SKILL.md` package for safe AI development-team orchestration. It turns multi-agent work from a set of long-lived chats into **role templates + an external task ledger + disposable execution instances**.

## Why

Persistent agent threads accumulate stale assumptions, coordinators become overloaded by raw logs, and existing repositories can be damaged by generic team bootstrap scripts. This skill first inspects the project state, then routes it to a safe workflow and requires deterministic evidence before it reports success.

## Overview

| Route | Default behavior | Result |
|---|---|---|
| `new` | dry-run before installation | managed role templates, ledger and task package |
| `existing-project` | non-invasive managed installation | backup-aware collaboration layer |
| `existing-team` | read-only audit | migration report and risks |
| `doctor` | read-only validation | explicit static validation state |
| `skill-health` | validates this source package | health and regression evidence |

## Features

- State-first routing with `inspect_team.py`, not directory-name guessing.
- Fresh, read-only reviewer instances that only receive acceptance criteria, final diff and test output.
- Role/model catalog for exploration, implementation, debugging, browser validation, architecture and evidence research.
- Externalized ledger, task package and summary records to keep coordinator context small.
- Default dry-run and explicit `--apply` for writes.
- Deterministic health checks plus new/existing environment regression.

## Comparison

| Approach | Safe for existing projects | Fresh review context | External state | Verified delivery |
|---|:---:|:---:|:---:|:---:|
| Multi-Agent Team Skill | yes | yes | yes | yes |
| Permanent sub-agent chats | manual | often no | often no | manual |
| Copying configs by hand | risky | no | inconsistent | no |

## Workflow

![Multi-Agent Team orchestration overview](../assets/architecture/en/team-orchestration-overview.png)

1. Inspect the target project read-only.
2. Choose the correct route and the smallest role profile.
3. Create execution instances from templates; keep artifacts in the ledger.
4. Review with a fresh read-only instance and verify through deterministic checks.

## Quick Start

### Prerequisites

- A coding environment that can load `SKILL.md` packages.
- Python 3.11+ and Bash.
- A target project path.

### Use as a Skill

```text
$multi-agent-team initialize the current project team
$multi-agent-team audit and optimize the current team
$multi-agent-team check whether the installed team is healthy
```

### Direct commands

```bash
# Inspect only; do not infer a route from the folder name.
python3 scripts/inspect_team.py --project <project-root>

# Preview first. It writes nothing by default.
python3 scripts/team_init.py --project <project-root> --profile auto

# Only after explicit approval.
python3 scripts/team_init.py --project <project-root> --profile auto --apply

# Existing teams are audited, not overwritten.
python3 scripts/team_audit.py --project <project-root>
python3 scripts/team_doctor.py --project <project-root>
```

## Modules

| Module | Responsibility |
|---|---|
| `scripts/` | inspect, initialize, audit, doctor and regression behavior |
| `templates/` | single source of truth for roles, configs and project documents |
| `references/` | progressive, route-specific operating rules |
| `governance/` | decisions, risks, changelog and health requirements |
| `install/` | local setup, safe sync and doctor entry points |
| `assets/` | public static visual assets only |

## Tech Stack

Python 3.11+ standard library, Bash, TOML, JSON and Markdown. The skill is intentionally dependency-light and keeps executable templates separate from presentation assets.

## Architecture

![Safe existing-skill upgrade flow](../assets/architecture/en/safe-existing-skill-upgrade.png)

The managed install never silently deletes work, overwrites business code or closes existing tasks. Existing-team routing produces an audit first; writing starts only after explicit confirmation.

## Directory

```text
multi-agent-team-skill/
├── SKILL.md          # minimal trigger and routing entry
├── templates/        # deployable source of truth
├── scripts/          # deterministic operations and checks
├── references/       # progressive documentation
├── governance/       # decisions, risks and release evidence
├── install/          # safe local install commands
├── examples/         # requests and regression evidence
└── assets/           # public visual assets + manifest
```

## Commands

| Command | Purpose |
|---|---|
| `inspect_team.py` | detect route read-only |
| `team_init.py` | preview or apply a managed installation |
| `team_audit.py` | inspect existing team state without overwriting it |
| `team_doctor.py` | validate one installed target project |
| `health_check.py --deep` | validate this skill plus two regression environments |
| `verify_assets.sh .` | validate public visual assets and README references |

## Development Guide

Edit the source of truth under `templates/`, then keep scripts, references and governance records aligned. Do not place project-specific names, credentials or local absolute paths in templates. Keep the top-level `SKILL.md` short and route detailed operating rules through `references/`.

## Validation

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
bash scripts/verify_assets.sh .
```

## Project Status

- Version: `0.2.0`
- Model: templates + ledger + disposable instances
- Write policy: dry-run first; `--apply` only after approval
- Release details: [CHANGELOG](../CHANGELOG.md)

## FAQ

**Do all eight roles run for every task?** No. Templates are available, but only the smallest relevant profile is instantiated.

**Can it rewrite a legacy repository?** No. Existing teams are audited first, and business code is outside the managed write scope.

**Why use a new reviewer?** A fresh reviewer does not inherit the implementation path or previous approval bias.

## Contributing

Read [CONTRIBUTING.md](../CONTRIBUTING.md), run all validation commands, and include the task scope, deterministic evidence and any migration impact in a pull request.

## Version

Follow semantic versioning. See [CHANGELOG.md](../CHANGELOG.md).

## Acknowledgements

The design follows Harness Engineering principles: source-of-truth templates, externalized state, fresh-context review and verification before completion claims.

## Star History

Star history is intentionally added only after the public repository exists; this package does not fabricate repository links or star counts.

## License

Released under the [MIT License](../LICENSE).

## Author

- xyqierkang@gmail.com
- https://github.com/qierkang
