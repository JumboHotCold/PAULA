"""List-compatible retrieval diagnostics; no user state or storage."""
from dataclasses import dataclass, field


class EvidenceList(list):
    def __init__(self, values=(), status='ok'):
        super().__init__(values)
        self.status = status


@dataclass
class RetrievalOutcome:
    evidence: list = field(default_factory=list)
    status: str = 'no_match'
    attempts: int = 1
    elapsed_ms: float = 0
