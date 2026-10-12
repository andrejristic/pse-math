"""PSE Mathematical Research System — Phase 1 (journal + SHARED_LIB + gate)."""

from .model import Candidate, Check, Finding, GateResult, Status, Verdict
from .shared_lib import ResearchSharedLib
from .verifier import LeanBackend, SymbolicBackend, Verifier

__all__ = [
    "Candidate", "Check", "Finding", "GateResult", "Status", "Verdict",
    "ResearchSharedLib", "Verifier", "SymbolicBackend", "LeanBackend",
]
