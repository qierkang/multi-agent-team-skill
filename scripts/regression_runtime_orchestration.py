#!/usr/bin/env python3
"""Fault-oriented regression suite for v2 long-running task orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts/team_init.py"
ORCH = ROOT / "scripts/thread_orchestrator.py"
DOCTOR = ROOT / "scripts/team_doctor.py"
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


def write_artifact(root: Path, relative: str, content: str = "verified evidence\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
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
        for relative in (
            "artifacts/fast-base.log",
            "artifacts/fast-dependent.log",
            "artifacts/handoff.md",
            "artifacts/escalating.log",
            "artifacts/timeout.log",
            "artifacts/catalog.log",
            "artifacts/billing-test.log",
            "artifacts/support.log",
            "artifacts/support-old.log",
        ):
            write_artifact(project, relative)
        outside_evidence = write_artifact(sandbox, "outside-proof.log")
        write_artifact(project, "artifacts/empty.log", "")
        (project / "artifacts/symlink.log").symlink_to("fast-base.log")

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

        ready = sandbox / "writer-ready"
        release = sandbox / "writer-release"
        writer_code = """
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from runtime_state import THREAD_REGISTRY, load_json, runtime_lock, safe_state_path
from thread_orchestrator import sync_derived_state, write_registry

root = Path(sys.argv[2]).resolve()
ready = Path(sys.argv[3])
release = Path(sys.argv[4])
with runtime_lock(root):
    registry = load_json(safe_state_path(root, THREAD_REGISTRY))
    registry["threads"][0]["current_stage"] = "writer-in-flight"
    write_registry(root, registry)
    ready.write_text("ready", encoding="utf-8")
    while not release.exists():
        time.sleep(0.01)
    sync_derived_state(root, registry)
