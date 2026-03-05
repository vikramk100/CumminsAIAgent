"""
Tests for Work Order and Confirmations CRUD API (api.v1.router).
Use real MongoDB: tests run against the database configured in .env (or MONGODB_URI),
with database name from MONGODB_DB_TEST or default sap_bnac_test.
Collections workorders, confirmations, operations are cleared before each test.
"""

import pytest
from fastapi.testclient import TestClient

from api.mcp_server import _get_db
from api.main import app

WORK_ORDERS_COLLECTION = "workorders"
CONFIRMATIONS_COLLECTION = "confirmations"
OPERATIONS_COLLECTION = "operations"


@pytest.fixture(autouse=True)
def clear_crud_collections():
    """Clear workorders, confirmations, operations before each test so tests are isolated.
    Resets agent_tools._client so we use a real MongoDB (previous tests may have mocked it).
    """
    from api import agent_tools
    agent_tools._client = None  # force real connection (e.g. after test_ml_and_agent mocks)
    db = _get_db()
    db[WORK_ORDERS_COLLECTION].delete_many({})
    db[CONFIRMATIONS_COLLECTION].delete_many({})
    db[OPERATIONS_COLLECTION].delete_many({})
    yield
    # Optional: leave data after test for debugging, or uncomment to clean after:
    # db[WORK_ORDERS_COLLECTION].delete_many({})
    # db[CONFIRMATIONS_COLLECTION].delete_many({})
    # db[OPERATIONS_COLLECTION].delete_many({})


@pytest.fixture
def client():
    """FastAPI test client; uses real MongoDB via _get_db()."""
    return TestClient(app)


# ---------- Work Order CRUD tests ----------


def test_create_workorder(client):
    r = client.post(
        "/api/v1/workorders",
        json={"equipmentId": "M-001", "status": "Created", "priority": 2, "actualWork": 0.0},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["equipmentId"] == "M-001"
    assert data["status"] == "Created"
    assert data["priority"] == 2
    assert "orderId" in data
    assert data["orderId"].startswith("WO-")


def test_create_workorder_defaults(client):
    r = client.post("/api/v1/workorders", json={"equipmentId": "M-002"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "Created"
    assert data["priority"] == 2
    assert data["actualWork"] == 0.0


def test_get_workorder(client):
    client.post("/api/v1/workorders", json={"equipmentId": "M-001"})
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-002"}).json()["orderId"]
    r = client.get(f"/api/v1/workorders/{order_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["orderId"] == order_id
    assert data["equipmentId"] == "M-002"
    assert "confirmations" in data
    assert data["confirmations"] == []


def test_get_workorder_not_found(client):
    r = client.get("/api/v1/workorders/WO-99999")
    assert r.status_code == 404


def test_update_workorder(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.put(
        f"/api/v1/workorders/{order_id}",
        json={"status": "In Progress", "actualWork": 2.5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "In Progress"
    assert data["actualWork"] == 2.5
    assert data["equipmentId"] == "M-001"


def test_update_workorder_not_found(client):
    r = client.put("/api/v1/workorders/WO-99999", json={"status": "Completed"})
    assert r.status_code == 404


def test_delete_workorder(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.delete(f"/api/v1/workorders/{order_id}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r2 = client.get(f"/api/v1/workorders/{order_id}")
    assert r2.status_code == 404


def test_delete_workorder_not_found(client):
    r = client.delete("/api/v1/workorders/WO-99999")
    assert r.status_code == 404


# ---------- Confirmations CRUD tests ----------


def test_create_confirmation(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "Task completed.", "status": "Submitted", "actualWork": 1.5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["orderId"] == order_id
    assert data["confirmationText"] == "Task completed."
    assert data["actualWork"] == 1.5
    assert "confirmationId" in data
    assert data["confirmationId"].startswith("CF-")


def test_list_confirmations(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "First confirmation"},
    )
    client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "Second confirmation"},
    )
    r = client.get(f"/api/v1/workorders/{order_id}/confirmations")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) == 2


def test_list_confirmations_workorder_not_found(client):
    r = client.get("/api/v1/workorders/WO-99999/confirmations")
    assert r.status_code == 404


def test_get_confirmation(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    created = client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "Done."},
    ).json()
    cid = created["confirmationId"]
    r = client.get(f"/api/v1/workorders/{order_id}/confirmations/{cid}")
    assert r.status_code == 200
    assert r.json()["confirmationText"] == "Done."


def test_get_confirmation_not_found(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.get(f"/api/v1/workorders/{order_id}/confirmations/CF-nonexistent")
    assert r.status_code == 404


def test_update_confirmation(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    created = client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "Original"},
    ).json()
    cid = created["confirmationId"]
    r = client.put(
        f"/api/v1/workorders/{order_id}/confirmations/{cid}",
        json={"confirmationText": "Updated text", "status": "Approved"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["confirmationText"] == "Updated text"
    assert data["status"] == "Approved"


def test_delete_confirmation(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    created = client.post(
        f"/api/v1/workorders/{order_id}/confirmations",
        json={"confirmationText": "To delete"},
    ).json()
    cid = created["confirmationId"]
    r = client.delete(f"/api/v1/workorders/{order_id}/confirmations/{cid}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r2 = client.get(f"/api/v1/workorders/{order_id}/confirmations")
    assert len(r2.json()["results"]) == 0


def test_delete_confirmation_not_found(client):
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.delete(f"/api/v1/workorders/{order_id}/confirmations/CF-nonexistent")
    assert r.status_code == 404


def test_create_confirmation_for_nonexistent_workorder(client):
    r = client.post(
        "/api/v1/workorders/WO-99999/confirmations",
        json={"confirmationText": "Test"},
    )
    assert r.status_code == 404


def test_chat_endpoint_registered(client):
    """Ensure POST /api/v1/chat is registered and returns 200 for an existing work order."""
    order_id = client.post("/api/v1/workorders", json={"equipmentId": "M-001"}).json()["orderId"]
    r = client.post(
        "/api/v1/chat",
        json={"orderId": order_id, "question": "What is the status?"},
        headers={"Accept": "application/json"},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}. Route may not be registered."
    data = r.json()
    assert isinstance(data, dict)
