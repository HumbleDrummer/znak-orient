"""Turn a list of CheckResult objects into a 0-100 score and severity buckets."""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks import CheckResult

_SEVERITY_DEDUCTION = {
    "critical": 25,
    "high": 12,
    "medium": 5,
    "info": 0,
}


@dataclass(frozen=True)
class ScoredAudit:
    domain: str
    score: int
    critical: list[CheckResult] = field(default_factory=list)
    high: list[CheckResult] = field(default_factory=list)
    medium: list[CheckResult] = field(default_factory=list)
    passed: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "score": self.score,
            "critical": [item.to_dict() for item in self.critical],
            "high": [item.to_dict() for item in self.high],
            "medium": [item.to_dict() for item in self.medium],
            "passed": [item.to_dict() for item in self.passed],
        }


def score_audit(domain: str, results: list[CheckResult]) -> ScoredAudit:
    """Deduct points per failing/warning check by severity; findings that PASS cost nothing."""

    score = 100
    critical, high, medium, passed = [], [], [], []
    for result in results:
        if result.status == "PASS":
            passed.append(result)
            continue
        score -= _SEVERITY_DEDUCTION.get(result.severity, 0)
        if result.severity == "critical":
            critical.append(result)
        elif result.severity == "high":
            high.append(result)
        else:
            medium.append(result)
    score = max(0, min(100, score))
    return ScoredAudit(domain=domain, score=score, critical=critical, high=high, medium=medium, passed=passed)
