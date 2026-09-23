"""Run one resumable, sequential ARC-AGI-1 evaluation attempt.

The solver receives training pairs and test inputs through the benchmark harness.
Ground-truth test outputs are used by the harness only after prediction to set the
local ``correct`` field. Progress is checkpointed after every task.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_REPO_COMMIT = "399030444e0ab0cc8b4e199870fb20b863846f34"
CONFIG = "gpt-5-1-codex-mini-codexcli"
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
NO_TOOL_INSTRUCTIONS = """Solve the ARC grid task directly. Do not call tools, run commands, or create files.
Reason internally, then return only the final rectangular JSON grid and no commentary.

"""
ATTEMPT3_STRATEGY = "wide_view_v1"
ATTEMPT4_STRATEGY = "blysk_retry_v1"
ATTEMPT3_INSTRUCTIONS = """Solve the ARC grid task directly. Do not call tools, run commands, or create files.
Use a wide-angle analysis before committing to an answer: inspect the entire grid, objects, colors,
spatial relations, symmetries, counts, boundaries, and input/output dimensions. Form several competing
transformation hypotheses and test each one against every training pair. On a difficult task, spend more
reasoning time and revisit the whole pattern instead of narrowing early. Reject any hypothesis that fails
even one training detail. Then return only the final rectangular JSON grid and no commentary.

