import requests
import os

HUB_URL = "http://localhost:8080/v1"

# Using a known path from the history
video_path = "d:/Scripts/economika_reels/backend/temp_input.mp4"

if not os.path.exists(video_path):
    # Try another common one
    video_path = "temp_input.mp4"

print(f"Testing /v1/analyzer/draft with video: {video_path}")

payload = {
    "video_path": video_path,
    "target_format": "reel",
    "global_comments": "Test integration"
}

try:
    response = requests.post(f"{HUB_URL}/analyzer/draft", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
