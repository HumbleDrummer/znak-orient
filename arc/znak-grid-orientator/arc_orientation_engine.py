"""Deterministic orientation cards and cross-task mechanism memory for ARC grids.

The engine reads training input/output pairs and test inputs only.  It emits
compact structural evidence, never predictions or hidden/reference outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any


SCHEMA = "ARC-COMPOSITIONAL-ORIENTATOR/1"
ATOMS = (
    "SELECT",
    "PARTITION",
    "MATCH",
    "COUNT",
    "TRANSFORM",
    "MOVE",
    "COPY",
    "RECOLOR",
    "MASK",
    "ASSEMBLE",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def validate_grid(grid: Any) -> list[list[int]]:
    if not isinstance(grid, list) or not grid or not all(isinstance(row, list) for row in grid):
        raise ValueError("grid must be a non-empty list of rows")
    width = len(grid[0])
    if width == 0 or any(len(row) != width for row in grid):
        raise ValueError("grid must be rectangular")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 9
        for row in grid
        for value in row
    ):
        raise ValueError("grid values must be exact integers from 0 through 9")
    return grid


def shape(grid: list[list[int]]) -> tuple[int, int]:
    return len(grid), len(grid[0])


def transform(grid: list[list[int]], name: str) -> list[list[int]]:
    if name == "identity":
        return [row[:] for row in grid]
    if name == "flip_h":
        return [row[::-1] for row in grid]
    if name == "flip_v":
        return [row[:] for row in grid[::-1]]
    if name == "transpose":
        return [list(row) for row in zip(*grid)]
    if name == "rot90":
        return [list(row) for row in zip(*grid[::-1])]
    if name == "rot180":
        return [row[::-1] for row in grid[::-1]]
    if name == "rot270":
        return [list(row) for row in zip(*grid)][::-1]
    raise ValueError(f"unknown transform {name}")


def symmetries(grid: list[list[int]]) -> list[str]:
    return [
        name
        for name in ("flip_h", "flip_v", "rot180", "transpose")
        if transform(grid, name) == grid
    ]


def connected_components(grid: list[list[int]], background: int) -> list[dict[str, Any]]:
    height, width = shape(grid)
    seen: set[tuple[int, int]] = set()
    components: list[dict[str, Any]] = []
    for row in range(height):
        for col in range(width):
            color = grid[row][col]
            if color == background or (row, col) in seen:
                continue
            queue = deque([(row, col)])
            seen.add((row, col))
            cells: list[tuple[int, int]] = []
            while queue:
                current = queue.popleft()
                cells.append(current)
                cr, cc = current
                for nr, nc in ((cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)):
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and (nr, nc) not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add((nr, nc))
                        queue.append((nr, nc))
            rows = [cell[0] for cell in cells]
            cols = [cell[1] for cell in cells]
            components.append(
                {
                    "color": color,
                    "size": len(cells),
                    "bbox": [min(rows), min(cols), max(rows), max(cols)],
                }
            )
    return components


def grid_facts(grid: Any) -> dict[str, Any]:
    grid = validate_grid(grid)
    counts = Counter(value for row in grid for value in row)
    background = min(counts, key=lambda color: (-counts[color], color))
    components = connected_components(grid, background)
    return {
        "shape": list(shape(grid)),
        "palette_size": len(counts),
        "background": background,
        "non_background_cells": sum(count for color, count in counts.items() if color != background),
        "components": len(components),
        "component_sizes": sorted(component["size"] for component in components),
        "symmetries": symmetries(grid),
    }


def _scale_factor(source: list[list[int]], target: list[list[int]]) -> tuple[int, int] | None:
    sh, sw = shape(source)
    th, tw = shape(target)
    if th % sh or tw % sw:
        return None
    row_scale, col_scale = th // sh, tw // sw
    if row_scale < 1 or col_scale < 1:
        return None
    expanded = [
        [source[row // row_scale][col // col_scale] for col in range(tw)]
        for row in range(th)
    ]
    return (row_scale, col_scale) if expanded == target else None


def pair_profile(pair: dict[str, Any]) -> dict[str, Any]:
    source = validate_grid(pair["input"])
    target = validate_grid(pair["output"])
    source_facts = grid_facts(source)
    target_facts = grid_facts(target)
    source_shape, target_shape = shape(source), shape(target)
    exact = [
        name
        for name in ("identity", "flip_h", "flip_v", "transpose", "rot90", "rot180", "rot270")
        if shape(transform(source, name)) == target_shape and transform(source, name) == target
    ]
    scale = _scale_factor(source, target)
    changed_cells = None
    transition_count = None
    if source_shape == target_shape:
        transitions = Counter(
            (source[row][col], target[row][col])
            for row in range(source_shape[0])
            for col in range(source_shape[1])
            if source[row][col] != target[row][col]
        )
        changed_cells = sum(transitions.values())
        transition_count = len(transitions)
    return {
        "input_shape": list(source_shape),
        "output_shape": list(target_shape),
        "same_shape": source_shape == target_shape,
        "input_palette_size": source_facts["palette_size"],
        "output_palette_size": target_facts["palette_size"],
        "input_components": source_facts["components"],
        "output_components": target_facts["components"],
        "changed_cells": changed_cells,
        "transition_count": transition_count,
        "exact_transforms": exact,
        "exact_scale": list(scale) if scale else None,
        "input_symmetries": source_facts["symmetries"],
        "output_symmetries": target_facts["symmetries"],
    }


def _relation(value_in: int, value_out: int, name: str) -> str:
    if value_out == value_in:
        return f"{name}_same"
    return f"{name}_{'up' if value_out > value_in else 'down'}"


def _pair_tags(profile: dict[str, Any]) -> set[str]:
    tags = {
        "shape_same" if profile["same_shape"] else "shape_changed",
        _relation(profile["input_palette_size"], profile["output_palette_size"], "palette"),
        _relation(profile["input_components"], profile["output_components"], "components"),
    }
    tags.update(f"exact_{name}" for name in profile["exact_transforms"])
    if profile["exact_scale"]:
        tags.add("exact_scale")
    changed = profile["changed_cells"]
    if changed is not None:
        area = profile["input_shape"][0] * profile["input_shape"][1]
        density = changed / area
        tags.add("edit_sparse" if density <= 0.2 else "edit_medium" if density <= 0.6 else "edit_dense")
    if set(profile["output_symmetries"]) - set(profile["input_symmetries"]):
        tags.add("symmetry_gained")
    return tags


def tool_recipe(profile: dict[str, Any]) -> list[str]:
    tags = set(profile.get("stable_tags") or profile.get("tags") or [])
    recipe = ["MATCH"]
    if any(tag.startswith("exact_") for tag in tags):
        recipe.append("TRANSFORM")
    if any(tag in tags for tag in ("palette_up", "palette_down")):
        recipe.append("RECOLOR")
    elif any(pair.get("changed_cells") for pair in profile.get("train", [])):
        recipe.append("RECOLOR")
    if any(tag in tags for tag in ("components_up", "components_down", "shape_changed", "shape_mixed")):
        recipe.append("ASSEMBLE")
    return recipe[:4]


def task_profile(task: dict[str, Any]) -> dict[str, Any]:
    train = task.get("train")
    test = task.get("test")
    if not isinstance(train, list) or not train or not isinstance(test, list) or not test:
        raise ValueError("task must contain non-empty train and test lists")
    profiles = [pair_profile(pair) for pair in train]
    test_facts = [grid_facts(pair["input"]) for pair in test]
    pair_tags = [_pair_tags(profile) for profile in profiles]
    tags = set().union(*pair_tags)
    if not all(profile["same_shape"] for profile in profiles) and not all(
        not profile["same_shape"] for profile in profiles
    ):
        tags.discard("shape_same")
        tags.discard("shape_changed")
        tags.add("shape_mixed")
    stable_tags = set.intersection(*pair_tags) if pair_tags else set()
    if "shape_mixed" in tags:
        stable_tags.discard("shape_same")
        stable_tags.discard("shape_changed")
        stable_tags.add("shape_mixed")
    variant_tags = tags - stable_tags
    return {
        "train_pairs": len(profiles),
        "test_inputs": len(test_facts),
        "train": profiles,
        "test": test_facts,
        "tags": sorted(tags),
        "stable_tags": sorted(stable_tags),
        "variant_tags": sorted(variant_tags),
    }


def profile_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    a, b = set(left["tags"]), set(right["tags"])
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def nearest_mechanisms(
    profile: dict[str, Any], bank: dict[str, Any], limit: int = 3
) -> list[dict[str, Any]]:
    candidates = []
    for record in bank.get("solved_mechanisms", []):
        score = profile_similarity(profile, record["profile"])
        candidates.append(
            {
                "task_id": record["task_id"],
                "similarity": round(score, 3),
                "shared_tags": sorted(set(profile["tags"]) & set(record["profile"]["tags"])),
            }
        )
    return sorted(candidates, key=lambda item: (-item["similarity"], item["task_id"]))[:limit]


def orientation_card(task_id: str, task: dict[str, Any], bank: dict[str, Any]) -> str:
    profile = task_profile(task)
    matches = nearest_mechanisms(profile, bank)
    pair_lines = []
    for index, pair in enumerate(profile["train"], start=1):
        pair_lines.append(
            "train%d in=%sx%s out=%sx%s colors=%s>%s components=%s>%s changed=%s exact=%s"
            % (
                index,
                pair["input_shape"][0],
                pair["input_shape"][1],
                pair["output_shape"][0],
                pair["output_shape"][1],
                pair["input_palette_size"],
                pair["output_palette_size"],
                pair["input_components"],
                pair["output_components"],
                pair["changed_cells"] if pair["changed_cells"] is not None else "dimension-change",
                ",".join(pair["exact_transforms"]) or "none",
            )
        )
    test_lines = [
        "test%d shape=%sx%s colors=%s components=%s sym=%s"
        % (
            index,
            facts["shape"][0],
            facts["shape"][1],
            facts["palette_size"],
            facts["components"],
            ",".join(facts["symmetries"]) or "none",
        )
        for index, facts in enumerate(profile["test"], start=1)
    ]
    match_lines = [
        "prior=%s similarity=%.3f shared=%s"
        % (match["task_id"], match["similarity"], ",".join(match["shared_tags"]) or "none")
        for match in matches
    ] or ["prior=none"]
    return "\n".join(
        [
            "ARC ORIENTATION CARD v1 task=" + task_id,
            "Observed tags: " + ",".join(profile["tags"]),
            "BLYSK stable=" + (",".join(profile["stable_tags"]) or "none"),
            "BLYSK variant=" + (",".join(profile["variant_tags"]) or "none"),
            "Tool recipe: " + " > ".join(tool_recipe(profile)),
            *pair_lines,
            *test_lines,
            "Related solved mechanism fingerprints:",
            *match_lines,
            "Three gears: UNDERSTAND facts; DISTINGUISH wrapper from mechanism; DEPLOY and prove.",
            "Atoms: " + " > ".join(ATOMS),
            "A prior match is only a hypothesis. Reject any rule that fails one visible training cell.",
            "Return only the final rectangular JSON grid, with no commentary.",
            "",
        ]
    )


def build_bank(
    data_dir: Path,
    prior_progress_path: Path,
    manifest_path: Path,
    source_attempt: int,
) -> dict[str, Any]:
    prior_bytes = prior_progress_path.read_bytes()
    prior = json.loads(prior_bytes)
    if prior.get("run_attempt") != source_attempt:
        raise ValueError("prior progress attempt mismatch")
    if prior.get("benchmark") != "ARC-AGI-2" or prior.get("split") != "evaluation":
        raise ValueError("prior progress identity mismatch")
    processed = prior.get("processed")
    carried = prior.get("carried_solved_task_ids")
    if not isinstance(processed, dict) or not isinstance(carried, list):
        raise ValueError("prior progress task collections are malformed")
    solved = set(carried)
    solved.update(
        task_id for task_id, record in processed.items() if record.get("task_solved") is True
    )
    profiles = []
    solved_mechanisms = []
    for path in sorted(data_dir.glob("*.json")):
        task_id = path.stem
        profile = task_profile(json.loads(path.read_text(encoding="utf-8")))
        profiles.append({"task_id": task_id, "profile": profile})
        if task_id in solved:
            solved_mechanisms.append({"task_id": task_id, "profile": profile})
    if len(profiles) != prior.get("total_tasks"):
        raise ValueError("profile count does not match prior progress")
    return {
        "schema": SCHEMA,
        "benchmark": "ARC-AGI-2",
        "route": "LOCAL_RESEARCH_ADAPTIVE",
        "split": "evaluation",
        "source_attempt": source_attempt,
        "next_attempt": source_attempt + 1,
        "adaptive_cross_task_memory": True,
        "blind_evaluation": False,
        "data_scope": "training_inputs_outputs_and_test_inputs_only_plus_prior_solved_status",
        "prior_progress": str(prior_progress_path.resolve()),
        "prior_progress_sha256": hashlib.sha256(prior_bytes).hexdigest(),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": sha256(manifest_path),
        "task_profiles": profiles,
        "solved_mechanisms": solved_mechanisms,
        "solved_mechanism_count": len(solved_mechanisms),
        "operator_atoms": list(ATOMS),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--prior-progress", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-attempt", required=True, type=int, choices=(1, 2))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    bank = build_bank(args.data_dir, args.prior_progress, args.manifest, args.source_attempt)
    write_json_atomic(args.output, bank)
    print(
        json.dumps(
            {
                "status": "BUILT",
                "output": str(args.output.resolve()),
                "sha256": sha256(args.output),
                "task_profiles": len(bank["task_profiles"]),
                "solved_mechanisms": bank["solved_mechanism_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())