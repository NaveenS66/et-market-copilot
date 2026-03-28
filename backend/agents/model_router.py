"""
ModelRouter — routes LLM tasks by complexity to minimise cost.
"""
from __future__ import annotations

from backend.models import AuditStep


class ModelRouter:
    ROUTING_TABLE: dict[str, tuple[str, float]] = {
        "sector_tagging":        ("gemini-flash", 0.0001),
        "signal_type_detection": ("gemini-flash", 0.0001),
        "promoter_detection":    ("gemini-flash", 0.0002),
        "standard_alert":        ("gemini-pro",   0.002),
        "conflicted_alert":      ("gpt-4o",       0.02),
    }
    GPT4O_COST: float = 0.02  # baseline cost if GPT-4o used for everything

    def route(self, task_type: str) -> tuple[str, float]:
        """Return (model_name, cost_saved_vs_gpt4o)."""
        model, cost = self.ROUTING_TABLE.get(task_type, ("gpt-4o", 0.02))
        cost_saved = self.GPT4O_COST - cost
        return model, cost_saved

    def log_routing(self, task_type: str, audit_trail: list[AuditStep]) -> str:
        """Log routing decision to audit trail and return model name."""
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
