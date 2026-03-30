import pytest
from fastapi.testclient import TestClient
from main import app
import os
from unittest.mock import MagicMock, patch

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@patch("main.client.files.upload")
@patch("main.client.models.generate_content")
def test_draft_video_success(mock_generate, mock_upload):
    # Mock upload
    mock_file = MagicMock()
    mock_file.state = "ACTIVE"
    mock_upload.return_value = mock_file
    
    # Mock generate_content
    mock_response = MagicMock()
    mock_response.text = '{"title": "Test Video", "scenes": []}'
    mock_generate.return_value = mock_response
    
    # Create a dummy file for the request
    dummy_path = "dummy_video.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
    
    try:
        response = client.post(
            "/v1/analyzer/draft",
            json={
                "video_path": os.path.abspath(dummy_path),
                "target_format": "reel"
            }
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Test Video"
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

def test_draft_video_not_found():
    response = client.post(
        "/v1/analyzer/draft",
        json={"video_path": "non_existent.mp4"}
    )
    assert response.status_code == 404

@patch("main.client.models.generate_content")
def test_storyboard_success(mock_generate):
    mock_response = MagicMock()
    mock_response.text = '{"scenes": [{"narration": "test", "image_prompt": "prompt"}]}'
    mock_generate.return_value = mock_response
    
    response = client.post(
        "/v1/analyzer/storyboard",
        json={
            "script_data": {"title": "Test", "scenes": []},
            "global_comments": "make it funny"
        }
    )
    assert response.status_code == 200
    assert "scenes" in response.json()

@patch("main.client.models.generate_content")
def test_refine_success(mock_generate):
    mock_response = MagicMock()
    mock_response.text = '{"title": "Refined", "scenes": []}'
    mock_generate.return_value = mock_response
    
    response = client.post(
        "/v1/analyzer/refine",
        json={
            "current_script": {"title": "Old"},
            "feedback": "more satire"
        }
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Refined"

def test_invalid_json_handling():
    from main import _safe_json_loads
    raw = "```json\n{\"a\": 1}\n```"
    assert _safe_json_loads(raw) == {"a": 1}
    
    malformed = '{"a": 1,}'
    assert _safe_json_loads(malformed) == {"a": 1}

@patch("main.client.files.upload")
def test_api_key_error_handling(mock_upload):
    mock_upload.side_effect = Exception("API_KEY_INVALID")
    
    dummy_path = "dummy_video_2.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
        
    try:
        response = client.post(
            "/v1/analyzer/draft",
            json={"video_path": os.path.abspath(dummy_path)}
        )
        assert response.status_code == 401
        assert "API Key" in response.json()["detail"]
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)
