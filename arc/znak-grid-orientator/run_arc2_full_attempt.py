"""Run one resumable, sequential ARC-AGI-2 evaluation attempt.

This file is generated from the audited ARC-AGI-1 runner, with ARC-AGI-2
identity, cardinality, and repository locks.  Every attempt uses the no-tool
solver mode selected for the clean ARC run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_REPO_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
EXPECTED_ARC1_COMMIT = "399030444e0ab0cc8b4e199870fb20b863846f34"
EXPECTED_TASKS = 120
CONFIG = "gpt-5-1-codex-mini-codexcli"
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
NO_TOOL_INSTRUCTIONS = """Solve the ARC grid task directly. Do not call tools, run commands, or create files.
Reason internally, then return only the final rectangular JSON grid and no commentary.

"""
ATTEMPT_SETTINGS = {
    1: {"task_timeout_seconds": 480, "shell_tool_enabled": False, "scratchpad_instructions": NO_TOOL_INSTRUCTIONS},
    2: {"task_timeout_seconds": 480, "shell_tool_enabled": False, "scratchpad_instructions": NO_TOOL_INSTRUCTIONS},
    3: {"task_timeout_seconds": 600, "shell_tool_enabled": False, "scratchpad_instructions": NO_TOOL_INSTRUCTIONS},
}


def load_orientation_engine(path: Path):
    spec = importlib.util.spec_from_file_location("arc_orientation_engine_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ARC orientation engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_mechanism_bank(
    path: Path,
    expected_sha256: str,
    prior_progress_path: Path,
    prior_progress_sha256: str,
    manifest_path: Path,
    task_ids: list[str],
    prior_solved: set[str],
    attempt: int,
) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError("mechanism bank is missing")
    if sha256(path).lower() != expected_sha256.lower():
        raise RuntimeError("mechanism bank hash mismatch")
    bank = json.loads(path.read_bytes())
    expected = {
        "schema": "ARC-COMPOSITIONAL-ORIENTATOR/1",
        "benchmark": "ARC-AGI-2",
        "route": "LOCAL_RESEARCH_ADAPTIVE",
        "split": "evaluation",
        "source_attempt": attempt - 1,
        "next_attempt": attempt,
        "adaptive_cross_task_memory": True,
        "blind_evaluation": False,
        "data_scope": "training_inputs_outputs_and_test_inputs_only_plus_prior_solved_status",
        "prior_progress_sha256": prior_progress_sha256,
        "manifest_sha256": sha256(manifest_path),
    }
    for field, expected_value in expected.items():
        if bank.get(field) != expected_value:
            raise RuntimeError(f"mechanism bank mismatch in {field}")
    if Path(str(bank.get("prior_progress", ""))).resolve() != prior_progress_path.resolve():
        raise RuntimeError("mechanism bank prior progress path mismatch")
    if Path(str(bank.get("manifest", ""))).resolve() != manifest_path.resolve():
        raise RuntimeError("mechanism bank manifest path mismatch")
    profiles = bank.get("task_profiles")
    solved_mechanisms = bank.get("solved_mechanisms")
    if not isinstance(profiles, list) or not isinstance(solved_mechanisms, list):
        raise RuntimeError("mechanism bank collections are malformed")
    profile_ids = [item.get("task_id") if isinstance(item, dict) else None for item in profiles]
    solved_ids = [
        item.get("task_id") if isinstance(item, dict) else None for item in solved_mechanisms
    ]
    if len(profile_ids) != len(set(profile_ids)) or set(profile_ids) != set(task_ids):
        raise RuntimeError("mechanism bank task profile coverage mismatch")
    if len(solved_ids) != len(set(solved_ids)) or set(solved_ids) != prior_solved:
        raise RuntimeError("mechanism bank solved mechanism set mismatch")
    if bank.get("solved_mechanism_count") != len(prior_solved):
        raise RuntimeError("mechanism bank solved mechanism count mismatch")
    return bank


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json_atomic(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        digest, filename = line.split(maxsplit=1)
        entries[filename.lstrip("*./")] = digest.lower()
    return entries


def verify_inputs(data_dir: Path, manifest_path: Path) -> list[str]:
    expected = parse_manifest(manifest_path)
    actual_names = sorted(path.name for path in data_dir.glob("*.json"))
    if len(expected) != EXPECTED_TASKS or len(actual_names) != EXPECTED_TASKS:
        raise RuntimeError(
            f"ARC2 evaluation cardinality mismatch: manifest={len(expected)} files={len(actual_names)}"
        )
    if set(expected) != set(actual_names):
        raise RuntimeError("ARC2 evaluation task IDs differ from the frozen manifest")
    mismatches = [name for name in actual_names if sha256(data_dir / name) != expected[name]]
    if mismatches:
        raise RuntimeError(f"ARC2 evaluation hash mismatch: {mismatches[:5]}")
    return [Path(name).stem for name in actual_names]


def summarize_submission(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"status": "MISSING", "pairs": 0, "correct_pairs": 0, "task_solved": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        return {"status": "INVALID", "pairs": 0, "correct_pairs": 0, "task_solved": False}
    attempts = [pair.get("attempt_1") if isinstance(pair, dict) else None for pair in payload]
    if any(attempt is None for attempt in attempts):
        return {
            "status": "NO_PREDICTION",
            "pairs": len(attempts),
            "correct_pairs": sum(bool(a and a.get("correct")) for a in attempts),
            "task_solved": False,
        }
    correct_pairs = sum(bool(attempt.get("correct")) for attempt in attempts)
    return {
        "status": "SOLVED" if correct_pairs == len(attempts) else "WRONG",
        "pairs": len(attempts),
        "correct_pairs": correct_pairs,
        "task_solved": correct_pairs == len(attempts),
    }


def summarize_generation(path: Path, unexpected_error: str | None) -> dict[str, object]:
    """Never credit a prediction from a generation call that raised an error."""
    if unexpected_error is not None:
        return {
            "status": "RUNNER_ERROR",
            "pairs": 0,
            "correct_pairs": 0,
            "task_solved": False,
            "error": unexpected_error,
        }
    return summarize_submission(path)


def verify_fresh_result_state(
    progress_path: Path,
    final_path: Path,
    events_path: Path,
    predictions_dir: Path,
    scratchpad_dir: Path,
) -> None:
    if progress_path.exists() or final_path.exists() or events_path.exists():
        raise RuntimeError("target run directory already contains result state")
    for directory in (predictions_dir, scratchpad_dir):
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f"target run directory contains stale files in {directory.name}")


def validate_arc1_prerequisite(
    path: Path,
    expected_sha256: str,
    expected_manifest_path: Path,
) -> None:
    if not path.is_file():
        raise RuntimeError("ARC1 prerequisite audit is missing")
    payload = path.read_bytes()
    if sha256_bytes(payload).lower() != expected_sha256.lower():
        raise RuntimeError("ARC1 prerequisite audit hash mismatch")
    audit = json.loads(payload)
    solved_tasks = audit.get("independently_solved_tasks")
    if not isinstance(solved_tasks, int) or isinstance(solved_tasks, bool) or not 0 <= solved_tasks <= 400:
        raise RuntimeError("ARC1 prerequisite solved task count mismatch")
    expected_verdict = "VERIFIED" if solved_tasks == 400 else "PARTIAL"
    expected = {
        "verdict": expected_verdict,
        "benchmark": "ARC-AGI-1",
        "version": EXPECTED_ARC1_COMMIT,
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "claim": "local_reference_match",
        "dataset_tasks": 400,
        "attempt_limit": 3,
    }
    for field, expected_value in expected.items():
        if audit.get(field) != expected_value:
            raise RuntimeError(f"ARC1 prerequisite mismatch in {field}")
    attempts = audit.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 3:
        raise RuntimeError("ARC1 prerequisite attempt count mismatch")
    attempt_numbers = [item.get("attempt") if isinstance(item, dict) else None for item in attempts]
    if attempt_numbers != list(range(1, len(attempts) + 1)):
        raise RuntimeError("ARC1 prerequisite attempts are not sequential")
    manifest_value = audit.get("manifest")
    if not isinstance(manifest_value, str) or Path(manifest_value).resolve() != expected_manifest_path.resolve():
        raise RuntimeError("ARC1 prerequisite manifest path mismatch")
    manifest_hash = audit.get("manifest_sha256")
    if not isinstance(manifest_hash, str) or manifest_hash.lower() != sha256(expected_manifest_path).lower():
        raise RuntimeError("ARC1 prerequisite manifest hash mismatch")
    errors = audit.get("errors")
    unsolved = audit.get("unsolved_task_ids")
    unprocessed = audit.get("unprocessed_task_ids")
    if not isinstance(errors, list) or errors:
        raise RuntimeError("ARC1 prerequisite errors is not empty")
    if not isinstance(unsolved, list) or len(unsolved) != 400 - solved_tasks:
        raise RuntimeError("ARC1 prerequisite unsolved task count mismatch")
    if not isinstance(unprocessed, list) or unprocessed:
        raise RuntimeError("ARC1 prerequisite unprocessed_task_ids is not empty")


def validate_arc1_receipt(
    receipt_path: Path,
    expected_receipt_sha256: str,
    audit_path: Path,
    expected_audit_sha256: str,
    auditor_path: Path,
    expected_auditor_sha256: str,
    finalizer_path: Path,
    expected_finalizer_sha256: str,
) -> None:
    if not receipt_path.is_file():
        raise RuntimeError("ARC1 prerequisite receipt is missing")
    payload = receipt_path.read_bytes()
    if sha256_bytes(payload).lower() != expected_receipt_sha256.lower():
        raise RuntimeError("ARC1 prerequisite receipt hash mismatch")
    receipt = json.loads(payload)
    audit = json.loads(audit_path.read_bytes())
    solved_tasks = audit.get("independently_solved_tasks")
    expected_status = audit.get("verdict")
    if expected_status not in ("VERIFIED", "PARTIAL") or not isinstance(solved_tasks, int):
        raise RuntimeError("ARC1 prerequisite audit status is invalid")
    expected = {
        "status": expected_status,
        "benchmark": "ARC-AGI-1",
        "claim": "local_reference_match",
        "solved_tasks": solved_tasks,
        "dataset_tasks": 400,
        "audit_sha256": expected_audit_sha256,
        "auditor_sha256": expected_auditor_sha256,
        "finalizer_sha256": expected_finalizer_sha256,
    }
    for field, expected_value in expected.items():
        actual = receipt.get(field)
        if field.endswith("sha256"):
            matches = isinstance(actual, str) and actual.lower() == expected_value.lower()
        else:
            matches = actual == expected_value
        if not matches:
            raise RuntimeError(f"ARC1 prerequisite receipt mismatch in {field}")
    audit_attempts = audit.get("attempts")
    receipt_attempts = receipt.get("attempts")
    if (
        not isinstance(audit_attempts, list)
        or not isinstance(receipt_attempts, int)
        or isinstance(receipt_attempts, bool)
        or receipt_attempts != len(audit_attempts)
        or not 1 <= receipt_attempts <= 3
    ):
        raise RuntimeError("ARC1 prerequisite receipt attempt count mismatch")
    audit_path_value = receipt.get("audit_path")
    if not isinstance(audit_path_value, str) or Path(audit_path_value).resolve() != audit_path.resolve():
        raise RuntimeError("ARC1 prerequisite receipt audit path mismatch")
    if sha256(audit_path).lower() != expected_audit_sha256.lower():
        raise RuntimeError("ARC1 prerequisite audit changed after receipt validation")
    if sha256(auditor_path).lower() != expected_auditor_sha256.lower():
        raise RuntimeError("ARC1 auditor changed after receipt validation")
    if sha256(finalizer_path).lower() != expected_finalizer_sha256.lower():
        raise RuntimeError("ARC1 finalizer changed after receipt validation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--codex-cli", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--prior-progress", type=Path)
    parser.add_argument("--expected-prior-progress-sha256")
    parser.add_argument("--run-lock", type=Path)
    parser.add_argument("--start-gate", type=Path)
    parser.add_argument("--start-ready", type=Path)
    parser.add_argument("--mechanism-bank", type=Path)
    parser.add_argument("--expected-mechanism-bank-sha256")
    args = parser.parse_args()
    settings = ATTEMPT_SETTINGS[args.attempt]

    if not args.run_lock or not args.start_gate or not args.start_ready:
        raise SystemExit("REFUSED: ARC2 requires run lock, start gate, and start ready paths")
    if args.attempt == 1 and (args.prior_progress or args.expected_prior_progress_sha256):
        raise SystemExit("REFUSED: attempt 1 cannot carry prior progress")
    if args.attempt > 1 and (
        not args.prior_progress or not args.expected_prior_progress_sha256
    ):
        raise SystemExit("REFUSED: retry requires prior progress and its approved hash")
    if args.attempt > 1 and (
        not args.mechanism_bank or not args.expected_mechanism_bank_sha256
    ):
        raise SystemExit("REFUSED: retry requires a bound mechanism bank")
    if args.attempt == 1 and (
        args.mechanism_bank or args.expected_mechanism_bank_sha256
    ):
        raise SystemExit("REFUSED: attempt 1 cannot use adaptive mechanism memory")

    root = args.root.resolve()
    run_dir = args.run_dir.resolve()
    harness_repo = (root / "sources" / "ARC-AGI-Benchmarking").resolve()
    arc2_repo = (root / "sources" / "ARC-AGI-2").resolve()
    data_dir = (arc2_repo / "data" / "evaluation").resolve()
    manifest_path = (root / "manifests" / "ARC-AGI-2-evaluation.sha256").resolve()
    adapter_path = (
        harness_repo / "src" / "arc_agi_benchmarking" / "adapters" / "codexcli.py"
    ).resolve()
    orientation_engine_path = (root / "tools" / "arc_orientation_engine.py").resolve()
    predictions_dir = run_dir / "predictions"
    scratchpad_dir = run_dir / "scratchpad"
    progress_path = run_dir / "PROGRESS.json"
    events_path = run_dir / "EVENTS.jsonl"
    final_path = run_dir / "FINAL.json"

    try:
        verify_fresh_result_state(
            progress_path, final_path, events_path, predictions_dir, scratchpad_dir
        )
    except RuntimeError as exc:
        raise SystemExit(f"REFUSED: {exc}") from exc

    for required in (
        harness_repo,
        arc2_repo,
        data_dir,
        manifest_path,
        adapter_path,
        orientation_engine_path,
        args.codex_cli,
    ):
        if not required.exists():
            raise SystemExit(f"REFUSED: missing required path {required}")

    import subprocess

    repo_commit = subprocess.check_output(
        ["git", "-C", str(arc2_repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if repo_commit != EXPECTED_REPO_COMMIT:
        raise SystemExit(f"REFUSED: ARC2 commit drift: {repo_commit}")

    task_ids = verify_inputs(data_dir, manifest_path)

    run_lock_path = args.run_lock.resolve()
    if not run_lock_path.is_file():
        raise SystemExit(f"REFUSED: run lock missing: {run_lock_path}")
    lock_payload = run_lock_path.read_bytes()
    run_lock_sha256 = sha256_bytes(lock_payload)
    run_lock = json.loads(lock_payload)
    expected_lock = {
            "benchmark": "ARC-AGI-2",
            "route": "LOCAL_RESEARCH",
            "split": "evaluation",
            "run_attempt": args.attempt,
            "attempt_limit": 3,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "task_timeout_seconds": settings["task_timeout_seconds"],
            "shell_tool_enabled": settings["shell_tool_enabled"],
            "arc2_repo_commit": repo_commit,
            "dataset_manifest_sha256": sha256(manifest_path).upper(),
            "runner_sha256": sha256(Path(__file__).resolve()).upper(),
            "adapter_sha256": sha256(adapter_path).upper(),
    }
    if args.attempt > 1:
        mechanism_bank_path = args.mechanism_bank.resolve()
        if not mechanism_bank_path.is_file():
            raise SystemExit("REFUSED: mechanism bank is missing")
        mechanism_bank_sha256 = sha256(mechanism_bank_path)
        if mechanism_bank_sha256.lower() != args.expected_mechanism_bank_sha256.lower():
            raise SystemExit("REFUSED: approved mechanism bank hash mismatch")
        expected_lock.update(
            {
                "orientation_engine_sha256": sha256(orientation_engine_path).upper(),
                "mechanism_bank_sha256": mechanism_bank_sha256.upper(),
                "adaptive_cross_task_memory": True,
                "blind_evaluation": False,
            }
        )
        if Path(str(run_lock.get("mechanism_bank", ""))).resolve() != mechanism_bank_path:
            raise SystemExit("REFUSED: run lock mechanism bank path mismatch")
    for field, expected_value in expected_lock.items():
        actual_value = run_lock.get(field)
        if isinstance(expected_value, str) and field.endswith("sha256"):
            matches = str(actual_value).upper() == expected_value
        else:
            matches = actual_value == expected_value
        if not matches:
            raise SystemExit(f"REFUSED: run lock mismatch in {field}")
    if Path(str(run_lock.get("run_dir", ""))).resolve() != run_dir:
        raise SystemExit("REFUSED: run lock target directory mismatch")
    prerequisite_path_value = run_lock.get("arc1_prerequisite_audit")
    prerequisite_hash = run_lock.get("arc1_prerequisite_audit_sha256")
    if not isinstance(prerequisite_path_value, str) or not isinstance(prerequisite_hash, str):
        raise SystemExit("REFUSED: ARC1 prerequisite binding missing from run lock")
    receipt_path_value = run_lock.get("arc1_prerequisite_receipt")
    receipt_hash = run_lock.get("arc1_prerequisite_receipt_sha256")
    auditor_hash = run_lock.get("arc1_auditor_sha256")
    finalizer_hash = run_lock.get("arc1_finalizer_sha256")
    if any(
        not isinstance(value, str)
        for value in (receipt_path_value, receipt_hash, auditor_hash, finalizer_hash)
    ):
        raise SystemExit("REFUSED: ARC1 prerequisite receipt binding missing from run lock")
    canonical_audit_path = (root / "runtime" / "ARC1_FINAL_AUDIT.json").resolve()
    canonical_receipt_path = (root / "runtime" / "ARC1_FINAL_AUDIT_RECEIPT.json").resolve()
    auditor_path = (root / "tools" / "audit_arc_grid_runs.py").resolve()
    finalizer_path = (root / "tools" / "finalize_arc1_audit.ps1").resolve()
    if Path(prerequisite_path_value).resolve() != canonical_audit_path:
        raise SystemExit("REFUSED: ARC1 prerequisite audit path is not canonical")
    if Path(receipt_path_value).resolve() != canonical_receipt_path:
        raise SystemExit("REFUSED: ARC1 prerequisite receipt path is not canonical")
    if sha256(auditor_path).lower() != auditor_hash.lower():
        raise SystemExit("REFUSED: ARC1 auditor hash changed before finalization")
    if sha256(finalizer_path).lower() != finalizer_hash.lower():
        raise SystemExit("REFUSED: ARC1 finalizer hash changed before finalization")
    finalizer_result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(finalizer_path),
        ],
        text=True,
        capture_output=True,
    )
    if finalizer_result.returncode != 0:
        detail = (finalizer_result.stderr or finalizer_result.stdout).strip()
        raise SystemExit(f"REFUSED: fresh ARC1 finalization failed: {detail}")
    try:
        validate_arc1_prerequisite(
            canonical_audit_path,
            prerequisite_hash,
            root / "manifests" / "ARC-AGI-1-evaluation.sha256",
        )
        validate_arc1_receipt(
            canonical_receipt_path,
            receipt_hash,
            canonical_audit_path,
            prerequisite_hash,
            auditor_path,
            auditor_hash,
            finalizer_path,
            finalizer_hash,
        )
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"REFUSED: {exc}") from exc
    locked_start_gate = run_lock.get("start_gate")
    if not isinstance(locked_start_gate, str) or (
        Path(locked_start_gate).resolve() != args.start_gate.resolve()
    ):
        raise SystemExit("REFUSED: run lock start gate mismatch")
    locked_start_ready = run_lock.get("start_ready")
    if not isinstance(locked_start_ready, str) or (
        Path(locked_start_ready).resolve() != args.start_ready.resolve()
    ):
        raise SystemExit("REFUSED: run lock start ready path mismatch")

    start_gate_path = args.start_gate.resolve()
    start_ready_path = args.start_ready.resolve()
    write_json_atomic(
        start_ready_path,
        {
            "status": "READY",
            "worker_pid": os.getpid(),
            "run_lock_sha256": run_lock_sha256,
            "ready_at": utc_now(),
        },
    )
    deadline = time.monotonic() + 120
    while not start_gate_path.is_file():
        if time.monotonic() >= deadline:
            raise SystemExit("REFUSED: start gate was not released within 120 seconds")
        time.sleep(0.2)
    gate_payload = start_gate_path.read_bytes()
    start_gate_sha256 = sha256_bytes(gate_payload)
    gate = json.loads(gate_payload)
    if gate.get("status") != "RELEASED":
        raise SystemExit("REFUSED: invalid start gate status")
    if gate.get("runner_pid") != os.getpid():
        raise SystemExit("REFUSED: start gate runner PID mismatch")
    if not isinstance(gate.get("watchdog_pid"), int) or gate["watchdog_pid"] <= 0:
        raise SystemExit("REFUSED: start gate watchdog PID missing")
    if str(gate.get("run_lock_sha256", "")).lower() != run_lock_sha256.lower():
        raise SystemExit("REFUSED: start gate run lock hash mismatch")
    if sha256(auditor_path).lower() != auditor_hash.lower():
        raise SystemExit("REFUSED: ARC1 auditor changed after start gate")
    if sha256(finalizer_path).lower() != finalizer_hash.lower():
        raise SystemExit("REFUSED: ARC1 finalizer changed after start gate")
    finalizer_result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(finalizer_path),
        ],
        text=True,
        capture_output=True,
    )
    if finalizer_result.returncode != 0:
        detail = (finalizer_result.stderr or finalizer_result.stdout).strip()
        raise SystemExit(f"REFUSED: post-gate ARC1 finalization failed: {detail}")
    try:
        validate_arc1_prerequisite(
            canonical_audit_path,
            prerequisite_hash,
            root / "manifests" / "ARC-AGI-1-evaluation.sha256",
        )
        validate_arc1_receipt(
            canonical_receipt_path,
            receipt_hash,
            canonical_audit_path,
            prerequisite_hash,
            auditor_path,
            auditor_hash,
            finalizer_path,
            finalizer_hash,
        )
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"REFUSED: post-gate ARC1 evidence invalid: {exc}") from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir.mkdir(parents=True, exist_ok=True)
    scratchpad_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(harness_repo))
    from main import ARCTester

    solver = ARCTester(
        config=CONFIG,
        save_submission_dir=str(predictions_dir),
        overwrite_submission=True,
        print_submission=False,
        num_attempts=1,
        retry_attempts=1,
    )
    solver.provider.model_config.kwargs["scratchpad_root"] = str(scratchpad_dir)
    solver.provider.model_config.kwargs["codex_cli_path"] = str(args.codex_cli.resolve())
    solver.provider.model_config.kwargs["auth_mode"] = "stored_login"
    solver.provider.model_config.kwargs["codex_exec_timeout_seconds"] = settings["task_timeout_seconds"]
    solver.provider.model_config.kwargs["model_reasoning_effort"] = REASONING_EFFORT
    solver.provider.model_config.kwargs["shell_tool_enabled"] = settings["shell_tool_enabled"]
    if settings["scratchpad_instructions"] is not None:
        solver.provider.model_config.kwargs["scratchpad_instructions"] = settings["scratchpad_instructions"]
    solver.model_config.model_name = MODEL
    solver.provider.model_config.model_name = MODEL

    prior_solved: set[str] = set()
    prior_progress_sha256 = None
    prior_path = None
    if args.prior_progress:
        prior_path = args.prior_progress.resolve()
        if not prior_path.is_file():
            raise SystemExit(f"REFUSED: prior progress missing: {prior_path}")
        prior_payload = prior_path.read_bytes()
        prior_progress_sha256 = sha256_bytes(prior_payload)
        if (
            args.expected_prior_progress_sha256
            and prior_progress_sha256.lower() != args.expected_prior_progress_sha256.lower()
        ):
            raise SystemExit("REFUSED: prior progress hash changed after approval")
        if Path(str(run_lock.get("prior_progress", ""))).resolve() != prior_path:
            raise SystemExit("REFUSED: run lock prior progress path mismatch")
        if str(run_lock.get("prior_progress_sha256", "")).lower() != prior_progress_sha256.lower():
            raise SystemExit("REFUSED: run lock prior progress hash mismatch")
        prior = json.loads(prior_payload)
        expected_prior = {
            "benchmark": "ARC-AGI-2",
            "route": "LOCAL_RESEARCH",
            "split": "evaluation",
            "run_attempt": args.attempt - 1,
            "attempt_limit": 3,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "shell_tool_enabled": False,
            "repo_commit": repo_commit,
            "manifest_sha256": sha256(manifest_path),
            "total_tasks": EXPECTED_TASKS,
        }
        for field, expected_value in expected_prior.items():
            if prior.get(field) != expected_value:
                raise SystemExit(f"REFUSED: prior progress mismatch in {field}")
        carried = prior.get("carried_solved_task_ids")
        processed = prior.get("processed")
        if not isinstance(carried, list) or not isinstance(processed, dict):
            raise SystemExit("REFUSED: malformed prior progress collections")
        if any(not isinstance(task_id, str) for task_id in carried):
            raise SystemExit("REFUSED: malformed carried task ID")
        if len(carried) != len(set(carried)) or set(carried) - set(task_ids):
            raise SystemExit("REFUSED: duplicate or foreign carried task ID")
        if set(processed) - set(task_ids) or set(carried) & set(processed):
            raise SystemExit("REFUSED: prior task partition mismatch")
        if len(carried) + len(processed) != EXPECTED_TASKS:
            raise SystemExit("REFUSED: prior attempt is not complete")
        for task_id, record in processed.items():
            if not isinstance(record, dict) or record.get("task_id") != task_id:
                raise SystemExit("REFUSED: malformed prior processed record")
            solved = record.get("task_solved")
            status = record.get("status")
            if not isinstance(solved, bool):
                raise SystemExit("REFUSED: prior task_solved is not boolean")
            if (solved and status != "SOLVED") or (not solved and status == "SOLVED"):
                raise SystemExit("REFUSED: prior solved/status mismatch")
        prior_final_path = prior_path.with_name("FINAL.json")
        if not prior_final_path.is_file():
            raise SystemExit("REFUSED: prior FINAL.json missing")
        prior_final = json.loads(prior_final_path.read_bytes())
        expected_final = {
            "status": "COMPLETE",
            "benchmark": "ARC-AGI-2",
            "route": "LOCAL_RESEARCH",
            "split": "evaluation",
            "run_attempt": args.attempt - 1,
            "attempt_limit": 3,
            "model": MODEL,
            "completed_tasks": EXPECTED_TASKS,
            "total_tasks": EXPECTED_TASKS,
            "progress_sha256": prior_progress_sha256,
        }
        for field, expected_value in expected_final.items():
            if prior_final.get(field) != expected_value:
                raise SystemExit(f"REFUSED: prior final mismatch in {field}")
        prior_solved.update(carried)
        prior_solved.update(
            task_id
            for task_id, record in processed.items()
            if record.get("task_solved") is True
        )

    mechanism_bank = None
    mechanism_bank_sha256 = None
    orientation_engine_sha256 = None
    orientation_engine = None
    if args.attempt > 1:
        try:
            mechanism_bank = validate_mechanism_bank(
                args.mechanism_bank.resolve(),
                args.expected_mechanism_bank_sha256,
                prior_path,
                prior_progress_sha256,
                manifest_path,
                task_ids,
                prior_solved,
                args.attempt,
            )
            orientation_engine = load_orientation_engine(orientation_engine_path)
        except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc
        mechanism_bank_sha256 = sha256(args.mechanism_bank.resolve())
        orientation_engine_sha256 = sha256(orientation_engine_path)

    progress = {
        "benchmark": "ARC-AGI-2",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": args.attempt,
        "attempt_limit": 3,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "auth_mode": "stored_login",
        "task_timeout_seconds": settings["task_timeout_seconds"],
        "shell_tool_enabled": settings["shell_tool_enabled"],
        "carried_solved_task_ids": sorted(prior_solved),
        "prior_progress_sha256": prior_progress_sha256,
        "adaptive_cross_task_memory": args.attempt > 1,
        "blind_evaluation": args.attempt == 1,
        "mechanism_bank_sha256": mechanism_bank_sha256,
        "orientation_engine_sha256": orientation_engine_sha256,
        "run_lock_sha256": run_lock_sha256,
        "start_gate_sha256": start_gate_sha256,
        "runner_worker_pid": os.getpid(),
        "repo_commit": repo_commit,
        "manifest_sha256": sha256(manifest_path),
        "total_tasks": len(task_ids),
        "started_utc": utc_now(),
        "processed": {},
    }
    write_json_atomic(progress_path, progress)

    with events_path.open("a", encoding="utf-8", buffering=1) as events:
        for index, task_id in enumerate(task_ids, start=1):
            if task_id in prior_solved:
                continue
            if task_id in progress["processed"]:
                continue
            started = utc_now()
            before = time.monotonic()
            unexpected_error = None
            orientation_card_sha256 = None
            if orientation_engine is not None:
                task_payload = json.loads((data_dir / f"{task_id}.json").read_bytes())
                card = orientation_engine.orientation_card(task_id, task_payload, mechanism_bank)
                if "{" in card or "}" in card:
                    raise SystemExit("REFUSED: orientation card contains unsafe format braces")
                solver.provider.model_config.kwargs["scratchpad_instructions"] = (
                    NO_TOOL_INSTRUCTIONS + card + "\n"
                )
                orientation_card_sha256 = hashlib.sha256(card.encode("utf-8")).hexdigest()
            try:
                solver.generate_task_solution(data_dir=str(data_dir), task_id=task_id)
            except BaseException as exc:
                unexpected_error = f"{type(exc).__name__}: {exc}"
            submission_path = predictions_dir / f"{task_id}.json"
            summary = summarize_generation(submission_path, unexpected_error)
            record = {
                "index": index,
                "task_id": task_id,
                "started_utc": started,
                "ended_utc": utc_now(),
                "duration_seconds": round(time.monotonic() - before, 3),
                "orientation_card_sha256": orientation_card_sha256,
                **summary,
                "submission_sha256": sha256(submission_path) if submission_path.is_file() else None,
            }
            progress["processed"][task_id] = record
            progress["updated_utc"] = record["ended_utc"]
            write_json_atomic(progress_path, progress)
            events.write(json.dumps(record, ensure_ascii=False) + "\n")
            completed = len(prior_solved) + len(progress["processed"])
            solved = len(prior_solved) + sum(
                bool(item["task_solved"]) for item in progress["processed"].values()
            )
            print(
                f"ARC2_PROGRESS completed={completed}/{EXPECTED_TASKS} solved={solved} "
                f"task={task_id} status={record['status']} duration={record['duration_seconds']}",
                flush=True,
            )

    records = list(progress["processed"].values())
    solved_tasks = len(prior_solved) + sum(bool(record["task_solved"]) for record in records)
    total_pairs = sum(int(record["pairs"]) for record in records)
    correct_pairs = sum(int(record["correct_pairs"]) for record in records)
    final = {
        "status": "COMPLETE",
        "benchmark": "ARC-AGI-2",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": args.attempt,
        "attempt_limit": 3,
        "model": MODEL,
        "completed_tasks": len(prior_solved) + len(records),
        "carried_solved_tasks": len(prior_solved),
        "total_tasks": EXPECTED_TASKS,
        "solved_tasks": solved_tasks,
        "task_accuracy": solved_tasks / EXPECTED_TASKS,
        "correct_pairs": correct_pairs,
        "total_pairs": total_pairs,
        "pair_accuracy": correct_pairs / total_pairs if total_pairs else None,
        "ended_utc": utc_now(),
        "progress_sha256": sha256(progress_path),
    }
    write_json_atomic(final_path, final)
    print("ARC2_FINAL " + json.dumps(final, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())