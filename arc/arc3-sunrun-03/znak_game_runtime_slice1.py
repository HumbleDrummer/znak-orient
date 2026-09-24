"""ZNAK Game Runtime v0.2 — Slice 1.

Implements:
- C01 ObservationEventAdapter
- C02 ActionContract
- C07 RunTrace

The module is intentionally dependency-free and does not dispatch actions to any
real environment. It prepares and authorizes exactly one typed action at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Any


TERMINAL_STATES = {"WIN", "GAME_OVER"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionSpec:
    action_type: str
    required_params: tuple[str, ...] = ()
    constraints: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ActionSpec":
        action_type = str(raw["action_type"])
        required = tuple(str(x) for x in raw.get("required_params", []))
        constraints = raw.get("constraints")
        if constraints is not None and not isinstance(constraints, dict):
            raise ValueError("constraints must be an object or null")
        return cls(action_type=action_type, required_params=required, constraints=constraints)


@dataclass(frozen=True)
class Subframe:
    index: int
    grid: Any
    frame_hash: str


@dataclass(frozen=True)
class ObservationEvent:
    run_id: str
    game_id: str
    level_id: str | None
    action_seq: int
    event_seq: int
    cause_action_id: str | None
    cause_action_type: str | None
    cause_action_payload: dict[str, Any] | None
    terminal_state: str
    level_counter: int | None
    score: float | int | None
    reward: float | int | None
    available_actions: tuple[ActionSpec, ...]
    subframes: tuple[Subframe, ...]
    settled_subframe_index: int | None
    source_ref: str

    @property
    def event_hash(self) -> str:
        return _sha256_json(
            {
                "run_id": self.run_id,
                "game_id": self.game_id,
                "level_id": self.level_id,
                "action_seq": self.action_seq,
                "event_seq": self.event_seq,
                "cause_action_id": self.cause_action_id,
                "cause_action_type": self.cause_action_type,
                "cause_action_payload": self.cause_action_payload,
                "terminal_state": self.terminal_state,
                "level_counter": self.level_counter,
                "score": self.score,
                "reward": self.reward,
                "available_actions": [asdict(x) for x in self.available_actions],
                "subframes": [asdict(x) for x in self.subframes],
                "settled_subframe_index": self.settled_subframe_index,
                "source_ref": self.source_ref,
            }
        )


class ObservationEventAdapter:
    """C01. Normalize one response while preserving all ordered subframes."""

    @staticmethod
    def adapt(
        response: dict[str, Any],
        *,
        run_id: str,
        game_id: str,
        action_seq: int,
        event_seq: int,
        cause_action_id: str | None = None,
        cause_action_type: str | None = None,
        cause_action_payload: dict[str, Any] | None = None,
        source_ref: str = "fixture",
    ) -> ObservationEvent:
        if not isinstance(response, dict):
            raise ValueError("response must be an object")

        frames = response.get("subframes")
        if frames is None:
            single = response.get("frame")
            frames = [single] if single is not None else None
        if not isinstance(frames, list) or not frames:
            raise ValueError("response must contain frame or non-empty subframes")

        subframes: list[Subframe] = []
        for index, grid in enumerate(frames):
            if grid is None:
                raise ValueError("subframe cannot be null")
            subframes.append(Subframe(index=index, grid=grid, frame_hash=_sha256_json(grid)))

        raw_actions = response.get("available_actions", [])
        if not isinstance(raw_actions, list):
            raise ValueError("available_actions must be a list")
        specs = tuple(ActionSpec.from_mapping(item) for item in raw_actions)

        hard = response.get("hard_state") or {}
        if not isinstance(hard, dict):
            raise ValueError("hard_state must be an object")

        terminal = str(hard.get("terminal_state", "UNKNOWN"))
        level_counter = hard.get("level_counter")
        score = hard.get("score")
        reward = hard.get("reward")

        settled = response.get("settled_subframe_index")
        if settled is None:
            settled = len(subframes) - 1
        if not isinstance(settled, int) or not (0 <= settled < len(subframes)):
            raise ValueError("settled_subframe_index out of range")

        level_id = response.get("level_id")
        if level_id is not None:
            level_id = str(level_id)

        return ObservationEvent(
            run_id=run_id,
            game_id=game_id,
            level_id=level_id,
            action_seq=action_seq,
            event_seq=event_seq,
            cause_action_id=cause_action_id,
            cause_action_type=cause_action_type,
            cause_action_payload=cause_action_payload,
            terminal_state=terminal,
            level_counter=level_counter,
            score=score,
            reward=reward,
            available_actions=specs,
            subframes=tuple(subframes),
            settled_subframe_index=settled,
            source_ref=source_ref,
        )


@dataclass(frozen=True)
class ActionCandidate:
    action_type: str
    params: dict[str, Any]


@dataclass(frozen=True)
class ActionAuthorization:
    legal: bool
    reason_code: str
    action_type: str
    params: dict[str, Any]
    dispatch_payload: dict[str, Any] | None


class ActionContract:
    """C02. Validate action availability, parameters and hard terminal state."""

    @staticmethod
    def authorize(
        candidate: ActionCandidate,
        observation: ObservationEvent,
    ) -> ActionAuthorization:
        if observation.terminal_state in TERMINAL_STATES:
            return ActionAuthorization(
                legal=False,
                reason_code="HARD_TERMINAL_STATE",
                action_type=candidate.action_type,
                params=dict(candidate.params),
                dispatch_payload=None,
            )

        by_type = {spec.action_type: spec for spec in observation.available_actions}
        spec = by_type.get(candidate.action_type)
        if spec is None:
            return ActionAuthorization(
                legal=False,
                reason_code="ACTION_UNAVAILABLE",
                action_type=candidate.action_type,
                params=dict(candidate.params),
                dispatch_payload=None,
            )

        missing = [name for name in spec.required_params if name not in candidate.params]
        if missing:
            return ActionAuthorization(
                legal=False,
                reason_code="MISSING_REQUIRED_PARAM:" + ",".join(sorted(missing)),
                action_type=candidate.action_type,
                params=dict(candidate.params),
                dispatch_payload=None,
            )

        constraints = spec.constraints or {}
        for name, rule in constraints.items():
            if name not in candidate.params:
                continue
            value = candidate.params[name]
            if not isinstance(rule, dict):
                return ActionAuthorization(
                    legal=False,
                    reason_code=f"INVALID_CONSTRAINT_SCHEMA:{name}",
                    action_type=candidate.action_type,
                    params=dict(candidate.params),
                    dispatch_payload=None,
                )
            if "min" in rule and value < rule["min"]:
                return ActionAuthorization(
                    legal=False,
                    reason_code=f"PARAM_OUT_OF_RANGE:{name}",
                    action_type=candidate.action_type,
                    params=dict(candidate.params),
                    dispatch_payload=None,
                )
            if "max" in rule and value > rule["max"]:
                return ActionAuthorization(
                    legal=False,
                    reason_code=f"PARAM_OUT_OF_RANGE:{name}",
                    action_type=candidate.action_type,
                    params=dict(candidate.params),
                    dispatch_payload=None,
                )
            if "enum" in rule and value not in rule["enum"]:
                return ActionAuthorization(
                    legal=False,
                    reason_code=f"PARAM_NOT_ALLOWED:{name}",
                    action_type=candidate.action_type,
                    params=dict(candidate.params),
                    dispatch_payload=None,
                )

        payload = {"action_type": candidate.action_type, "params": dict(candidate.params)}
        return ActionAuthorization(
            legal=True,
            reason_code="LEGAL",
            action_type=candidate.action_type,
            params=dict(candidate.params),
            dispatch_payload=payload,
        )


@dataclass(frozen=True)
class TraceDecision:
    action_seq: int
    observation_event_hash: str
    candidate_action: dict[str, Any]
    authorization: dict[str, Any]
    prediction: dict[str, Any]
    component_versions: dict[str, str]


@dataclass(frozen=True)
class TraceOutcome:
    action_seq: int
    result_event_hash: str
    actual_effect: dict[str, Any]


class RunTrace:
    """C07. Append-only binding of observation → decision/prediction → result."""

    def __init__(self) -> None:
        self._decisions: list[TraceDecision] = []
        self._outcomes: list[TraceOutcome] = []

    @property
    def decisions(self) -> tuple[TraceDecision, ...]:
        return tuple(self._decisions)

    @property
    def outcomes(self) -> tuple[TraceOutcome, ...]:
        return tuple(self._outcomes)

    def append_decision(
        self,
        *,
        action_seq: int,
        observation: ObservationEvent,
        candidate: ActionCandidate,
        authorization: ActionAuthorization,
        prediction: dict[str, Any],
        component_versions: dict[str, str],
    ) -> TraceDecision:
        expected_seq = len(self._decisions)
        if action_seq != expected_seq:
            raise ValueError(f"decision sequence mismatch: expected {expected_seq}, got {action_seq}")
        if action_seq > len(self._outcomes):
            raise ValueError("previous action outcome must be recorded before next decision")

        item = TraceDecision(
            action_seq=action_seq,
            observation_event_hash=observation.event_hash,
            candidate_action={"action_type": candidate.action_type, "params": dict(candidate.params)},
            authorization={
                "legal": authorization.legal,
                "reason_code": authorization.reason_code,
                "dispatch_payload": authorization.dispatch_payload,
            },
            prediction=json.loads(_canonical_json(prediction)),
            component_versions=dict(sorted(component_versions.items())),
        )
        self._decisions.append(item)
        return item

    def append_outcome(
        self,
        *,
        action_seq: int,
        result_event: ObservationEvent,
        actual_effect: dict[str, Any],
    ) -> TraceOutcome:
        if action_seq >= len(self._decisions):
            raise ValueError("outcome has no matching decision")
        if any(item.action_seq == action_seq for item in self._outcomes):
            raise ValueError("outcome already recorded for action")
        if action_seq != len(self._outcomes):
            raise ValueError("outcomes must be appended in order")

        item = TraceOutcome(
            action_seq=action_seq,
            result_event_hash=result_event.event_hash,
            actual_effect=json.loads(_canonical_json(actual_effect)),
        )
        self._outcomes.append(item)
        return item

    def canonical_snapshot(self) -> dict[str, Any]:
        return {
            "decisions": [asdict(x) for x in self._decisions],
            "outcomes": [asdict(x) for x in self._outcomes],
        }

    @property
    def trace_hash(self) -> str:
        return _sha256_json(self.canonical_snapshot())


class Slice1Runtime:
    """Small vertical slice: observe → authorize one action → trace → observe result."""

    COMPONENT_VERSIONS = {
        "observation_event_adapter": "0.2",
        "action_contract": "0.2",
        "run_trace": "0.2",
    }

    def __init__(self) -> None:
        self.trace = RunTrace()

    def prepare_action(
        self,
        *,
        observation: ObservationEvent,
        action_seq: int,
        candidate: ActionCandidate,
        prediction: dict[str, Any],
    ) -> ActionAuthorization:
        auth = ActionContract.authorize(candidate, observation)
        self.trace.append_decision(
            action_seq=action_seq,
            observation=observation,
            candidate=candidate,
            authorization=auth,
            prediction=prediction,
            component_versions=self.COMPONENT_VERSIONS,
        )
        return auth

    def record_result(
        self,
        *,
        action_seq: int,
        result_event: ObservationEvent,
        actual_effect: dict[str, Any],
    ) -> TraceOutcome:
        return self.trace.append_outcome(
            action_seq=action_seq,
            result_event=result_event,
            actual_effect=actual_effect,
        )
