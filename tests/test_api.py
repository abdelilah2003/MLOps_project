from fastapi.testclient import TestClient
import prompt_firewall.api as api


client = TestClient(api.app)


def test_health():
    response = client.get("/health")
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_path" in body
    assert "model_exists" in body


def test_check_without_model_returns_503():
    response = client.post("/check", json={"prompt": "hello"})
    response = client.post("/check", json={"prompt": "hello"})
    assert response.status_code == 503
