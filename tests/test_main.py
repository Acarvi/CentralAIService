import pytest
import os
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "error"]
    assert "sentinel" in data

@pytest.mark.asyncio
@patch("main.client.files.upload")
@patch("main.client.models.generate_content")
async def test_draft_video_success(mock_generate, mock_upload):
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
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

@pytest.mark.asyncio
async def test_draft_video_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/analyzer/draft",
            json={"video_path": "non_existent.mp4"}
        )
    assert response.status_code == 404

@pytest.mark.asyncio
@patch("main.client.models.generate_content")
async def test_storyboard_success(mock_generate):
    mock_response = MagicMock()
    mock_response.text = '{"scenes": [{"narration": "test", "image_prompt": "prompt"}]}'
    mock_generate.return_value = mock_response
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/v1/analyzer/storyboard",
            json={
                "script_data": {"title": "Test", "scenes": []},
                "global_comments": "make it funny"
            }
        )
    assert response.status_code == 200
    assert "scenes" in response.json()

@pytest.mark.asyncio
@patch("main.client.models.generate_content")
async def test_refine_success(mock_generate):
    mock_response = MagicMock()
    mock_response.text = '{"title": "Refined", "scenes": []}'
    mock_generate.return_value = mock_response
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
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

@pytest.mark.asyncio
@patch("main.client.files.upload")
async def test_api_key_error_handling(mock_upload):
    mock_upload.side_effect = Exception("API_KEY_INVALID")
    
    dummy_path = "dummy_video_2.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
        
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/v1/analyzer/draft",
                json={"video_path": os.path.abspath(dummy_path)}
            )
        assert response.status_code == 401
        assert response.json()["error"] == "API_KEY_EXPIRED"
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

@pytest.mark.asyncio
@patch("main.client.files.upload")
async def test_draft_video_general_500_redacted(mock_upload):
    """Verify that general 500 errors redact sensitive info."""
    key = "AIzaSyTestKey123"
    # we need to mock GEMINI_API_KEY in main.py
    with patch("main.GEMINI_API_KEY", key):
        # Simulate an error that might contain a key
        mock_upload.side_effect = Exception(f"Error with key {key}")
        
        dummy_path = "dummy_video_redact.mp4"
        with open(dummy_path, "w") as f:
            f.write("dummy")
            
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/v1/analyzer/draft",
                    json={"video_path": os.path.abspath(dummy_path)}
                )
            assert response.status_code == 500
            assert key not in response.json()["error"]
            assert "[REDACTED_GEMINI_KEY]" in response.json()["error"]
        finally:
            if os.path.exists(dummy_path):
                os.remove(dummy_path)

@pytest.mark.asyncio
async def test_api_generate_success():
    """Verify generic AI generation endpoint."""
    with patch("main.client.models.generate_content") as mock_gen:
        mock_resp = MagicMock()
        mock_resp.text = "Generated text"
        mock_gen.return_value = mock_resp
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/v1/ai/generate",
                json={"prompt": "test prompt"}
            )
        assert response.status_code == 200
        assert response.json()["text"] == "Generated text"

@pytest.mark.asyncio
@patch("main.client.files.upload")
async def test_draft_video_failed_state(mock_upload):
    mock_file = MagicMock()
    mock_file.state = "FAILED"
    mock_file.name = "failed_video"
    mock_upload.return_value = mock_file
    
    dummy_path = "dummy_video_fail.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
        
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/v1/analyzer/draft",
                json={"video_path": os.path.abspath(dummy_path)}
            )
        assert response.status_code == 500
        assert "failed to process" in response.json()["detail"]
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

@pytest.mark.asyncio
@patch("main.client.files.upload")
@patch("main.client.models.generate_content")
async def test_draft_video_with_context(mock_generate, mock_upload):
    mock_file = MagicMock()
    mock_file.state = "ACTIVE"
    mock_upload.return_value = mock_file
    
    mock_response = MagicMock()
    mock_response.text = '{"scenes": []}'
    mock_generate.return_value = mock_response
    
    dummy_path = "dummy_video_context.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
        
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/v1/analyzer/draft",
                json={
                    "video_path": os.path.abspath(dummy_path),
                    "global_comments": "Use slow pace",
                    "context_script": "This is a long script context"
                }
            )
        assert response.status_code == 200
        # Verify prompt construction implicitly by the fact it didn't crash
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

@pytest.mark.asyncio
@patch("main.client.files.upload")
@patch("main.client.models.generate_content")
async def test_draft_video_parsing_error(mock_generate, mock_upload):
    mock_file = MagicMock()
    mock_file.state = "ACTIVE"
    mock_upload.return_value = mock_file
    
    mock_response = MagicMock()
    mock_response.text = 'Definitely not JSON'
    mock_generate.return_value = mock_response
    
    dummy_path = "dummy_video_parse_fail.mp4"
    with open(dummy_path, "w") as f:
        f.write("dummy")
        
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/v1/analyzer/draft",
                json={"video_path": os.path.abspath(dummy_path)}
            )
        assert response.status_code == 500
        assert "Invalid JSON response" in response.json()["error"]
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

def test_safe_json_loads_advanced():
    from main import _safe_json_loads
    import pytest
    
    # Test with comma at end of list
    assert _safe_json_loads('[1, 2, ]') == [1, 2]
    # Test with comma at end of object
    assert _safe_json_loads('{"a": 1, }') == {"a": 1}
    # Test multiple objects
    # Note: _safe_json_loads handles re.sub(r'}\s*{', '}, {', ...) but returns json.loads(current_text)
    # If it's something like "{} {}", it becomes "{}, {}" which is invalid JSON as a whole unless wrapped in []
    # Actually current implementation does json.loads(current_text) which would fail for multiple top-level objects
    # But let's test what it currently does.
    
    # Test escape of quotes
    assert _safe_json_loads('{"text": "He "quoted" this"}') == {"text": 'He "quoted" this'}
    assert _safe_json_loads('{"text": "End."}') == {"text": "End."}
    
    # Test failure
    with pytest.raises(ValueError, match="Invalid JSON response"):
        _safe_json_loads('{"a": 1') # Missing closing brace
