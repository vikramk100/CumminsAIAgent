import json

import requests


def main() -> None:
    base = "http://localhost:8000"
    endpoints = [
        ("GET", f"{base}/api/predictions", {}),
        ("POST", f"{base}/api/predict", {"json": {
            "Process_Temperature": 100,
            "Air_Temperature": 20,
            "Rotational_Speed": 1500,
            "Torque": 25,
            "Tool_Wear": 10,
            "engineModel": "X15",
        }}),
        ("POST", f"{base}/api/triggerWorkOrder", {"json": {
            "equipmentId": "EQ-1",
            "predictedFailure": "Test Failure",
            "faultCode": "F001",
            "suggestedOperation": "Test operation",
        }}),
        ("GET", f"{base}/api/v1/dispatch-brief/WO-10000", {}),
        ("POST", f"{base}/api/v1/audit-trail", {"json": {
            "orderId": "WO-10000",
            "equipmentId": "EQ-1",
            "toolName": "wrench",
            "checked": True,
            "userId": "tester",
            "source": "probe",
        }}),
    ]

    for method, url, kwargs in endpoints:
        print(f"\n=== {method} {url} ===")
        try:
            resp = requests.request(method, url, timeout=10, **kwargs)
            print("Status:", resp.status_code)
            try:
                body = resp.json()
                print("JSON:", json.dumps(body, indent=2)[:800])
            except Exception:
                print("Body (truncated):", resp.text[:800])
        except Exception as exc:
            print("ERROR:", repr(exc))


if __name__ == "__main__":
    main()