"""
        writer = subprocess.Popen(
            ["python3", "-c", writer_code, str(ROOT / "scripts"), str(concurrent), str(ready), str(release)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 10
        while not ready.exists() and writer.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        if not ready.exists():
            release.write_text("release", encoding="utf-8")
            writer_output = writer.communicate(timeout=5)
            raise AssertionError(f"concurrent writer did not reach in-flight state: {writer_output}")
        health_process = subprocess.Popen(
            ["python3", str(ORCH), "health", "--project", str(concurrent)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        health_blocked = False
        early_health: tuple[str, str] | None = None
        try:
            early_health = health_process.communicate(timeout=0.3)
        except subprocess.TimeoutExpired:
            health_blocked = True
        finally:
            release.write_text("release", encoding="utf-8")
        writer_output = writer.communicate(timeout=10)
        health_output = health_process.communicate(timeout=10) if health_blocked else early_health
        require(writer.returncode == 0, f"in-flight writer failed: {writer_output}")
        require(health_blocked, f"health read an inconsistent in-flight snapshot: {health_output}")
        require(
            health_process.returncode == 0
            and health_output is not None
            and "STATE=runtime_health_passed" in health_output[0],
            f"health did not pass after the locked write completed: {health_output}",
        )
        passed.append("health waits on the runtime lock and reads one consistent registry/derived-state snapshot")

        low = write_task(project, "low", {"domain_key": "docs", "title": "fix typo", "task_type": "docs", "risk": "low", "owned_paths": ["README.md"]})
        medium = write_task(project, "medium", {"domain_key": "api", "title": "bounded api work", "task_packages": 3, "independent_boundary": True, "owned_paths": ["src/api"]})
        high = write_task(project, "high", {"domain_key": "billing", "title": "billing migration", "task_type": "migration", "risk": "high", "expected_days": 3, "task_packages": 4, "independent_boundary": True, "recurring": True, "owned_paths": ["src/billing"]})
        low_plan, medium_plan, high_plan = plan(project, low), plan(project, medium), plan(project, high)
        require(low_plan["decision"] == "dispatch_fast_agent" and low_plan["model_tier"] == "fast", "low routing mismatch")
        require(low_plan["dispatch_packet"] == "minimal" and low_plan["review_policy"] == "on-failure", "light dispatch policy mismatch")
        require(medium_plan["decision"] == "dispatch_fast_agent" and medium_plan["dispatch_packet"] == "full", "medium routing mismatch")
        require(high_plan["decision"] == "create_project_thread" and high_plan["model_tier"] == "advanced", "high routing mismatch")
        require(high_plan["review_policy"] == "always-fresh-reviewer", "high-risk review policy mismatch")
        require(all(item["control_plane_mode"] == "control-plane-only" for item in (low_plan, medium_plan, high_plan)), "planner allows main-task implementation")
        passed.append("deterministic dual-lane routing keeps the main task control-plane-only")

        registry = project / ".codex/team/thread-registry.json"
        base_before = registry.read_bytes()
        enqueue_dry = run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", low,
            "--task-id", "fast-base",
        ).stdout
        require("STATE=work_enqueue_plan_ready" in enqueue_dry and registry.read_bytes() == base_before, "enqueue dry-run wrote state")
        run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", low,
            "--task-id", "fast-base", "--apply",
        )
        blocked_dependency = write_task(project, "dependent", {
            "domain_key": "dependent",
            "title": "dependent docs",
            "task_type": "docs",
            "risk": "low",
            "dependencies": ["fast-base"],
        })
        run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", blocked_dependency,
            "--task-id", "fast-dependent", "--apply",
        )
        blocked_dispatch = run(
            "python3", ORCH, "dispatch", "--project", project, "--task-id", "fast-dependent",
            "--instance-id", "agent-dependent", "--apply", expected=(2,),
        )
        require("dependencies are not completed" in blocked_dispatch.stderr, "incomplete dependency dispatched")
        bypass = run(
            "python3", ORCH, "update", "--project", project, "--thread-id", "fast-dependent",
            "--status", "active", "--apply", expected=(2,),
        )
        require("invalid status transition" in bypass.stderr, "update bypassed dependency-aware dispatch")
        run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", blocked_dependency,
            "--task-id", "blocked-bypass", "--apply",
        )
        run(
            "python3", ORCH, "update", "--project", project, "--thread-id", "blocked-bypass",
            "--status", "blocked", "--apply",
        )
        blocked_before = registry.read_bytes()
        blocked_resume = run(
            "python3", ORCH, "update", "--project", project, "--thread-id", "blocked-bypass",
            "--status", "active", "--handoff", "artifacts/handoff.md", "--apply", expected=(2,),
        )
        require(
            "task has never been dispatched" in blocked_resume.stderr and registry.read_bytes() == blocked_before,
            "queued -> blocked -> active bypass mutated the registry",
        )
        run(
            "python3", ORCH, "dispatch", "--project", project, "--task-id", "fast-base",
            "--instance-id", "agent-base", "--apply",
        )
        run(
            "python3", ORCH, "update", "--project", project, "--thread-id", "fast-base",
            "--status", "completed", "--evidence", "artifacts/fast-base.log", "--apply",
        )
        run(
            "python3", ORCH, "dispatch", "--project", project, "--task-id", "fast-dependent",
            "--instance-id", "agent-dependent", "--apply",
        )
        run(
            "python3", ORCH, "update", "--project", project, "--thread-id", "fast-dependent",
            "--status", "completed", "--evidence", "artifacts/fast-dependent.log", "--apply",
        )
        healthy_registry = json.loads(registry.read_text(encoding="utf-8"))
        fast_base_record = next(item for item in healthy_registry["threads"] if item["id"] == "fast-base")
        fast_base_record["evidence_paths"] = ["artifacts/missing-health.log"]
        registry.write_text(json.dumps(healthy_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", ORCH, "reconcile", "--project", project, "--apply")
        invalid_health = run("python3", ORCH, "health", "--project", project, expected=(1,)).stdout
        invalid_doctor = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("invalid evidence path for fast-base" in invalid_health, "health accepted missing persisted evidence")
        require("thread evidence fast-base" in invalid_doctor, "doctor accepted missing persisted evidence")
        fast_base_record["evidence_paths"] = ["artifacts/fast-base.log"]
        registry.write_text(json.dumps(healthy_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", ORCH, "reconcile", "--project", project, "--apply")
        for index in range(12):
            queued_task = write_task(project, f"queued-{index}", {
                "domain_key": f"queued-{index}",
                "title": f"queued work {index}",
                "task_type": "docs",
                "risk": "low",
            })
            run(
                "python3", ORCH, "enqueue", "--project", project, "--task-json", queued_task,
                "--task-id", f"queued-{index}", "--apply",
            )
        health_payload = json.loads(
            run("python3", ORCH, "health", "--project", project, "--json").stdout.split("\nSTATE=", 1)[0]
        )
        require(health_payload["queued_tasks"] == 12, "queue was capped or queue count is wrong")
        passed.append("unbounded queue preserves dependencies while dispatch remains dry-run and capacity controlled")

        before = registry.read_bytes()
        current_revision = json.loads(before)["revision"]
        dry = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1").stdout
        require("STATE=thread_register_plan_ready" in dry and registry.read_bytes() == before, "register dry-run wrote state")
        applied = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1", "--expected-revision", str(current_revision), "--apply").stdout
        require("STATE=thread_registered" in applied, "thread registration failed")
        replay = run("python3", ORCH, "register", "--project", project, "--domain-key", "billing", "--thread-id", "thread-1", "--title", "billing migration", "--model", str(high_plan["model"]), "--owned-path", "src/billing", "--idempotency-key", "billing-v1", "--apply").stdout
        require("STATE=thread_already_registered" in replay, "idempotent replay failed")
        require("STATE=runtime_health_passed" in run("python3", ORCH, "health", "--project", project).stdout, "healthy registry failed")
        passed.append("dry-run, CAS revision, idempotency and derived state remain consistent")

        invalid_evidence_cases = (
            (str(outside_evidence), "project-relative"),
            ("../outside-proof.log", "project-relative"),
            ("artifacts/missing.log", "does not exist"),
            ("artifacts/empty.log", "non-empty"),
            ("artifacts/symlink.log", "contains symlink"),
        )
        for invalid_path, marker in invalid_evidence_cases:
            unchanged = registry.read_bytes()
            rejected = run(
                "python3", ORCH, "update", "--project", project, "--thread-id", "thread-1",
                "--status", "completed", "--evidence", invalid_path, "--apply", expected=(2,),
            )
            require(marker in rejected.stderr, f"invalid evidence was not rejected: {invalid_path}")
            require(registry.read_bytes() == unchanged, f"invalid evidence mutated registry: {invalid_path}")
        passed.append("completion, health and doctor reject absolute, traversal, missing, empty and symlink evidence")

        child_task = write_task(project, "child", {
            "domain_key": "billing-child",
            "title": "bounded child",
            "task_type": "docs",
            "risk": "low",
            "parent_thread_id": "thread-1",
        })
        run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", child_task,
            "--task-id", "child-1", "--apply",
        )
        child_record = json.loads(registry.read_text(encoding="utf-8"))["threads"][-1]
        require(child_record["lane"] == "fast" and child_record["depth"] == 2, "project child nesting mismatch")
        too_deep = run(
            "python3", ORCH, "enqueue", "--project", project, "--task-json", low,
            "--task-id", "grandchild", "--parent-thread-id", "child-1", "--apply", expected=(2,),
        )
        require("parent must be an active project-lane task" in too_deep.stderr, "deeper nesting was accepted")
        passed.append("project tasks may dispatch one-shot agents but deeper nesting is rejected")

        escalating = write_task(project, "escalating", {
            "domain_key": "escalating",
            "title": "bounded implementation",
            "task_packages": 3,
            "independent_boundary": True,
            "risk": "medium",
        })
        run("python3", ORCH, "enqueue", "--project", project, "--task-json", escalating, "--task-id", "escalating", "--apply")
        run("python3", ORCH, "dispatch", "--project", project, "--task-id", "escalating", "--instance-id", "terra-1", "--apply")
        run("python3", ORCH, "fail", "--project", project, "--task-id", "escalating", "--fingerprint", "same-cause", "--handoff", "artifacts/handoff.md", "--apply")
        run("python3", ORCH, "fail", "--project", project, "--task-id", "escalating", "--fingerprint", "same-cause", "--handoff", "artifacts/handoff.md", "--apply")
        escalated = next(item for item in json.loads(registry.read_text(encoding="utf-8"))["threads"] if item["id"] == "escalating")
        require(escalated["status"] == "escalation_required" and escalated["instance_id"] == "terra-1", "running instance changed brain during escalation")
        require(escalated["required_model"] == "gpt-5.4", "same-cause failure did not route to Sol")
        run(
            "python3", ORCH, "replace", "--project", project, "--task-id", "escalating",
            "--new-instance-id", "sol-2", "--new-model", "gpt-5.4", "--handoff", "artifacts/handoff.md", "--apply",
        )
        replaced = next(item for item in json.loads(registry.read_text(encoding="utf-8"))["threads"] if item["id"] == "escalating")
        require(replaced["instance_id"] == "sol-2" and replaced["replaces_instance_id"] == "terra-1" and replaced["generation"] == 2, "replacement handoff mismatch")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "escalating", "--status", "completed", "--evidence", "artifacts/escalating.log", "--apply")
        passed.append("same-cause failures keep the running model fixed and require a higher-tier replacement instance")

        timeout_task = write_task(project, "timeout", {
            "domain_key": "timeout",
            "title": "timeout probe",
            "task_type": "docs",
            "risk": "low",
            "timeout_seconds": 60,
        })
        run("python3", ORCH, "enqueue", "--project", project, "--task-json", timeout_task, "--task-id", "timeout", "--apply")
        run("python3", ORCH, "dispatch", "--project", project, "--task-id", "timeout", "--instance-id", "timeout-agent", "--apply")
        timeout_registry = json.loads(registry.read_text(encoding="utf-8"))
        timeout_record = next(item for item in timeout_registry["threads"] if item["id"] == "timeout")
        timeout_record["started_at"] = "2000-01-01T00:00:00+00:00"
        registry.write_text(json.dumps(timeout_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", ORCH, "reconcile", "--project", project, "--apply")
        timed_out = run("python3", ORCH, "health", "--project", project, expected=(1,)).stdout
        require("execution timeout exceeded: timeout" in timed_out, "execution timeout was not detected")
        timeout_registry = json.loads(registry.read_text(encoding="utf-8"))
        timeout_record = next(item for item in timeout_registry["threads"] if item["id"] == "timeout")
        timeout_record["started_at"] = timeout_record["last_heartbeat"]
        registry.write_text(json.dumps(timeout_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", ORCH, "reconcile", "--project", project, "--apply")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "timeout", "--status", "completed", "--evidence", "artifacts/timeout.log", "--apply")
        passed.append("health detects execution timeout and accepts evidence-backed recovery")

        reuse_plan = plan(project, high)
        require(
            reuse_plan["decision"] == "reuse_project_thread" and reuse_plan["existing_thread_id"] == "thread-1",
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
        require(plan(project, conflicting)["decision"] == "queue_project_ownership", "ownership conflict not queued")
        stale = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-1", "--stage", "stale", "--expected-revision", "0", "--apply", expected=(2,))
        require("STATE=thread_orchestration_failed" in stale.stdout, "stale revision was accepted")
        passed.append("ownership collisions and stale writers fail closed")

        run("python3", ORCH, "register", "--project", project, "--domain-key", "catalog", "--thread-id", "thread-w2", "--title", "catalog work", "--model", str(medium_plan["model"]), "--owned-path", "src/catalog", "--apply")
        third_writer = write_task(project, "third-writer", {"domain_key": "search", "title": "search work", "expected_days": 2, "task_packages": 4, "independent_boundary": True, "recurring": True, "owned_paths": ["src/search"]})
        require(plan(project, third_writer)["decision"] == "queue_project_writer", "writer capacity was not planned")
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
        resume = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-old", "--status", "active", "--handoff", "artifacts/handoff.md", "--apply", expected=(2,))
        require("cannot resume" in resume.stderr, "blocked thread resumed into an ownership collision")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-new", "--status", "completed", "--evidence", "artifacts/support.log", "--apply")
        resumed = run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-old", "--status", "active", "--handoff", "artifacts/handoff.md", "--apply").stdout
        require("STATE=thread_updated" in resumed, "eligible blocked task did not resume through handoff")
        run("python3", ORCH, "update", "--project", project, "--thread-id", "thread-old", "--status", "completed", "--evidence", "artifacts/support-old.log", "--apply")
        passed.append("blocked recovery rechecks dispatch, handoff, dependencies, domain, ownership and capacity")

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
