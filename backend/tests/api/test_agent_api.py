from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

DOCTOR = {"username": "doctor", "password": "MedRisk2026!"}
ADMIN = {"username": "admin", "password": "Admin2026!"}
HIP_INPUTS = {"age": 82, "asa": "III", "hemoglobin": 98.0, "fracture_type": "31C"}


def _login(client: TestClient, credentials: dict[str, str]) -> None:
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200, response.text


def _create_assessment(client: TestClient) -> str:
    patients = client.get("/api/v1/patients", params={"size": 1})
    assert patients.status_code == 200, patients.text
    patient_id = patients.json()["records"][0]["id"]
    created = client.post(
        "/api/v1/assessments",
        json={"patient_id": patient_id, "disease_id": "hip_fracture", "inputs": HIP_INPUTS},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def _wait_for_run(client: TestClient, run_id: str, expected: str = "WAITING_HUMAN") -> dict:
    for _ in range(50):
        response = client.get(f"/api/v1/agent/runs/{run_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] == expected:
            return payload
        if payload["status"] in {"FAILED", "DONE"}:
            raise AssertionError(f"run ended as {payload['status']}: {payload.get('error')}")
        time.sleep(0.1)
    raise AssertionError(f"run {run_id} did not reach {expected}")


def test_agent_write_requires_doctor_and_approval_completes() -> None:
    with TestClient(app) as client:
        _login(client, DOCTOR)
        assessment_id = _create_assessment(client)

        created = client.post("/api/v1/agent/runs", json={"assessment_id": assessment_id})
        assert created.status_code == 202, created.text
        run = created.json()
        assert run["status"] == "RUNNING"
        assert run["disease_id"] == "hip_fracture"
        run_id = run["id"]

        waiting = _wait_for_run(client, run_id)
        assert waiting["verification"]["schema_passed"] is True
        assert waiting["verification"]["numeric_passed"] is True
        assert waiting["verification"]["citation_passed"] is True
        assert waiting["draft"]["disclaimer"] == "演示模型，未经校准"

        run_input = waiting.get("input")
        steps_text = str(waiting.get("steps"))
        assert "MR2026" not in steps_text
        assert "PATIENT-" in steps_text or "PATIENT-" in str(run_input)

        client.post("/api/v1/auth/logout")
        _login(client, ADMIN)
        assert client.post("/api/v1/agent/runs", json={"assessment_id": assessment_id}).status_code == 403
        assert (
            client.post(f"/api/v1/agent/runs/{run_id}/approve", json={"decision": "APPROVE"}).status_code
            == 403
        )
        assert client.get(f"/api/v1/agent/runs/{run_id}").status_code == 200

        client.post("/api/v1/auth/logout")
        _login(client, DOCTOR)
        approved = client.post(
            f"/api/v1/agent/runs/{run_id}/approve",
            json={"decision": "APPROVE", "note": "复核通过"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "DONE"
        assert approved.json()["decision"] == "APPROVE"

        feedback = client.post(f"/api/v1/agent/runs/{run_id}/feedback", json={"rating": 5})
        assert feedback.status_code == 200, feedback.text


def test_agent_a_run_cannot_be_approved_twice() -> None:
    with TestClient(app) as client:
        _login(client, DOCTOR)
        assessment_id = _create_assessment(client)
        created = client.post("/api/v1/agent/runs", json={"assessment_id": assessment_id})
        assert created.status_code == 202, created.text
        run_id = created.json()["id"]
        _wait_for_run(client, run_id)

        draft = _wait_for_run(client, run_id)["draft"]
        first = client.post(
            f"/api/v1/agent/runs/{run_id}/approve",
            json={
                "decision": "REJECT",
                "edited_draft": {**draft, "summary": "拒绝时编辑内容不参与校验 99%"},
            },
        )
        assert first.status_code == 200, first.text
        second = client.post(f"/api/v1/agent/runs/{run_id}/approve", json={"decision": "APPROVE"})
        assert second.status_code == 409
        assert second.json()["code"] == "AGENT_NOT_WAITING"


def test_edited_draft_is_revalidated_before_approval() -> None:
    with TestClient(app) as client:
        _login(client, DOCTOR)
        assessment_id = _create_assessment(client)
        created = client.post("/api/v1/agent/runs", json={"assessment_id": assessment_id})
        assert created.status_code == 202, created.text
        run_id = created.json()["id"]
        waiting = _wait_for_run(client, run_id)
        draft = waiting["draft"]

        tampered = {**draft, "summary": "本例风险约为 99%，建议立即手术。"}
        rejected = client.post(
            f"/api/v1/agent/runs/{run_id}/approve",
            json={"decision": "APPROVE", "edited_draft": tampered},
        )
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "VALIDATION_ERROR"

        safe = {**draft, "summary": f"{draft['summary']} 已由医生核对。"}
        approved = client.post(
            f"/api/v1/agent/runs/{run_id}/approve",
            json={"decision": "APPROVE", "edited_draft": safe},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["draft"]["summary"].endswith("已由医生核对。")


def test_live_mode_requires_api_key_before_creating_a_run(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_mock", False)
    monkeypatch.setattr(settings, "llm_api_key", "")

    with TestClient(app) as client:
        _login(client, DOCTOR)
        assessment_id = _create_assessment(client)
        response = client.post("/api/v1/agent/runs", json={"assessment_id": assessment_id})
        assert response.status_code == 422
        assert response.json()["data"] == {"field": "llm_api_key"}