"""
ATTEMPT_SETTINGS = {
    1: {"task_timeout_seconds": 240, "shell_tool_enabled": True, "scratchpad_instructions": None},
    2: {"task_timeout_seconds": 480, "shell_tool_enabled": False, "scratchpad_instructions": NO_TOOL_INSTRUCTIONS},
    3: {"task_timeout_seconds": 600, "shell_tool_enabled": False, "scratchpad_instructions": ATTEMPT3_INSTRUCTIONS},
    4: {"task_timeout_seconds": 600, "shell_tool_enabled": False, "scratchpad_instructions": None},
}
HARNESS_SOURCE_SUFFIXES = {".json", ".py", ".txt", ".yaml", ".yml"}


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


def harness_tree_sha256(harness_repo: Path) -> str:
    candidates = [harness_repo / "main.py", harness_repo / "provider_config.yml"]
    candidates.extend((harness_repo / "src" / "arc_agi_benchmarking").rglob("*"))
    paths = sorted(
        (
            path
            for path in candidates
            if path.is_file() and path.suffix.lower() in HARNESS_SOURCE_SUFFIXES
        ),
        key=lambda path: path.relative_to(harness_repo).as_posix(),
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(harness_repo).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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
    if len(expected) != 400 or len(actual_names) != 400:
        raise RuntimeError(f"ARC1 evaluation cardinality mismatch: manifest={len(expected)} files={len(actual_names)}")
    if set(expected) != set(actual_names):
        raise RuntimeError("ARC1 evaluation task IDs differ from the frozen manifest")
    mismatches = [name for name in actual_names if sha256(data_dir / name) != expected[name]]
    if mismatches:
        raise RuntimeError(f"ARC1 evaluation hash mismatch: {mismatches[:5]}")
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


def quarantine_failed_submission(submission_path: Path, quarantine_dir: Path) -> str | None:
    """Preserve a partial/stale file outside the auditable predictions directory."""
    if not submission_path.is_file():
        return None
    digest = sha256(submission_path)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    destination = quarantine_dir / submission_path.name
    if destination.exists():
        raise RuntimeError(f"quarantine destination already exists: {destination.name}")
    os.replace(submission_path, destination)
    return digest


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


def process_command_line(process_id: int) -> str:
    """Read one Windows process command line without trusting the gate payload."""
    query = (
        f"(Get-CimInstance Win32_Process -Filter 'ProcessId={process_id}' "
        "-ErrorAction SilentlyContinue).CommandLine"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", query],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def process_identity(process_id: int) -> dict[str, object] | None:
    query = (
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={process_id}' "
        "-ErrorAction SilentlyContinue; if($p){[ordered]@{"
        "ProcessId=[int]$p.ProcessId;ParentProcessId=[int]$p.ParentProcessId;"
        "ExecutablePath=[string]$p.ExecutablePath;CommandLine=[string]$p.CommandLine;"
        "CreationDate=([datetimeoffset]$p.CreationDate).ToString('o')}"
        "|ConvertTo-Json -Compress}"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", query],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, dict) else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def process_is_descendant(child_pid: int, ancestor_pid: int) -> bool:
    current = child_pid
    for _ in range(16):
        if current == ancestor_pid:
            return True
        identity = process_identity(current)
        if identity is None or type(identity.get("ParentProcessId")) is not int:
            return False
        current = int(identity["ParentProcessId"])
        if current <= 0:
            return False
    return False


def command_has_argument(command: str, option: str, expected: str) -> bool:
    """Match a complete PowerShell-style option value, not a PID/path substring."""
    pattern = rf"(?i)(?:^|\s){re.escape(option)}\s+(?:\"{re.escape(expected)}\"|{re.escape(expected)})(?=\s|$)"
    return re.search(pattern, command) is not None


def windows_command_arguments(command: str) -> list[str]:
    if not command:
        return []
    argc = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = shell32.CommandLineToArgvW(command, ctypes.byref(argc))
    if not argv:
        return []
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def exact_option_value(arguments: list[str], option: str, expected: str) -> bool:
    matches = [index for index, item in enumerate(arguments) if item.lower() == option.lower()]
    return len(matches) == 1 and matches[0] + 1 < len(arguments) and arguments[matches[0] + 1] == expected


def build_blysk_instructions(task_id: str, task: dict[str, object]) -> str:
    engine_path = Path(__file__).with_name("arc_orientation_engine.py")
    spec = importlib.util.spec_from_file_location("arc_orientation_engine_runtime", engine_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ARC orientation engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    card = module.orientation_card(task_id, task, {"solved_mechanisms": []})
    return (
        "Solve the ARC grid task directly. Do not call tools, run commands, or create files.\n"
        "Use the BLYSK card as structural evidence, not as an answer. Prefer the smallest rule that "
        "explains every training pair. Reject any hypothesis that fails one visible training detail. "
        "Return only the final rectangular JSON grid and no commentary.\n\n"
        + card
    )


def validate_retry4_evidence(
    prior_path: Path,
    expected_sha256: str,
    task_ids: list[str],
    repo_commit: str,
    manifest_sha256: str,
) -> tuple[set[str], str]:
    prior_payload = prior_path.read_bytes()
    prior_sha256 = sha256_bytes(prior_payload)
    if prior_sha256.lower() != expected_sha256.lower():
        raise RuntimeError("attempt-3 progress hash changed")
    prior = json.loads(prior_payload)
    expected_prior = {
        "benchmark": "ARC-AGI-1",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": 3,
        "attempt_limit": 3,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "shell_tool_enabled": False,
        "repo_commit": repo_commit,
        "manifest_sha256": manifest_sha256.lower(),
        "total_tasks": 400,
    }
    for field, expected in expected_prior.items():
        actual = prior.get(field)
        matches = str(actual).lower() == str(expected).lower() if field.endswith("sha256") else actual == expected
        if not matches:
            raise RuntimeError(f"attempt-3 progress mismatch in {field}")
    carried = prior.get("carried_solved_task_ids")
    processed = prior.get("processed")
    if not isinstance(carried, list) or not isinstance(processed, dict):
        raise RuntimeError("attempt-3 task collections are malformed")
    carried_set = set(carried)
    processed_set = set(processed)
    task_set = set(task_ids)
    if len(carried) != len(carried_set) or carried_set & processed_set:
        raise RuntimeError("attempt-3 task partition overlaps or duplicates")
    if carried_set | processed_set != task_set:
        raise RuntimeError("attempt-3 task partition does not match frozen inputs")
    solved = set(carried_set)
    for task_id, record in processed.items():
        if not isinstance(record, dict) or record.get("task_id") != task_id:
            raise RuntimeError(f"attempt-3 record identity mismatch for {task_id}")
        task_solved = record.get("task_solved")
        if type(task_solved) is not bool:
            raise RuntimeError(f"attempt-3 task_solved invalid for {task_id}")
        if task_solved:
            solved.add(task_id)
    final_path = prior_path.parent / "FINAL.json"
    if not final_path.is_file():
        raise RuntimeError("attempt-3 FINAL.json is missing")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    expected_final = {
        "status": "COMPLETE",
        "benchmark": "ARC-AGI-1",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": 3,
        "attempt_limit": 3,
        "model": MODEL,
        "completed_tasks": 400,
        "total_tasks": 400,
        "solved_tasks": len(solved),
        "progress_sha256": prior_sha256,
    }
    for field, expected in expected_final.items():
        actual = final.get(field)
        matches = str(actual).lower() == str(expected).lower() if field.endswith("sha256") else actual == expected
        if not matches:
            raise RuntimeError(f"attempt-3 FINAL mismatch in {field}")
    return solved, prior_sha256


def validate_prior_evidence(
    prior_path: Path,
    expected_sha256: str,
    run_lock: dict[str, object],
    task_ids: list[str],
    repo_commit: str,
    manifest_sha256: str,
    pre_audit_path: Path,
) -> tuple[set[str], str]:
    """Validate the complete attempt-2 state and its independent audit."""
    prior_payload = prior_path.read_bytes()
    prior_sha256 = sha256_bytes(prior_payload)
    if prior_sha256.lower() != expected_sha256.lower():
        raise RuntimeError("prior progress hash changed after approval")
    prior = json.loads(prior_payload)
    expected_prior = {
        "benchmark": "ARC-AGI-1",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": 2,
        "attempt_limit": 3,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "shell_tool_enabled": False,
        "repo_commit": repo_commit,
        "manifest_sha256": manifest_sha256.lower(),
        "total_tasks": 400,
    }
    for field, expected in expected_prior.items():
        actual = prior.get(field)
        if field.endswith("sha256"):
            matches = str(actual).lower() == str(expected).lower()
        else:
            matches = actual == expected
        if not matches:
            raise RuntimeError(f"prior progress mismatch in {field}")

    carried = prior.get("carried_solved_task_ids")
    processed = prior.get("processed")
    if not isinstance(carried, list) or not all(isinstance(item, str) for item in carried):
        raise RuntimeError("prior carried task IDs are invalid")
    if len(carried) != len(set(carried)):
        raise RuntimeError("prior carried task IDs contain duplicates")
    if not isinstance(processed, dict):
        raise RuntimeError("prior processed records are invalid")
    processed_ids = set(processed)
    task_set = set(task_ids)
    carried_set = set(carried)
    if not all(isinstance(item, str) for item in processed):
        raise RuntimeError("prior processed task IDs are invalid")
    if carried_set & processed_ids:
        raise RuntimeError("prior carried and processed task IDs overlap")
    if carried_set | processed_ids != task_set:
        raise RuntimeError("prior task partition does not match the frozen 400 tasks")

    prior_solved = set(carried)
    for task_id, record in processed.items():
        if not isinstance(record, dict) or record.get("task_id") != task_id:
            raise RuntimeError(f"prior record identity mismatch for {task_id}")
        solved = record.get("task_solved")
        if type(solved) is not bool:
            raise RuntimeError(f"prior task_solved is not boolean for {task_id}")
        status = record.get("status")
        if (status == "SOLVED") != solved:
            raise RuntimeError(f"prior status/solution mismatch for {task_id}")
        if solved:
            prior_solved.add(task_id)

    final_path = prior_path.parent / "FINAL.json"
    if not final_path.is_file():
        raise RuntimeError("prior FINAL.json is missing")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    expected_final = {
        "status": "COMPLETE",
        "benchmark": "ARC-AGI-1",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": 2,
        "attempt_limit": 3,
        "model": MODEL,
        "completed_tasks": 400,
        "total_tasks": 400,
        "solved_tasks": len(prior_solved),
        "progress_sha256": prior_sha256,
    }
    for field, expected in expected_final.items():
        actual = final.get(field)
        if field.endswith("sha256"):
            matches = str(actual).lower() == str(expected).lower()
        else:
            matches = actual == expected
        if not matches:
            raise RuntimeError(f"prior FINAL mismatch in {field}")

    unsolved = sorted(task_set - prior_solved)
    if run_lock.get("carried_solved_tasks") != len(prior_solved):
        raise RuntimeError("run lock carried count does not match prior evidence")
    if run_lock.get("retry_task_count") != len(unsolved):
        raise RuntimeError("run lock retry count does not match prior evidence")
    locked_retry_ids = run_lock.get("retry_task_ids")
    if (
        not isinstance(locked_retry_ids, list)
        or not all(isinstance(item, str) for item in locked_retry_ids)
        or len(locked_retry_ids) != len(set(locked_retry_ids))
        or locked_retry_ids != unsolved
    ):
        raise RuntimeError("run lock retry task IDs do not match prior evidence")

    audit = json.loads(pre_audit_path.read_text(encoding="utf-8"))
    expected_audit = {
        "verdict": "PARTIAL",
        "benchmark": "ARC-AGI-1",
        "version": repo_commit,
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "claim": "local_reference_match",
        "manifest_sha256": manifest_sha256.lower(),
        "dataset_tasks": 400,
        "attempt_limit": 3,
        "independently_solved_tasks": len(prior_solved),
    }
    for field, expected in expected_audit.items():
        actual = audit.get(field)
        if field.endswith("sha256"):
            matches = str(actual).lower() == str(expected).lower()
        else:
            matches = actual == expected
        if not matches:
            raise RuntimeError(f"pre-audit mismatch in {field}")
    if audit.get("errors") != [] or audit.get("unprocessed_task_ids") != []:
        raise RuntimeError("pre-audit reports errors or unprocessed tasks")
    if audit.get("unsolved_task_ids") != unsolved:
        raise RuntimeError("pre-audit unsolved task IDs do not match prior evidence")
    attempts = audit.get("attempts")
    if (
        not isinstance(attempts, list)
        or len(attempts) != 2
        or [item.get("attempt") if isinstance(item, dict) else None for item in attempts]
        != [1, 2]
    ):
        raise RuntimeError("pre-audit attempt count mismatch")
    first_attempt = attempts[0]
    last_attempt = attempts[-1]
    if (
        not isinstance(last_attempt, dict)
        or last_attempt.get("attempt") != 2
        or Path(str(last_attempt.get("run_dir", ""))).resolve() != prior_path.parent
        or str(last_attempt.get("progress_sha256", "")).lower() != prior_sha256.lower()
    ):
        raise RuntimeError("pre-audit is not bound to prior attempt 2")
    locked_attempt1_progress = Path(str(run_lock.get("attempt1_progress", ""))).resolve()
    if (
        not locked_attempt1_progress.is_file()
        or Path(str(first_attempt.get("run_dir", ""))).resolve()
        != locked_attempt1_progress.parent
        or str(first_attempt.get("progress_sha256", "")).lower()
        != str(run_lock.get("attempt1_progress_sha256", "")).lower()
        or sha256(locked_attempt1_progress).lower()
        != str(run_lock.get("attempt1_progress_sha256", "")).lower()
    ):
        raise RuntimeError("pre-audit is not bound to locked attempt 1")
    return prior_solved, prior_sha256


def verify_bound_files(
    run_lock_path: Path,
    run_lock_sha256: str,
    adapter_path: Path,
    auditor_path: Path,
    pre_audit_path: Path,
    manifest_path: Path,
    models_path: Path,
    harness_main_path: Path,
    watchdog_path: Path,
    codex_cli_path: Path,
    run_lock: dict[str, object],
) -> None:
    expected = {
        run_lock_path: run_lock_sha256,
        adapter_path: str(run_lock["adapter_sha256"]),
        auditor_path: str(run_lock["auditor_sha256"]),
        pre_audit_path: str(run_lock["pre_audit_sha256"]),
        manifest_path: str(run_lock["dataset_manifest_sha256"]),
        models_path: str(run_lock["models_sha256"]),
        harness_main_path: str(run_lock["harness_main_sha256"]),
        watchdog_path: str(run_lock["watchdog_sha256"]),
        codex_cli_path: str(run_lock["codex_cli_sha256"]),
        Path(str(run_lock["attempt1_progress"])).resolve(): str(
            run_lock["attempt1_progress_sha256"]
        ),
        Path(str(run_lock["prior_progress"])).resolve(): str(
            run_lock["prior_progress_sha256"]
        ),
        Path(__file__).resolve(): str(run_lock["runner_sha256"]),
    }
    for path, digest in expected.items():
        if sha256(path).lower() != digest.lower():
            raise RuntimeError(f"locked file changed before release: {path.name}")
    if harness_tree_sha256(harness_main_path.parent).lower() != str(
        run_lock["harness_tree_sha256"]
    ).lower():
        raise RuntimeError("locked ARC harness source tree changed before release")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--codex-cli", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--prior-progress", type=Path)
    parser.add_argument("--expected-prior-progress-sha256")
    parser.add_argument("--run-lock", type=Path)
    parser.add_argument("--start-gate", type=Path)
    parser.add_argument("--start-ready", type=Path)
    args = parser.parse_args()
    if args.attempt == 3:
        required_retry_evidence = {
            "--prior-progress": args.prior_progress,
            "--expected-prior-progress-sha256": args.expected_prior_progress_sha256,
            "--run-lock": args.run_lock,
            "--start-gate": args.start_gate,
            "--start-ready": args.start_ready,
        }
        missing = [name for name, value in required_retry_evidence.items() if not value]
        if missing:
            raise SystemExit(
                "REFUSED: attempt 3 requires locked evidence and start handshake: "
                + ", ".join(missing)
            )
    if args.attempt == 4:
        missing = [
            name
            for name, value in {
                "--prior-progress": args.prior_progress,
                "--expected-prior-progress-sha256": args.expected_prior_progress_sha256,
            }.items()
            if not value
        ]
        if missing:
            raise SystemExit("REFUSED: attempt 4 requires " + ", ".join(missing))
    settings = ATTEMPT_SETTINGS[args.attempt]

    root = args.root.resolve()
    run_dir = args.run_dir.resolve()
    harness_repo = (root / "sources" / "ARC-AGI-Benchmarking").resolve()
    arc1_repo = (root / "sources" / "ARC-AGI-1").resolve()
    data_dir = (arc1_repo / "data" / "evaluation").resolve()
    manifest_path = (root / "manifests" / "ARC-AGI-1-evaluation.sha256").resolve()
    adapter_path = (
        harness_repo / "src" / "arc_agi_benchmarking" / "adapters" / "codexcli.py"
    ).resolve()
    models_path = (harness_repo / "src" / "arc_agi_benchmarking" / "models.yml").resolve()
    harness_main_path = (harness_repo / "main.py").resolve()
    auditor_path = (root / "tools" / "audit_arc_grid_runs.py").resolve()
    pre_audit_path = (root / "runtime" / "ARC1_PRE_ATTEMPT3_AUDIT.json").resolve()
    predictions_dir = run_dir / "predictions"
    scratchpad_dir = run_dir / "scratchpad"
    failed_predictions_dir = run_dir / "failed_predictions"
    progress_path = run_dir / "PROGRESS.json"
    events_path = run_dir / "EVENTS.jsonl"
    final_path = run_dir / "FINAL.json"

    if args.attempt in (3, 4):
        try:
            verify_fresh_result_state(
                progress_path, final_path, events_path, predictions_dir, scratchpad_dir
            )
            if failed_predictions_dir.exists() and any(failed_predictions_dir.iterdir()):
                raise RuntimeError("target run directory contains stale failed predictions")
        except RuntimeError as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc

    required_paths = [harness_repo, arc1_repo, data_dir, manifest_path, adapter_path, args.codex_cli]
    if args.attempt == 3:
        required_paths.extend([auditor_path, pre_audit_path, models_path, harness_main_path])
    for required in required_paths:
        if not required.exists():
            raise SystemExit(f"REFUSED: missing required path {required}")

    repo_commit = subprocess.check_output(
        ["git", "-C", str(arc1_repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if repo_commit != EXPECTED_REPO_COMMIT:
        raise SystemExit(f"REFUSED: ARC1 commit drift: {repo_commit}")

    task_ids = verify_inputs(data_dir, manifest_path)

    run_lock_sha256 = None
    run_lock = None
    watchdog_path = None
    if args.run_lock:
        run_lock_path = args.run_lock.resolve()
        if not run_lock_path.is_file():
            raise SystemExit(f"REFUSED: run lock missing: {run_lock_path}")
        lock_payload = run_lock_path.read_bytes()
        run_lock_sha256 = sha256_bytes(lock_payload)
        run_lock = json.loads(lock_payload)
        watchdog_path = Path(str(run_lock.get("watchdog", ""))).resolve()
        if args.attempt == 3 and not watchdog_path.is_file():
            raise SystemExit("REFUSED: locked watchdog path is missing")
        runner_python_path = Path(str(run_lock.get("runner_python", ""))).resolve()
        watchdog_host_path = Path(str(run_lock.get("watchdog_host", ""))).resolve()
        if args.attempt == 3 and runner_python_path != Path(sys.executable).resolve():
            raise SystemExit("REFUSED: locked Python runtime path mismatch")
        if args.attempt == 3 and Path(str(run_lock.get("codex_cli", ""))).resolve() != args.codex_cli.resolve():
            raise SystemExit("REFUSED: locked Codex CLI path mismatch")
        expected_lock = {
            "benchmark": "ARC-AGI-1",
            "route": "LOCAL_RESEARCH",
            "split": "evaluation",
            "run_attempt": args.attempt,
            "attempt_limit": 4 if args.attempt == 4 else 3,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "task_timeout_seconds": settings["task_timeout_seconds"],
            "shell_tool_enabled": settings["shell_tool_enabled"],
            "arc1_repo_commit": repo_commit,
            "dataset_manifest_sha256": sha256(manifest_path).upper(),
            "runner_sha256": sha256(Path(__file__).resolve()).upper(),
            "adapter_sha256": sha256(adapter_path).upper(),
        }
        if args.attempt == 3:
            expected_lock["analysis_strategy"] = ATTEMPT3_STRATEGY
            expected_lock["pre_audit_sha256"] = sha256(pre_audit_path).upper()
            expected_lock["auditor_sha256"] = sha256(auditor_path).upper()
            expected_lock["models_sha256"] = sha256(models_path).upper()
            expected_lock["harness_main_sha256"] = sha256(harness_main_path).upper()
            expected_lock["watchdog_sha256"] = sha256(watchdog_path).upper()
            expected_lock["harness_tree_sha256"] = harness_tree_sha256(harness_repo).upper()
            expected_lock["runner_python_sha256"] = sha256(runner_python_path).upper()
            expected_lock["watchdog_host_sha256"] = sha256(watchdog_host_path).upper()
            expected_lock["codex_cli_sha256"] = sha256(args.codex_cli.resolve()).upper()
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
        if args.attempt == 3 and Path(str(run_lock.get("pre_audit", ""))).resolve() != pre_audit_path:
            raise SystemExit("REFUSED: run lock pre-audit path mismatch")
        if args.attempt == 3 and (
            not isinstance(run_lock.get("start_nonce"), str)
            or len(str(run_lock["start_nonce"])) < 16
        ):
            raise SystemExit("REFUSED: run lock start nonce is missing")
        if args.attempt > 1 and not args.expected_prior_progress_sha256:
            raise SystemExit("REFUSED: locked retry requires expected prior progress hash")
        if args.start_gate:
            locked_start_gate = run_lock.get("start_gate")
            if not isinstance(locked_start_gate, str) or (
                Path(locked_start_gate).resolve() != args.start_gate.resolve()
            ):
                raise SystemExit("REFUSED: run lock start gate mismatch")
            locked_start_ready = run_lock.get("start_ready")
            if not args.start_ready or not isinstance(locked_start_ready, str) or (
                Path(locked_start_ready).resolve() != args.start_ready.resolve()
            ):
                raise SystemExit("REFUSED: run lock start ready path mismatch")

    prior_solved: set[str] = set()
    prior_progress_sha256 = None
    prior_path = None
    if args.prior_progress:
        prior_path = args.prior_progress.resolve()
        if not prior_path.is_file():
            raise SystemExit(f"REFUSED: prior progress missing: {prior_path}")
        if args.run_lock:
            if Path(str(run_lock.get("prior_progress", ""))).resolve() != prior_path:
                raise SystemExit("REFUSED: run lock prior progress path mismatch")
            if str(run_lock.get("prior_progress_sha256", "")).lower() != str(
                args.expected_prior_progress_sha256
            ).lower():
                raise SystemExit("REFUSED: run lock prior progress hash mismatch")
        try:
            if args.attempt == 3:
                prior_solved, prior_progress_sha256 = validate_prior_evidence(
                    prior_path,
                    str(args.expected_prior_progress_sha256),
                    run_lock,
                    task_ids,
                    repo_commit,
                    sha256(manifest_path),
                    pre_audit_path,
                )
            elif args.attempt == 4:
                prior_solved, prior_progress_sha256 = validate_retry4_evidence(
                    prior_path,
                    str(args.expected_prior_progress_sha256),
                    task_ids,
                    repo_commit,
                    sha256(manifest_path),
                )
            else:
                prior_payload = prior_path.read_bytes()
                prior_progress_sha256 = sha256_bytes(prior_payload)
                if (
                    args.expected_prior_progress_sha256
                    and prior_progress_sha256.lower()
                    != args.expected_prior_progress_sha256.lower()
                ):
                    raise RuntimeError("prior progress hash changed after approval")
                prior = json.loads(prior_payload)
                if prior.get("benchmark") != "ARC-AGI-1" or prior.get("repo_commit") != repo_commit:
                    raise RuntimeError("prior progress identity mismatch")
                prior_solved.update(prior.get("carried_solved_task_ids", []))
                prior_solved.update(
                    task_id
                    for task_id, record in prior.get("processed", {}).items()
                    if record.get("task_solved") is True
                )
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc

    start_gate_sha256 = None
    if args.start_gate:
        if not args.run_lock or run_lock_sha256 is None or not args.start_ready:
            raise SystemExit("REFUSED: start gate requires a verified run lock and ready path")
        start_gate_path = args.start_gate.resolve()
        start_ready_path = args.start_ready.resolve()
        if start_gate_path.exists() or start_ready_path.exists():
            raise SystemExit("REFUSED: stale start handshake file exists")
        write_json_atomic(
            start_ready_path,
            {
                "status": "READY",
                "worker_pid": os.getpid(),
                "run_lock_sha256": run_lock_sha256,
                "start_nonce": run_lock["start_nonce"],
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
        if type(gate.get("watchdog_pid")) is not int or gate["watchdog_pid"] <= 0:
            raise SystemExit("REFUSED: start gate watchdog PID missing")
        if type(gate.get("runner_wrapper_pid")) is not int or gate["runner_wrapper_pid"] <= 0:
            raise SystemExit("REFUSED: start gate wrapper PID missing")
        if gate.get("start_nonce") != run_lock["start_nonce"]:
            raise SystemExit("REFUSED: start gate nonce mismatch")
        if str(gate.get("run_lock_sha256", "")).lower() != run_lock_sha256.lower():
            raise SystemExit("REFUSED: start gate run lock hash mismatch")

        wrapper = process_identity(gate["runner_wrapper_pid"])
        watchdog = process_identity(gate["watchdog_pid"])
        wrapper_command = str(wrapper.get("CommandLine", "")) if wrapper else ""
        watchdog_command = str(watchdog.get("CommandLine", "")) if watchdog else ""
        wrapper_arguments = windows_command_arguments(wrapper_command)
        watchdog_arguments = windows_command_arguments(watchdog_command)
        wrapper_executable = Path(str(wrapper.get("ExecutablePath", ""))).resolve() if wrapper else None
        watchdog_executable = Path(str(watchdog.get("ExecutablePath", ""))).resolve() if watchdog else None
        try:
            lock_started = datetime.fromisoformat(str(run_lock["started_utc"])).timestamp()
            wrapper_started = datetime.fromisoformat(str(wrapper["CreationDate"])).timestamp()
            watchdog_started = datetime.fromisoformat(str(watchdog["CreationDate"])).timestamp()
            process_times_valid = (
                wrapper_started >= lock_started - 5 and watchdog_started >= lock_started - 5
            )
        except (KeyError, TypeError, ValueError):
            process_times_valid = False
        if (
            wrapper_executable != runner_python_path
            or not process_times_valid
            or not process_is_descendant(os.getpid(), gate["runner_wrapper_pid"])
            or len(wrapper_arguments) < 2
            or Path(wrapper_arguments[1]).resolve() != Path(__file__).resolve()
            or not exact_option_value(wrapper_arguments, "--run-dir", str(run_dir))
            or not exact_option_value(wrapper_arguments, "--attempt", "3")
        ):
            raise SystemExit("REFUSED: start gate wrapper process identity mismatch")
        if (
            watchdog_executable != watchdog_host_path
            or not exact_option_value(watchdog_arguments, "-File", str(watchdog_path))
            or not exact_option_value(watchdog_arguments, "-RunDir", str(run_dir))
            or not exact_option_value(watchdog_arguments, "-RunnerPid", str(gate["runner_wrapper_pid"]))
        ):
            raise SystemExit("REFUSED: start gate watchdog process identity mismatch")

        try:
            verify_bound_files(
                run_lock_path,
                run_lock_sha256,
                adapter_path,
                auditor_path,
                pre_audit_path,
                manifest_path,
                models_path,
                harness_main_path,
                watchdog_path,
                args.codex_cli.resolve(),
                run_lock,
            )
            current_commit = subprocess.check_output(
                ["git", "-C", str(arc1_repo), "rev-parse", "HEAD"], text=True
            ).strip()
            if current_commit != repo_commit:
                raise RuntimeError("ARC1 commit changed before release")
            if verify_inputs(data_dir, manifest_path) != task_ids:
                raise RuntimeError("ARC1 task list changed before release")
            checked_solved, checked_prior_sha = validate_prior_evidence(
                prior_path,
                str(args.expected_prior_progress_sha256),
                run_lock,
                task_ids,
                repo_commit,
                sha256(manifest_path),
                pre_audit_path,
            )
            if checked_solved != prior_solved or checked_prior_sha != prior_progress_sha256:
                raise RuntimeError("prior evidence changed before release")
            verify_fresh_result_state(
                progress_path, final_path, events_path, predictions_dir, scratchpad_dir
            )
            if failed_predictions_dir.exists() and any(failed_predictions_dir.iterdir()):
                raise RuntimeError("target run directory contains stale failed predictions")
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir.mkdir(parents=True, exist_ok=True)
    scratchpad_dir.mkdir(parents=True, exist_ok=True)
    failed_predictions_dir.mkdir(parents=True, exist_ok=True)

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
    if args.attempt in (3, 4) and solver.provider.model_config.kwargs.get("thread_id"):
        raise SystemExit("REFUSED: inherited thread resume is forbidden for isolated retry")
    solver.provider.model_config.kwargs["scratchpad_root"] = str(scratchpad_dir)
    solver.provider.model_config.kwargs["codex_cli_path"] = str(args.codex_cli.resolve())
    solver.provider.model_config.kwargs["auth_mode"] = "stored_login"
    solver.provider.model_config.kwargs["codex_exec_timeout_seconds"] = settings["task_timeout_seconds"]
    solver.provider.model_config.kwargs["model_reasoning_effort"] = REASONING_EFFORT
    solver.provider.model_config.kwargs["shell_tool_enabled"] = settings["shell_tool_enabled"]
    if args.attempt in (3, 4):
        solver.provider.model_config.kwargs["sandbox_mode"] = "read-only"
        solver.provider.model_config.kwargs["strict_isolation"] = True
    if settings["scratchpad_instructions"] is not None:
        solver.provider.model_config.kwargs["scratchpad_instructions"] = settings["scratchpad_instructions"]
    solver.model_config.model_name = MODEL
    solver.provider.model_config.model_name = MODEL

    if args.attempt == 3:
        try:
            verify_fresh_result_state(
                progress_path, final_path, events_path, predictions_dir, scratchpad_dir
            )
            if failed_predictions_dir.exists() and any(failed_predictions_dir.iterdir()):
                raise RuntimeError("target run directory contains stale failed predictions")
        except RuntimeError as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc

    if progress_path.is_file():
        if args.attempt == 3:
            raise SystemExit("REFUSED: attempt 3 cannot resume an existing PROGRESS")
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    else:
        progress = {
            "benchmark": "ARC-AGI-1",
            "route": "LOCAL_RESEARCH",
            "split": "evaluation",
            "run_attempt": args.attempt,
            "attempt_limit": 3,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "auth_mode": "stored_login",
            "task_timeout_seconds": settings["task_timeout_seconds"],
            "shell_tool_enabled": settings["shell_tool_enabled"],
            "analysis_strategy": ATTEMPT3_STRATEGY if args.attempt == 3 else ATTEMPT4_STRATEGY if args.attempt == 4 else None,
            "carried_solved_task_ids": sorted(prior_solved),
            "prior_progress_sha256": prior_progress_sha256,
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
        manifest_entries = parse_manifest(manifest_path)
        for index, task_id in enumerate(task_ids, start=1):
            if task_id in prior_solved:
                continue
            if task_id in progress["processed"]:
                continue
            started = utc_now()
            before = time.monotonic()
            unexpected_error = None
            try:
                if args.attempt == 4:
                    task_filename = f"{task_id}.json"
                    task_path = data_dir / task_filename
                    if sha256(task_path) != manifest_entries[task_filename]:
                        raise RuntimeError(f"task input changed before BLYSK generation: {task_id}")
                    task_payload = json.loads(task_path.read_text(encoding="utf-8"))
                    solver.provider.model_config.kwargs["scratchpad_instructions"] = build_blysk_instructions(
                        task_id, task_payload
                    )
                if args.attempt == 3:
                    verify_bound_files(
                        run_lock_path,
                        run_lock_sha256,
                        adapter_path,
                        auditor_path,
                        pre_audit_path,
                        manifest_path,
                        models_path,
                        harness_main_path,
                        watchdog_path,
                        args.codex_cli.resolve(),
                        run_lock,
                    )
                    task_filename = f"{task_id}.json"
                    if sha256(data_dir / task_filename) != manifest_entries[task_filename]:
                        raise RuntimeError(f"task input changed before generation: {task_id}")
                solver.generate_task_solution(data_dir=str(data_dir), task_id=task_id)
                if args.attempt == 4 and sha256(task_path) != manifest_entries[task_filename]:
                    raise RuntimeError(f"task input changed during BLYSK generation: {task_id}")
                if args.attempt == 3:
                    verify_bound_files(
                        run_lock_path,
                        run_lock_sha256,
                        adapter_path,
                        auditor_path,
                        pre_audit_path,
                        manifest_path,
                        models_path,
                        harness_main_path,
                        watchdog_path,
                        args.codex_cli.resolve(),
                        run_lock,
                    )
                    if sha256(data_dir / task_filename) != manifest_entries[task_filename]:
                        raise RuntimeError(f"task input changed during generation: {task_id}")
            except BaseException as exc:
                unexpected_error = f"{type(exc).__name__}: {exc}"
            submission_path = predictions_dir / f"{task_id}.json"
            failed_submission_sha256 = None
            if unexpected_error is not None:
                failed_submission_sha256 = quarantine_failed_submission(
                    submission_path, failed_predictions_dir
                )
            summary = summarize_generation(submission_path, unexpected_error)
            record = {
                "index": index,
                "task_id": task_id,
                "started_utc": started,
                "ended_utc": utc_now(),
                "duration_seconds": round(time.monotonic() - before, 3),
                **summary,
                "submission_sha256": sha256(submission_path) if submission_path.is_file() else None,
                "failed_submission_sha256": failed_submission_sha256,
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
                f"ARC1_PROGRESS completed={completed}/400 solved={solved} "
                f"task={task_id} status={record['status']} duration={record['duration_seconds']}",
                flush=True,
            )

    if args.attempt == 3:
        try:
            verify_bound_files(
                run_lock_path,
                run_lock_sha256,
                adapter_path,
                auditor_path,
                pre_audit_path,
                manifest_path,
                models_path,
                harness_main_path,
                watchdog_path,
                args.codex_cli.resolve(),
                run_lock,
            )
            if verify_inputs(data_dir, manifest_path) != task_ids:
                raise RuntimeError("ARC1 inputs changed before FINAL")
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise SystemExit(f"REFUSED: {exc}") from exc
        expected_retry_ids = set(task_ids) - prior_solved
        processed_ids = set(progress["processed"])
        if processed_ids != expected_retry_ids or prior_solved & processed_ids:
            raise SystemExit("REFUSED: final attempt 3 task partition is not exact")
        if len(prior_solved) + len(processed_ids) != 400:
            raise SystemExit("REFUSED: final attempt 3 coverage is not 400/400")
        for task_id, record in progress["processed"].items():
            if not isinstance(record, dict) or record.get("task_id") != task_id:
                raise SystemExit(f"REFUSED: final record identity mismatch for {task_id}")
            if type(record.get("task_solved")) is not bool:
                raise SystemExit(f"REFUSED: final task_solved is invalid for {task_id}")
            if (record.get("status") == "SOLVED") != record["task_solved"]:
                raise SystemExit(f"REFUSED: final status/solution mismatch for {task_id}")

    if args.attempt == 4:
        expected_retry_ids = set(task_ids) - prior_solved
        processed_ids = set(progress["processed"])
        if processed_ids != expected_retry_ids or prior_solved & processed_ids:
            raise SystemExit("REFUSED: retry-4 task partition is not exact")
        if len(prior_solved) + len(processed_ids) != 400:
            raise SystemExit("REFUSED: retry-4 coverage is not 400/400")

    records = list(progress["processed"].values())
    solved_tasks = len(prior_solved) + sum(bool(record["task_solved"]) for record in records)
    total_pairs = sum(int(record["pairs"]) for record in records)
    correct_pairs = sum(int(record["correct_pairs"]) for record in records)
    final = {
        "status": "COMPLETE",
        "benchmark": "ARC-AGI-1",
        "route": "LOCAL_RESEARCH",
        "split": "evaluation",
        "run_attempt": args.attempt,
        "attempt_limit": 4 if args.attempt == 4 else 3,
        "model": MODEL,
        "completed_tasks": len(prior_solved) + len(records),
        "carried_solved_tasks": len(prior_solved),
        "total_tasks": 400,
        "solved_tasks": solved_tasks,
        "task_accuracy": solved_tasks / 400,
        "correct_pairs": correct_pairs,
        "total_pairs": total_pairs,
        "pair_accuracy": correct_pairs / total_pairs if total_pairs else None,
        "ended_utc": utc_now(),
        "progress_sha256": sha256(progress_path),
    }
    write_json_atomic(final_path, final)
    print("ARC1_FINAL " + json.dumps(final, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())