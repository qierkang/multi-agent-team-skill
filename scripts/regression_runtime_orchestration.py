#!/usr/bin/env python3
"""Fault-oriented regression suite for v2 long-running task orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts/team_init.py"
ORCH = ROOT / "scripts/thread_orchestrator.py"
MODEL_ARGS = (
    "--model-fast", "gpt-5.3-codex-spark",
    "--model-standard", "gpt-5.3-codex",
    "--model-advanced", "gpt-5.4",
)


def run(*args: object, expected: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(item) for item in args], text=True, capture_output=True, check=False)
    if result.returncode not in expected:
        raise AssertionError(f"exit={result.returncode} args={args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def require(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def write_task(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def plan(project: Path, task: Path) -> dict[str, object]:
    output = run("python3", ORCH, "plan", "--project", project, "--task-json", task).stdout
    return json.loads(output.split("\nSTATE=", 1)[0])


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="multi-agent-team-runtime-"))
    passed: list[str] = []
    try:
        project = sandbox / "project"
        project.mkdir()
        run("python3", INIT, "--project", project, "--profile", "core", "--thread-mode", "controlled-auto", "--apply", *MODEL_ARGS)

        concurrent = sandbox / "concurrent"
        concurrent.mkdir()
        run("python3", INIT, "--project", concurrent, "--profile", "core", "--thread-mode", "controlled-auto", "--apply", *MODEL_ARGS)
        commands = [
            ["python3", str(ORCH), "register", "--project", str(concurrent), "--domain-key", f"domain-{index}", "--thread-id", f"concurrent-{index}", "--title", f"concurrent {index}", "--model", "gpt-5.3-codex", "--owned-path", f"src/domain-{index}", "--apply"]
            for index in (1, 2)
        ]
        processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
        results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
        require(all(code == 0 for _, _, code in results), f"concurrent register failed: {results}")
        concurrent_registry = json.loads((concurrent / ".codex/team/thread-registry.json").read_text(encoding="utf-8"))
        require(concurrent_registry["revision"] == 2 and len(concurrent_registry["threads"]) == 2, "concurrent registration lost an update")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", concurrent).stdout, "concurrent registry health failed")
        passed.append("cross-process runtime lock prevents lost registry updates")

        low = write_task(project, "low", {"domain_key": "docs", "title": "fix typo", "task_type": "docs", "risk": "low", "owned_paths": ["README.md"]})
        medium = write_task(project, "medium", {"domain_key": "api", "title": "bounded api work", "task_packages": 3, "independent_boundary": True, "owned_paths": ["src/api"]})
        high = write_task(project, "high", {"domain_key": "billing", "title": "billing migration", "task_type": "migration", "risk": "high", "expected_days": 3, "task_packages": 4, "independent_boundary": True, "recurring": True, "owned_paths": ["src/billing"]})
        low_plan, medium_plan, high_plan = plan(project, low), plan(project, medium), plan(project, high)
        require(low_plan["decision"] == "handle_in_main" and low_plan["model_tier"] == "fast", "low routing mismatch")
        require(medium_plan["decision"] == "use_subagents", "medium routing mismatch")
        require(high_plan["decision"] == "create_thread" and high_plan["model_tier"] == "advanced", "high routing mismatch")
        passed.append("deterministic scoring chooses main, subagents or long-running task and model tier")

        registry = project / ".codex/team/thread-registry.json"
        before = registry.read_bytes()
        dry = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1").stdout
        require("STATE=thread_register_plan_ready" in dry and registry.read_bytes() == before, "register dry-run wrote state")
        applied = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1", "--expected-revision", "0", "--apply").stdout
        require("STATE=thread_registered" in applied, "thread registration failed")
        replay = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1", "--apply").stdout
        require("STATE=thread_already_registered" in replay, "idempotent replay failed")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", project).stdout, "healthy registry failed")
        passed.append("dry-run, CAS revision, idempotency and derived state remain consistent")

        reuse_plan = plan(project, high)
        require(
            reuse_plan["decision"] == "reuse_thread" and reuse_plan["existing_thread_id"] == "thread-1",
            "same-domain task did not reuse the registered long-running thread",
        )
        invalid_contract = write_task(project, "invalid-contract", {
            "domain_key": "catalog",
            "title": "invalid explicit reuse",
            "existing_thread_id": "thread-1",
        })
        invalid_result = run(
            "python3", ORCH, "plan", "--project", project, "--task-json", invalid_contract,
            expected=(2,),
        )
        require("unknown fields: existing_thread_id" in invalid_result.stderr, "unknown task field was silently ignored")
        passed.append("task contract rejects unknown reuse ids and registry domain drives reuse")

        conflicting = write_task(project, "conflict", {"domain_key": "checkout", "title": "checkout", "expected_days": 2, "task_packages": 4, "independent_boundary": True, "recurring": True, "owned_paths": ["src"]})
        require(plan(project, conflicting)["decision"] == "blocked_ownership_conflict", "ownership conflict not blocked")
        stale = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-1", "--stage", "stale", "--expected-revision", "0", "--apply", expected=(2,))
        require("STATE=thread_orchestration_failed" in stale.stdout, "stale revision was accepted")
        passed.append("ownership collisions and stale writers fail closed")

        run("python3", ORCH, "register", "--project", project, "--domain-key", "catalog", "--thread-id", "thread-w2", "--title", "catalog work", "--model", str(medium_plan["model"]), "--owned-path", "src/catalog", "--apply")
        third_writer = write_task(project, "third-writer", {"domain_key": "search", "title": "search work", "expected_days": 2, "task_packages": 4, "independent_boundary": True, "recurring": True, "owned_paths": ["src/search"]})
        require(plan(project, third_writer)["decision"] == "queue_writer_capacity", "writer capacity was not planned")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-w2", "--status", "completed", "--evidence", "artifacts/catalog.log", "--apply")
        passed.append("long-running writer capacity is enforced before dispatch")

        for used, expected_exit, marker in ((84000, 2, "context compaction"), (102000, 2, "scope freeze"), (120000, 1, "budget exhausted")):
            run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-1", "--token-used", used, "--apply")
            health = run("python3", ORCH, "health", "--project", project, expected=(expected_exit,)).stdout
            require(marker in health, f"missing token guardrail: {marker}")
        passed.append("token guardrails trigger at 70, 85 and 100 percent")

        no_evidence = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-1", "--status", "completed", "--apply", expected=(2,))
        require("requires at least one evidence" in no_evidence.stderr, "completion without evidence was accepted")
        completed = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-1", "--status", "completed", "--stage", "verified", "--summary", "migration complete", "--evidence", "artifacts/billing-test.log", "--apply").stdout
        require("STATE=thread_updated" in completed, "evidence-backed completion failed")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", project).stdout, "terminal thread health mismatch")
        passed.append("completion gate requires evidence and terminal tasks release ownership")

        run("python3", ORCH, "register", "--project", project, "--domain-key", "support", "--thread-id", "thread-old", "--title", "old support", "--model", str(medium_plan["model"]), "--owned-path", "src/support", "--apply")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-old", "--status", "blocked", "--apply")
        run("python3", ORCH, "register", "--project", project, "--domain-key", "support", "--thread-id", "thread-new", "--title", "new support", "--model", str(medium_plan["model"]), "--owned-path", "src/support", "--apply")
        resume = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-old", "--status", "active", "--apply", expected=(2,))
        require("cannot resume" in resume.stderr, "blocked thread resumed into an ownership collision")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-new", "--status", "completed", "--evidence", "artifacts/support.log", "--apply")
        passed.append("resuming a blocked task rechecks domain, ownership and capacity")

        locks_path = project / ".codex/team/ownership-locks.json"
        locks = json.loads(locks_path.read_text(encoding="utf-8"))
        locks["revision"] = -1
        locks_path.write_text(json.dumps(locks), encoding="utf-8")
        drift = run("python3", ORCH, "health", "--project", project, expected=(1,)).stdout
        require("locks drift" in drift, "derived-state drift was not detected")
        reconcile = run("python3", ORCH, "reconcile", "--project", project, "--apply").stdout
        require("STATE=runtime_state_reconciled" in reconcile, "reconcile failed")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", project).stdout, "reconciled health failed")
        budget_path = project / ".codex/team/budget-state.json"
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
        budget["project_token_used"] += 1
        budget_path.write_text(json.dumps(budget), encoding="utf-8")
        budget_drift = run("python3", ORCH, "health", "--project", project, expected=(1,)).stdout
        require("budget state drifts" in budget_drift, "project token total drift was not detected")
        run("python3", ORCH, "reconcile", "--project", project, "--apply")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", project).stdout, "budget reconcile failed")
        passed.append("ownership and project-token drift are detectable and recoverable")

        invalid = write_task(project, "invalid", {"domain_key": "escape", "title": "escape", "owned_paths": ["../outside"]})
        escaped = run("python3", ORCH, "plan", "--project", project, "--task-json", invalid, expected=(2,))
        require("STATE=thread_orchestration_failed" in escaped.stdout, "path traversal was accepted")
        passed.append("owned path traversal is rejected")

        for item in passed:
            print(f"PASS {item}")
        print(f"STATE=runtime_orchestration_regression_passed; checks={len(passed)}")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
