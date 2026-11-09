from __future__ import annotations

from typing import Any

import pytest

from app.services.assessment_service import evaluate_deterministic
from app.services.deid_service import pseudonym_for_patient


@pytest.fixture
def hip_evaluation() -> dict[str, Any]:
    return evaluate_deterministic(
        "hip_fracture",
        {"age": 78, "asa": "III", "hemoglobin": 95, "fracture_type": "31C"},
    )


@pytest.fixture
def hip_context(hip_evaluation: dict[str, Any]) -> dict[str, Any]:
    from uuid import UUID

    patient_id = UUID("00bd171b-5f4f-4cc0-b448-0d7271ea1bf3")
    return {
        "assessment_id": "b18f4f33-b188-4000-811e-8dbc66653f3d",
        "patient_token": pseudonym_for_patient(patient_id),
        "age": 78,
        "gender": "MALE",
        "disease_id": "hip_fracture",
        "disease_name": "髋部骨折围手术期风险评估",
        "inputs": hip_evaluation["inputs"],
        "result": hip_evaluation["result"],
    }
