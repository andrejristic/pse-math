"""
ModelBackend — the LLM boundary (build spec Sec 13 MODELS, + A5 phrasing).

Like VerifierBackend, the model is pluggable so the Surface/Dell split is config,
not a fork. The rest of the system depends only on this interface.

CRITICAL boundaries preserved here:
  - Candidate GENERATION is a COSTED action (build spec Sec 13): every call
    reports a cost so budget accounting means something.
  - PHRASING is structured-in / natural-language-out; the generator invents
    nothing (build spec Sec 11, PSELGenerator). The phrase() method is given
    structured data and may only render it.

Backends:
  - StubModelBackend: deterministic, no model. Generation returns a marked
    placeholder; phrasing echoes the structured data. Enough to build and test
    every consumer on the Surface with zero model weight.
  - LocalModelBackend / RemoteModelBackend: real llama.cpp / API. Declared here
    as loud-failing placeholders; wired on the Dell.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ModelResult:
    text: str
    cost: float = 0.0        # costed action (tokens / arbitrary units)
    backend: str = ""


class ModelBackend(Protocol):
    def generate_candidate(self, prompt: str, context: dict[str, Any]) -> ModelResult:
        """Expensive: propose a proof candidate. Reports a cost."""
        ...

    def phrase(self, structured: dict[str, Any]) -> str:
        """Cheap: render structured data as prose. Invents nothing."""
        ...


class StubModelBackend:
    """No model. Deterministic. For building/testing consumers on the Surface."""

    name = "stub"

    def generate_candidate(self, prompt: str, context: dict[str, Any]) -> ModelResult:
        # Deterministic placeholder — clearly not a real proof.
        return ModelResult(
            text="-- STUB: no model wired; candidate generation is a Dell action",
            cost=0.0, backend=self.name,
        )

    def phrase(self, structured: dict[str, Any]) -> str:
        # Render structured data verbatim; a real backend would prose it. This is
        # deliberately mechanical so tests can assert on exact content.
        parts = [f"{k}={v}" for k, v in sorted(structured.items())]
        return "; ".join(parts)


class LocalModelBackend:
    """Small local llama.cpp model (Surface, light phrasing/triage). Placeholder."""

    name = "local"

    def __init__(self, model_path: str) -> None:
        raise NotImplementedError(
            "LocalModelBackend is wired on-device with llama.cpp; not built in the "
            "shared core. Use StubModelBackend on the Surface for now."
        )


class RemoteModelBackend:
    """Remote API for heavy candidate generation (Dell). Placeholder."""

    name = "remote"

    def __init__(self, **cfg: Any) -> None:
        raise NotImplementedError(
            "RemoteModelBackend is a Dell-profile action; not built in the shared "
            "core. Candidate generation at scale belongs on the deployment machine."
        )
