# Memory Log - CentralAIService

## [2026-04-11] Task 01: Fix 500 error in /v1/analyzer/draft

### Context
The endpoint `/v1/analyzer/draft` was failing with a 500 error, specifically when Gemini processing failed or when the JSON response from Gemini was malformed.

### Changes
- **main.py**:
    - Added explicit check for `video_file.state == "FAILED"` after upload.
    - Improved `_safe_json_loads` with better regex cleaning and structured error reporting.
    - Refined exception handling to correctly pass `HTTPException` through to FastAPI.
    - Added `try/except` around parsing to return a 500 with the raw response if parsing fails, instead of a generic crash.
- **tests/test_main.py**:
    - Fixed existing test failures.
    - Added 4 new test cases covering success with context, failed video state, and JSON parsing errors.
    - Increased coverage of core logic to >80% (remaining missing lines are mostly in the ComfyUI proxy which was not modified).

### Results
- `pytest` confirms success cases and failure handling.
- `reproduce_500.py` now returns 200 OK (or handled 500/401 instead of generic crash).
- 100% coverage of the modified paths in `/v1/analyzer/draft`.

---
