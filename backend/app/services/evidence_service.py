from __future__ import annotations

from typing import Any


def build_rule_evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose only evidence already present in the deterministic rule result.

    This deliberately does not query an external guideline corpus yet. Every id
    returned here is safe for the draft layer to cite; nothing is invented.
    """

    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    severity_raw = result.get("severity")
    severity: dict[str, Any] = severity_raw if isinstance(severity_raw, dict) else {}
    basis_raw = severity.get("basis")
    for basis in basis_raw if isinstance(basis_raw, list) else []:
        if not isinstance(basis, dict):
            continue
        item_id = f"basis:{basis.get('id', '')}"
        if not basis.get("id") or item_id in seen:
            continue
        seen.add(item_id)
        evidence.append(
            {
                "id": item_id,
                "kind": "basis",
                "label": str(basis.get("label", "")),
                "value": str(basis.get("value", "")),
                "source": str(basis.get("source", "")),
            }
        )

    recommendations = result.get("recommendations")
    if isinstance(recommendations, list):
        for recommendation in recommendations:
            if not isinstance(recommendation, dict):
                continue
            citations = recommendation.get("citations")
            if not isinstance(citations, list):
                continue
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                citation_id = str(citation.get("id", "")).strip()
                if not citation_id or citation_id in seen:
                    continue
                seen.add(citation_id)
                evidence.append(
                    {
                        "id": citation_id,
                        "kind": str(citation.get("type", "rule")),
                        "label": str(citation.get("label", "")),
                        "value": "",
                        "source": str(recommendation.get("text", "")),
                    }
                )

    return evidence
