"""Independently audit checkpointed ARC-AGI-1/2 grid runs.

The runner stores one prediction file per processed task and may carry solved
task IDs from an earlier attempt.  This tool verifies the dataset manifest,
prediction hashes, event/checkpoint agreement, direct grid/reference equality,
and the complete carry chain.  It never invokes a solver or edits a run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8-sig"), object_pairs_hook=reject_duplicate_keys)


def load_json(path: Path) -> Any:
    return decode_json(path.read_bytes())


def load_json_snapshot(path: Path) -> tuple[Any, str]:
    payload = path.read_bytes()
    return decode_json(payload), sha256_bytes(payload)


def validate_grid(grid: Any) -> str | None:
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        return "grid must have 1-30 rows"
    width = None
    for row_index, row in enumerate(grid):
        if not isinstance(row, list) or not 1 <= len(row) <= 30:
            return f"row {row_index} must have 1-30 cells"
        if width is None:
            width = len(row)
        elif len(row) != width:
            return f"row {row_index} makes grid nonrectangular"
        for column_index, cell in enumerate(row):
            if type(cell) is not int or not 0 <= cell <= 9:
                return f"cell {row_index},{column_index} must be integer 0-9"
    return None


def load_manifest(path: Path, data_dir: Path) -> tuple[dict[str, bytes], list[str], str]:
    task_payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    manifest_payload = path.read_bytes()
    manifest_sha256 = sha256_bytes(manifest_payload)
    manifest_text = manifest_payload.decode("utf-8")
    for line_number, raw in enumerate(manifest_text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"manifest line {line_number}: malformed")
            continue
        expected_hash, filename = parts
        filename = filename.lstrip("*")
        relative_path = Path(filename)
        if (
            relative_path.name != filename
            or relative_path.suffix != ".json"
            or not relative_path.stem
        ):
            errors.append(
                f"manifest line {line_number}: filename must be a bare <task_id>.json"
            )
            continue
        task_path = data_dir / relative_path
        task_id = relative_path.stem
        if task_id in seen:
            errors.append(f"manifest line {line_number}: duplicate task {task_id}")
            continue
        seen.add(task_id)
        if not task_path.is_file():
            errors.append(f"manifest task missing: {task_path}")
        else:
            task_payload = task_path.read_bytes()
            task_payloads[task_id] = task_payload
            if sha256_bytes(task_payload).lower() != expected_hash.lower():
                errors.append(f"manifest hash mismatch: {task_id}")
    actual_ids = {path.stem for path in data_dir.glob("*.json")}
    if seen != actual_ids:
        missing = sorted(seen - actual_ids)
        extra = sorted(actual_ids - seen)
        if missing:
            errors.append(f"dataset missing IDs: {missing}")
        if extra:
            errors.append(f"dataset extra IDs: {extra}")
    return task_payloads, errors, manifest_sha256


def reference_outputs(task_payload: bytes) -> list[Any]:
    task = decode_json(task_payload)
    tests = task.get("test") if isinstance(task, dict) else None
    if not isinstance(tests, list) or not tests:
        raise ValueError("missing nonempty test list")
    outputs: list[Any] = []
    for pair_index, pair in enumerate(tests):
        if not isinstance(pair, dict) or "output" not in pair:
            raise ValueError(f"test pair {pair_index}: missing output")
        grid_error = validate_grid(pair["output"])
        if grid_error:
            raise ValueError(f"test pair {pair_index}: {grid_error}")
        outputs.append(pair["output"])
    return outputs


def audit_prediction(path: Path, references: list[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pairs": len(references),
        "correct_pairs": 0,
        "task_solved": False,
        "errors": [],
    }
    try:
        payload, prediction_sha256 = load_json_snapshot(path)
        result["prediction_sha256"] = prediction_sha256
    except Exception as exc:  # report malformed artifacts without hiding later tasks
        result["errors"].append(f"prediction unreadable: {type(exc).__name__}: {exc}")
        result["prediction_sha256"] = sha256(path) if path.is_file() else None
        return result
    if not isinstance(payload, list) or len(payload) != len(references):
        result["errors"].append(
            f"prediction pair count: expected {len(references)}, got "
            f"{len(payload) if isinstance(payload, list) else 'non-list'}"
        )
        return result
    correct = 0
    for pair_index, (pair, reference) in enumerate(zip(payload, references)):
        attempt = pair.get("attempt_1") if isinstance(pair, dict) else None
        if not isinstance(attempt, dict):
            continue
        answer = attempt.get("answer")
        grid_error = validate_grid(answer)
        if grid_error:
            result["errors"].append(f"pair {pair_index}: invalid answer grid: {grid_error}")
            independent_correct = False
        else:
            independent_correct = answer == reference
        if independent_correct:
            correct += 1
        stored_correct = attempt.get("correct")
        if stored_correct is not independent_correct:
            result["errors"].append(
                f"pair {pair_index}: stored correct={stored_correct!r}, "
                f"independent={independent_correct}"
            )
    result["correct_pairs"] = correct
    result["task_solved"] = correct == len(references)
    return result


def read_events(path: Path) -> tuple[dict[str, Any], list[str]]:
    events: dict[str, Any] = {}
    errors: list[str] = []
    if not path.is_file():
        return events, [f"missing events file: {path}"]
    payload = path.read_bytes()
    for line_number, raw in enumerate(payload.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = decode_json(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            errors.append(f"events line {line_number}: invalid JSON: {exc}")
            continue
        task_id = event.get("task_id") if isinstance(event, dict) else None
        if not isinstance(task_id, str):
            errors.append(f"events line {line_number}: missing task_id")
        elif task_id in events:
            errors.append(f"events duplicate task: {task_id}")
        else:
            events[task_id] = event
    return events, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True, choices=("ARC-AGI-1", "ARC-AGI-2"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--split", default="evaluation")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, action="append", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--allow-inflight-prediction",
        action="store_true",
        help="permit exactly one manifest task prediction not yet committed to PROGRESS",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    manifest = args.manifest.resolve()
    run_dirs = [path.resolve() for path in args.run_dir]
    errors: list[str] = []
    task_payloads, manifest_errors, manifest_sha256 = load_manifest(manifest, data_dir)
    task_ids = list(task_payloads)
    errors.extend(manifest_errors)
    if not task_ids:
        errors.append("dataset manifest contains no tasks")
    references: dict[str, list[Any]] = {}
    for task_id, task_payload in task_payloads.items():
        try:
            references[task_id] = reference_outputs(task_payload)
        except Exception as exc:
            errors.append(f"reference {task_id}: {type(exc).__name__}: {exc}")

    solved_before: set[str] = set()
    independently_solved: dict[str, dict[str, Any]] = {}
    latest_records: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    expected_attempt = None
    identity: dict[str, Any] | None = None
    previous_progress_path: Path | None = None
    previous_progress_sha256: str | None = None

    for run_dir in run_dirs:
        progress_path = run_dir / "PROGRESS.json"
        lock_path = run_dir / "RUN_LOCK.json"
        if not progress_path.is_file():
            errors.append(f"missing progress: {progress_path}")
            continue
        if not lock_path.is_file():
            errors.append(f"missing lock: {lock_path}")
            continue
        progress, progress_sha256 = load_json_snapshot(progress_path)
        lock, lock_sha256 = load_json_snapshot(lock_path)
        attempt = progress.get("run_attempt")
        if not isinstance(attempt, int) or attempt not in (1, 2, 3):
            errors.append(f"{run_dir.name}: invalid attempt {attempt!r}")
            continue
        if expected_attempt is None and attempt != 1:
            errors.append(f"{run_dir.name}: first supplied attempt must be 1")
        if expected_attempt is not None and attempt != expected_attempt + 1:
            errors.append(f"{run_dir.name}: nonconsecutive attempt after {expected_attempt}")
        expected_attempt = attempt

        current_identity = {
            "benchmark": progress.get("benchmark"),
            "split": progress.get("split"),
            "repo_commit": progress.get("repo_commit"),
            "manifest_sha256": progress.get("manifest_sha256"),
            "model": progress.get("model"),
            "reasoning_effort": progress.get("reasoning_effort"),
            "attempt_limit": progress.get("attempt_limit"),
        }
        if identity is None:
            identity = current_identity
        else:
            for field in ("benchmark", "split", "repo_commit", "manifest_sha256", "model", "reasoning_effort", "attempt_limit"):
                if current_identity[field] != identity[field]:
                    errors.append(f"{run_dir.name}: identity drift in {field}")
        if current_identity["benchmark"] != args.benchmark:
            errors.append(f"{run_dir.name}: benchmark mismatch")
        if current_identity["split"] != args.split:
            errors.append(f"{run_dir.name}: split mismatch")
        if current_identity["repo_commit"] != args.version:
            errors.append(f"{run_dir.name}: repository version mismatch")
        if str(current_identity["manifest_sha256"]).lower() != manifest_sha256.lower():
            errors.append(f"{run_dir.name}: manifest identity mismatch")
        if lock.get("run_attempt") != attempt or lock.get("benchmark") != args.benchmark:
            errors.append(f"{run_dir.name}: RUN_LOCK identity mismatch")
        if "run_lock_sha256" in progress:
            recorded_run_lock_sha256 = progress["run_lock_sha256"]
            if not isinstance(recorded_run_lock_sha256, str) or (
                recorded_run_lock_sha256.lower() != lock_sha256.lower()
            ):
                errors.append(f"{run_dir.name}: PROGRESS run lock hash mismatch")
        if "run_dir" in lock:
            locked_run_dir = lock["run_dir"]
            try:
                resolved_locked_run_dir = (
                    Path(locked_run_dir).resolve() if isinstance(locked_run_dir, str) and locked_run_dir else None
                )
            except OSError:
                resolved_locked_run_dir = None
            if resolved_locked_run_dir != run_dir:
                errors.append(f"{run_dir.name}: RUN_LOCK target directory mismatch")
        repository_lock_field = (
            "arc1_repo_commit" if args.benchmark == "ARC-AGI-1" else "arc2_repo_commit"
        )
        lock_checks = {
            "route": progress.get("route"),
            "split": progress.get("split"),
            "attempt_limit": progress.get("attempt_limit"),
            "model": progress.get("model"),
            "reasoning_effort": progress.get("reasoning_effort"),
            repository_lock_field: progress.get("repo_commit"),
        }
        for field, expected in lock_checks.items():
            if lock.get(field) != expected:
                errors.append(f"{run_dir.name}: RUN_LOCK drift in {field}")
        if str(lock.get("dataset_manifest_sha256", "")).lower() != manifest_sha256.lower():
            errors.append(f"{run_dir.name}: RUN_LOCK manifest mismatch")
        if previous_progress_path is None:
            if progress.get("prior_progress_sha256") not in (None, ""):
                errors.append(f"{run_dir.name}: unexpected prior progress on first supplied attempt")
        else:
            if str(progress.get("prior_progress_sha256", "")).lower() != previous_progress_sha256:
                errors.append(f"{run_dir.name}: progress prior hash mismatch")
            if str(lock.get("prior_progress_sha256", "")).lower() != previous_progress_sha256:
                errors.append(f"{run_dir.name}: RUN_LOCK prior hash mismatch")
            lock_prior = lock.get("prior_progress")
            try:
                lock_prior_path = Path(lock_prior).resolve() if isinstance(lock_prior, str) else None
            except OSError:
                lock_prior_path = None
            if lock_prior_path != previous_progress_path:
                errors.append(f"{run_dir.name}: RUN_LOCK prior path mismatch")

        carried_raw = progress.get("carried_solved_task_ids", [])
        if not isinstance(carried_raw, list) or any(not isinstance(item, str) for item in carried_raw):
            errors.append(f"{run_dir.name}: carried_solved_task_ids must be a string list")
            carried_raw = []
        if len(carried_raw) != len(set(carried_raw)):
            errors.append(f"{run_dir.name}: duplicate carried_solved_task_ids")
        carried = set(carried_raw)
        unknown_carried = carried - set(task_ids)
        if unknown_carried:
            errors.append(f"{run_dir.name}: unknown carried task IDs {sorted(unknown_carried)}")
        if carried != solved_before:
            errors.append(
                f"{run_dir.name}: carry chain mismatch; expected {len(solved_before)}, got {len(carried)}"
            )
        processed = progress.get("processed")
        if not isinstance(processed, dict):
            errors.append(f"{run_dir.name}: processed is not an object")
            continue
        events, event_errors = read_events(run_dir / "EVENTS.jsonl")
        errors.extend(f"{run_dir.name}: {error}" for error in event_errors)
        processed_ids = set(processed)
        if set(events) != processed_ids:
            errors.append(
                f"{run_dir.name}: event/checkpoint ID mismatch "
                f"events={len(events)} processed={len(processed_ids)}"
            )
        prediction_ids = {path.stem for path in (run_dir / "predictions").glob("*.json")}
        extra_predictions = prediction_ids - processed_ids
        missing_predictions = processed_ids - prediction_ids
        if missing_predictions:
            errors.append(f"{run_dir.name}: missing predictions {sorted(missing_predictions)}")
        foreign_predictions = extra_predictions - set(task_ids)
        inflight_predictions = extra_predictions & set(task_ids)
        if foreign_predictions:
            errors.append(f"{run_dir.name}: predictions outside manifest {sorted(foreign_predictions)}")
        if inflight_predictions and not (
            args.allow_inflight_prediction and len(inflight_predictions) == 1
        ):
            errors.append(f"{run_dir.name}: extra predictions {sorted(inflight_predictions)}")

        run_solved = set(carried)
        run_correct_pairs = 0
        run_pairs = 0
        for task_id, record in processed.items():
            if task_id not in references:
                errors.append(f"{run_dir.name}: unknown task {task_id}")
                continue
            prediction_path = run_dir / "predictions" / f"{task_id}.json"
            audit = audit_prediction(prediction_path, references[task_id])
            run_pairs += audit["pairs"]
            run_correct_pairs += audit["correct_pairs"]
            for error in audit["errors"]:
                errors.append(f"{run_dir.name}/{task_id}: {error}")
            expected_hash = record.get("submission_sha256")
            actual_hash = audit["prediction_sha256"]
            if expected_hash != actual_hash:
                errors.append(f"{run_dir.name}/{task_id}: prediction hash mismatch")
            event = events.get(task_id)
            if event is not None and event != record:
                errors.append(f"{run_dir.name}/{task_id}: event/checkpoint record mismatch")
            stored_solved = record.get("task_solved") is True
            stored_status = record.get("status")
            if record.get("pairs") != audit["pairs"]:
                errors.append(f"{run_dir.name}/{task_id}: stored pairs mismatch")
            if record.get("correct_pairs") != audit["correct_pairs"]:
                errors.append(f"{run_dir.name}/{task_id}: stored correct_pairs mismatch")
            if stored_solved != audit["task_solved"]:
                errors.append(f"{run_dir.name}/{task_id}: stored task_solved mismatch")
            if audit["task_solved"] and stored_status != "SOLVED":
                errors.append(f"{run_dir.name}/{task_id}: stored status mismatch")
            if not audit["task_solved"] and stored_status == "SOLVED":
                errors.append(f"{run_dir.name}/{task_id}: stored status mismatch")
            if audit["task_solved"]:
                run_solved.add(task_id)
                independently_solved.setdefault(
                    task_id,
                    {
                        "attempt": attempt,
                        "run_dir": str(run_dir),
                        "prediction": str(prediction_path),
                        "prediction_sha256": actual_hash,
                        "pairs": audit["pairs"],
                    },
                )
            latest_records[task_id] = {
                "attempt": attempt,
                "stored_status": stored_status,
                "independently_solved": audit["task_solved"],
                "correct_pairs": audit["correct_pairs"],
                "pairs": audit["pairs"],
            }

        attempts.append(
            {
                "attempt": attempt,
                "run_dir": str(run_dir),
                "progress_sha256": progress_sha256,
                "lock_sha256": lock_sha256,
                "carried_solved": len(carried),
                "processed": len(processed),
                "solved_after_attempt": len(run_solved),
                "processed_correct_pairs": run_correct_pairs,
                "processed_pairs": run_pairs,
                "extra_prediction_files": sorted(extra_predictions),
            }
        )
        solved_before = run_solved
        previous_progress_path = progress_path.resolve()
        previous_progress_sha256 = progress_sha256.lower()

    solved_ids = sorted(independently_solved)
    unsolved_ids = sorted(set(task_ids) - set(solved_ids))
    processed_union = sorted(latest_records)
    unprocessed_ids = sorted(set(task_ids) - set(processed_union) - set(solved_ids))
    complete = bool(task_ids) and len(solved_ids) == len(task_ids) and not errors and len(attempts) <= 3
    verdict = "VERIFIED" if complete else ("PARTIAL" if args.allow_partial else "BLOCKED")
    report = {
        "verdict": verdict,
        "benchmark": args.benchmark,
        "version": args.version,
        "route": "LOCAL_RESEARCH",
        "split": args.split,
        "claim": "local_reference_match",
        "manifest": str(manifest),
        "manifest_sha256": manifest_sha256,
        "dataset_tasks": len(task_ids),
        "attempt_limit": 3,
        "attempts": attempts,
        "independently_solved_tasks": len(solved_ids),
        "task_accuracy": len(solved_ids) / len(task_ids) if task_ids else None,
        "unsolved_task_ids": unsolved_ids,
        "unprocessed_task_ids": unprocessed_ids,
        "latest_unsolved_records": {
            task_id: latest_records.get(task_id) for task_id in unsolved_ids if task_id in latest_records
        },
        "solved_evidence": independently_solved,
        "errors": errors,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)
    return 0 if verdict in ("VERIFIED", "PARTIAL") and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())