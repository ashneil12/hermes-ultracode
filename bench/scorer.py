"""Deterministic scorer — match findings to planted bugs by signature keywords.

No LLM in the scoring loop, so the numbers are trustworthy. A finding matches a
bug if any of the bug's signature variants has ALL its keywords present (as
substrings) in the finding's text (claim + evidence + locator, lowercased).
"""

from dataclasses import dataclass, field
from typing import List, Set

from bench.tasks import Bug, BugTask


def _finding_text(f) -> str:
    return f"{getattr(f, 'claim', '')} {getattr(f, 'evidence', '')} {getattr(f, 'locator', '')}".lower()


def matches_bug(text: str, bug: Bug) -> bool:
    for variant in bug.signatures:
        if all(kw.lower() in text for kw in variant):
            return True
    return False


@dataclass
class Score:
    task_id: str
    n_findings: int = 0
    found_bug_names: Set[str] = field(default_factory=set)
    missed_bug_names: List[str] = field(default_factory=list)
    n_planted: int = 0
    spurious: int = 0  # findings matching no planted bug

    @property
    def recall(self) -> float:
        return len(self.found_bug_names) / self.n_planted if self.n_planted else 0.0

    @property
    def precision(self) -> float:
        tp = self.n_findings - self.spurious
        return tp / self.n_findings if self.n_findings else 0.0

    def as_dict(self):
        return {
            "task": self.task_id,
            "n_findings": self.n_findings,
            "found": sorted(self.found_bug_names),
            "missed": self.missed_bug_names,
            "spurious": self.spurious,
            "recall": round(self.recall, 3),
            "precision": round(self.precision, 3),
        }


def score(findings: List, task: BugTask) -> Score:
    s = Score(task_id=task.id, n_findings=len(findings), n_planted=len(task.planted))
    # which planted bugs got found
    for bug in task.planted:
        if any(matches_bug(_finding_text(f), bug) for f in findings):
            s.found_bug_names.add(bug.name)
        else:
            s.missed_bug_names.append(bug.name)
    # how many findings are spurious (match nothing planted)
    for f in findings:
        text = _finding_text(f)
        if not any(matches_bug(text, bug) for bug in task.planted):
            s.spurious += 1
    return s


def aggregate(scores: List[Score]) -> dict:
    if not scores:
        return {}
    n = len(scores)
    return {
        "tasks": n,
        "mean_recall": round(sum(s.recall for s in scores) / n, 3),
        "mean_precision": round(sum(s.precision for s in scores) / n, 3),
        "total_findings": sum(s.n_findings for s in scores),
        "total_spurious": sum(s.spurious for s in scores),
        "total_found": sum(len(s.found_bug_names) for s in scores),
        "total_planted": sum(s.n_planted for s in scores),
        "overall_recall": round(sum(len(s.found_bug_names) for s in scores) / max(1, sum(s.n_planted for s in scores)), 3),
    }
