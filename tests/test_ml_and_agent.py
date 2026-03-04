import os
from unittest import mock

import numpy as np
import pytest

os.environ.setdefault("MONGODB_DB", "sap_bnac")


def test_predict_failure_returns_label_and_confidence(monkeypatch):
    from scripts import train_failure_classifier as tfc

    dummy_pipeline = mock.Mock()

    def fake_predict_proba(X):
        return np.array([[0.1, 0.9]])

    dummy_pipeline.predict_proba.side_effect = fake_predict_proba

    artifact = {
        "pipeline": dummy_pipeline,
        "le_engine": tfc.LabelEncoder().fit(["X15"]),
        "le_target": tfc.LabelEncoder().fit(["No_Failure", "P0300_S3"]),
        "numeric_features": tfc.NUMERIC_FEATURES,
    }

    with mock.patch("scripts.train_failure_classifier.joblib.load", return_value=artifact), mock.patch(
        "scripts.train_failure_classifier.MODEL_PATH", tfc.MODEL_PATH
    ):
        telemetry = {
            "Process_Temperature": 300,
            "Air_Temperature": 290,
            "Rotational_Speed": 1500,
            "Torque": 50,
            "Tool_Wear": 120,
            "engineModel": "X15",
        }
        label, confidence = tfc.predict_failure(telemetry)
        assert isinstance(label, str)
        assert 0.0 <= confidence <= 1.0


def test_agent_tools_query_manuals_extracts_tools(monkeypatch):
    from api import agent_tools
    from api.dispatch_agent import extract_tools_from_text

    fake_docs = [
        {
            "content": "Use a torque wrench and 10mm socket to tighten the bolts. Verify with multimeter.",
            "section": "Maintenance Procedures",
            "pageNumber": 42,
            "engineModel": "X15",
        }
    ]

    class FakeCursor(list):
        def limit(self, n):
            return self[:n]

    fake_db = {
        "manuals": mock.Mock(
            find=mock.Mock(return_value=FakeCursor(fake_docs)),
        )
    }

    class FakeClient:
        def __getitem__(self, name):
            # first index returns DB, second returns collection
            return fake_db

    monkeypatch.setattr(agent_tools, "_client", FakeClient())

    results = agent_tools.query_manuals("P0300", engine_model="X15")
    assert results
    tools = extract_tools_from_text(results[0]["content"])
    assert any(t in tools for t in ["Torque Wrench", "Multimeter", "10mm Socket"])


def test_mongo_connection_reused(monkeypatch):
    from api import agent_tools

    monkeypatch.setenv("MONGODB_PASSWORD", "test")  # so _get_db() passes placeholder check
    # Reset module client so the test creates a new one via patched MongoClient
    monkeypatch.setattr(agent_tools, "_client", None)

    fake_db = mock.Mock()
    fake_client = mock.MagicMock()
    fake_client.__getitem__.return_value = fake_db

    with mock.patch("api.agent_tools.pymongo.MongoClient", return_value=fake_client):
        db1 = agent_tools._get_db()
        db2 = agent_tools._get_db()
        assert db1 is db2
        assert agent_tools._client is fake_client

