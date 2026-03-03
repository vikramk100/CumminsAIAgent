"""
Train multi-class failure_label classifier: RF/XGBoost, SMOTE, StandardScaler.
Export .joblib pipeline and provide predict_failure(telemetry_data) with confidence.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Paths (script lives in scripts/, project root is parent of scripts)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ml_dataset.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "failure_classifier.joblib"
METADATA_PATH = MODEL_DIR / "failure_classifier_metadata.json"

NUMERIC_FEATURES = ["Process_Temperature", "Air_Temperature", "Rotational_Speed", "Torque", "Tool_Wear"]
CATEGORICAL_FEATURES = ["engineModel"]
TARGET = "failure_label"
RANDOM_STATE = 42
TEST_SIZE = 0.2


def _load_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from extract_ml_dataset import extract_flattened_dataset
    return extract_flattened_dataset(str(DATA_PATH))


def _build_pipeline(use_xgb: bool = False):
    from sklearn.preprocessing import StandardScaler as SS
    from sklearn.impute import SimpleImputer
    steps = [
        ("imputer", SimpleImputer(strategy="median", fill_value=0)),
        ("scaler", SS()),
        ("smote", SMOTE(random_state=RANDOM_STATE, k_neighbors=1)),
    ]
    if use_xgb:
        try:
            from xgboost import XGBClassifier
            steps.append(("clf", XGBClassifier(random_state=RANDOM_STATE, use_label_encoder=False, eval_metric="mlogloss")))
        except ImportError:
            steps.append(("clf", RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)))
    else:
        steps.append(("clf", RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)))
    return ImbPipeline(steps)


def train_and_evaluate(use_xgb: bool = False) -> dict[str, Any]:
    df = _load_data()
    if df.empty or TARGET not in df.columns:
        raise ValueError("No data or missing target column")
    for c in NUMERIC_FEATURES:
        if c not in df.columns:
            df[c] = 0
    df[NUMERIC_FEATURES] = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    if "engineModel" not in df.columns:
        df["engineModel"] = "X15"
    # Collapse rare failure_label to "Other" so SMOTE and stratify work
    label_counts = df[TARGET].astype(str).value_counts()
    rare = label_counts[label_counts < 5].index.tolist()
    if rare:
        df = df.copy()
        df.loc[df[TARGET].astype(str).isin(rare), TARGET] = "Other"
    le_engine = LabelEncoder()
    le_target = LabelEncoder()
    X = df[NUMERIC_FEATURES].copy()
    X["engineModel_enc"] = le_engine.fit_transform(df["engineModel"].astype(str))
    X = X.fillna(X.median(numeric_only=True))
    X = X.fillna(0)
    y = le_target.fit_transform(df[TARGET].astype(str))
    # Stratify only if every class has at least 2 samples
    stratify_arg = y
    import numpy as np
    _, counts = np.unique(y, return_counts=True)
    if counts.min() < 2:
        stratify_arg = None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=stratify_arg)
    pipeline = _build_pipeline(use_xgb=use_xgb)
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)
    report_str = classification_report(y_test, y_pred)
    print("Confusion Matrix:\n", cm)
    print("\nClassification Report:\n", report_str)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "pipeline": pipeline,
        "le_engine": le_engine,
        "le_target": le_target,
        "numeric_features": NUMERIC_FEATURES,
        "target_name": TARGET,
    }
    joblib.dump(artifact, MODEL_PATH)
    metadata = {
        "classes": le_target.classes_.tolist(),
        "engine_classes": le_engine.classes_.tolist(),
        "numeric_features": NUMERIC_FEATURES,
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Model saved to {MODEL_PATH}")
    return {"confusion_matrix": cm.tolist(), "classification_report": report, "metadata": metadata}


def predict_failure(telemetry_data: dict[str, Any]) -> tuple[str, float]:
    """
    Predict failure_label and confidence (max probability) for a single record.
    telemetry_data: Process_Temperature, Air_Temperature, Rotational_Speed, Torque, Tool_Wear, engineModel.
    Returns (failure_label, confidence).
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run training first.")
    artifact = joblib.load(MODEL_PATH)
    pipeline = artifact["pipeline"]
    le_engine = artifact["le_engine"]
    le_target = artifact["le_target"]
    numeric = artifact["numeric_features"]
    engine_model = str(telemetry_data.get("engineModel", "X15"))
    if engine_model not in le_engine.classes_:
        engine_model = le_engine.classes_[0]
    row = {k: float(telemetry_data.get(k, 0)) for k in numeric}
    row["engineModel_enc"] = le_engine.transform([engine_model])[0]
    X = pd.DataFrame([row])  # same column order as training
    proba = pipeline.predict_proba(X)[0]
    idx = int(np.argmax(proba))
    label = le_target.inverse_transform([idx])[0]
    confidence = float(proba[idx])
    return label, confidence


def failure_label_to_fault_code_and_severity(label: str) -> tuple[str, int]:
    """Parse failure_label (e.g. P0300_S3) -> (faultCode, severity 1-5). No failure -> ('', 0)."""
    if not label or label == "No_Failure":
        return "", 0
    m = re.match(r"^(.+)_S(\d)$", label)
    if m:
        return m.group(1), int(m.group(2))
    return label, 3


if __name__ == "__main__":
    import sys
    use_xgb = "xgb" in (sys.argv or [])
    train_and_evaluate(use_xgb=use_xgb)
