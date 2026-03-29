"""
ModelRouter — routes LLM tasks by complexity to minimise cost.

Tier 1 (cheapest/fastest): Groq + Llama-3.1-8B  — classification tasks
Tier 2 (balanced):         Gemini 1.5 Flash      — standard alert generation
Tier 3 (most capable):     GPT-4o                — conflicted signals, fallback

Each tier falls through to the next on error.
"""
from __future__ import annotations

import os

from backend.models import AuditStep

# ---------------------------------------------------------------------------
# Cost table (USD per call, approximate)
# ---------------------------------------------------------------------------
# GPT-4o baseline used for savings calculation
GPT4O_COST: float = 0.02

ROUTING_TABLE: dict[str, tuple[str, float]] = {
    # task_type → (model_label, cost_per_call)
    "sector_tagging":        ("groq/llama-3.1-8b-instant", 0.000005),
    "signal_type_detection": ("groq/llama-3.1-8b-instant", 0.000005),
    "promoter_detection":    ("groq/llama-3.1-8b-instant", 0.000010),
    "standard_alert":        ("gemini-1.5-flash",           0.0005),
    "conflicted_alert":      ("gpt-4o",                     0.02),
}


class ModelRouter:
    ROUTING_TABLE = ROUTING_TABLE
    GPT4O_COST = GPT4O_COST

    def route(self, task_type: str) -> tuple[str, float]:
        """Return (model_label, cost_saved_vs_gpt4o)."""
        model, cost = self.ROUTING_TABLE.get(task_type, ("gpt-4o", 0.02))
        cost_saved = self.GPT4O_COST - cost
        return model, cost_saved

    def log_routing(self, task_type: str, audit_trail: list[AuditStep]) -> str:
        """Log routing decision to audit trail and return model label."""
        model, cost_saved = self.route(task_type)
        note = (
            f"Used {model} for {task_type} — "
            f"saved ~${cost_saved:.4f} vs GPT-4o"
        )
        audit_trail.append(
            AuditStep(
                agent="ModelRouter",
                action="route",
                model_used=model,
                output_summary=note,
                task_type=task_type,
                estimated_cost_saved=cost_saved,
            )
        )
        return model


# ---------------------------------------------------------------------------
# LLM call functions — each raises on failure so caller can cascade
# ---------------------------------------------------------------------------

def call_groq(prompt: str, model: str = "llama-3.1-8b-instant") -> str:
    """Call Groq API (Llama). Free tier, very fast."""
    from langchain_groq import ChatGroq
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    llm = ChatGroq(model=model, groq_api_key=api_key, temperature=0.1)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def call_gemini(prompt: str, model: str = "gemini-1.5-flash-latest") -> str:
    """Call Google Gemini API."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.1)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def call_openai(prompt: str, model: str = "gpt-4o") -> str:
    """Call OpenAI API."""
    from langchain_openai import ChatOpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    llm = ChatOpenAI(model=model, openai_api_key=api_key, temperature=0.1)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def generate_with_cascade(
    prompt: str,
    preferred_model: str,
    audit_trail: list[AuditStep],
) -> tuple[str, str, bool, str | None]:
    """
    Try preferred_model first, then cascade through fallbacks.

    Returns: (raw_text, model_used, fallback_occurred, fallback_reason)

    Cascade order:
      groq/* → gemini-* → gpt-4o
    """
    attempts: list[tuple[str, callable]] = []

    # Build attempt list starting from preferred model
    if preferred_model.startswith("groq/"):
        groq_model = preferred_model.split("/", 1)[1]
        attempts = [
            (preferred_model, lambda p, m=groq_model: call_groq(p, m)),
            ("gemini-1.5-flash", lambda p: call_gemini(p, "gemini-1.5-flash-latest")),
            ("gpt-4o", lambda p: call_openai(p, "gpt-4o")),
        ]
    elif preferred_model.startswith("gemini"):
        attempts = [
            (preferred_model, lambda p: call_gemini(p, "gemini-1.5-flash-latest")),
            ("gpt-4o", lambda p: call_openai(p, "gpt-4o")),
        ]
    else:
        # gpt-4o or unknown — just try OpenAI
        attempts = [
            ("gpt-4o", lambda p: call_openai(p, "gpt-4o")),
        ]

    last_error: str = "No models available"
    for model_label, fn in attempts:
        try:
            raw = fn(prompt)
            if raw and len(raw.strip()) >= 50:
                fallback = model_label != preferred_model
                reason = last_error if fallback else None
                if fallback:
                    audit_trail.append(AuditStep(
                        agent="ModelRouter",
                        action="fallback",
                        model_used=model_label,
                        fallback_occurred=True,
                        fallback_reason=f"Fell back from {preferred_model}: {last_error}",
                        output_summary=f"Fallback to {model_label} succeeded",
                    ))
                return raw, model_label, fallback, reason
            else:
                last_error = f"{model_label}: response too short"
        except Exception as e:
            last_error = f"{model_label}: {e}"
            audit_trail.append(AuditStep(
                agent="ModelRouter",
                action="model_error",
                model_used=model_label,
                fallback_occurred=True,
                fallback_reason=str(e),
                output_summary=f"{model_label} failed: {e}",
            ))

    # All models failed — return empty
    return "", "none", True, last_error
