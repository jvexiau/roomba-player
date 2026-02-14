from fastapi.testclient import TestClient

from roomba_player.app import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_home_page():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "roomba-player" in response.text
        assert "/player" in response.text


def test_player_page():
    with TestClient(app) as client:
        response = client.get("/player")
        assert response.status_code == 200
        assert "Keyboard AZERTY" in response.text
        assert "/static/player-main.js" in response.text
        assert "__CAMERA_ENABLED__" not in response.text


def test_camera_start_disabled_by_default():
    with TestClient(app) as client:
        response = client.post("/camera/start")
        assert response.status_code == 200
        assert response.json()["enabled"] is False
