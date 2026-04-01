import os
import json
import time
import httpx
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CentralAIService", version="1.0.0")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"timeout": 120000},
)

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")

def redact_sensitive(text: str) -> str:
    """Robust redaction of API keys and secrets."""
    if not text:
        return text
    # Redact Gemini Key if present
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 5:
        text = text.replace(GEMINI_API_KEY, "[REDACTED_GEMINI_KEY]")
    return text

class DraftRequest(BaseModel):
    video_path: str
    global_comments: str = ""
    target_format: str = "reel"
    context_script: str = ""
    custom_prompt: Optional[str] = None

class StoryboardRequest(BaseModel):
    script_data: Dict[str, Any]
    global_comments: str = ""

class RefineRequest(BaseModel):
    current_script: Dict[str, Any]
    feedback: str
    global_comments: str = ""

def _safe_json_loads(text: str) -> dict:
    """Robust JSON parsing for LLM responses."""
    import re
    processed_text = text.strip()
    if processed_text.startswith("```"):
        start = processed_text.find("{")
        end = processed_text.rfind("}")
        if start != -1 and end != -1:
            processed_text = processed_text[start:end+1]
    try:
        return json.loads(processed_text)
    except Exception:
        pass

    current_text = processed_text
    current_text = re.sub(r',\s*}', '}', current_text)
    current_text = re.sub(r',\s*\]', ']', current_text)
    current_text = re.sub(r'}\s*{', '}, {', current_text)
    current_text = re.sub(r'\]\s*{', '], {', current_text)
    
    try:
        return json.loads(current_text)
    except Exception:
        pass
        
    letters = "a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9"
    processed_text = re.sub(rf'(?<=[{letters}\s！？。，])"(?=[{letters}\s！？。，])', r'\"', processed_text)
    processed_text = re.sub(rf'(?<=[{letters}\s])"(?=[.!?])', r'\"', processed_text)

    try:
        return json.loads(processed_text)
    except Exception:
        pass

    try:
        start = processed_text.find("{")
        end = processed_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(processed_text[start:end+1])
    except Exception:
        pass
        
    return json.loads(processed_text)

@app.get("/health")
async def health():
    comfy_status = "offline"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{COMFYUI_URL}/queue")
            if resp.status_code == 200:
                comfy_status = "online"
    except Exception:
        pass

    return {
        "status": "ok",
        "timestamp": time.time(),
        "dependencies": {
            "comfyui": comfy_status
        }
    }

@app.post("/v1/analyzer/draft")
async def draft_video(req: DraftRequest):
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {req.video_path}")

    try:
        video_file = client.files.upload(
            file=req.video_path,
            config=types.UploadFileConfig(
                display_name=os.path.basename(req.video_path), mime_type="video/mp4"
            ),
        )

        while video_file.state == "PROCESSING":
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)

        prompt = req.custom_prompt or "Analiza este video y crea un guion JSON con escenas (solo narración)."
        if req.global_comments:
            prompt = f"{prompt}\n\nCOMENTARIOS ADICIONALES DEL USUARIO:\n{req.global_comments}"
        
        prompt += f"\n\nTU TAREA ACTUAL: Genera el guion en FORMATO: {req.target_format.upper()}."
        if req.target_format.lower() == "reel" and req.context_script:
            prompt += f"\n\nBASA EL REEL EN ESTE GUION LARGO (CONTEXTO): \n{req.context_script}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _safe_json_loads(response.text)
    except Exception as e:
        err_str = redact_sensitive(str(e))
        if "API_KEY_INVALID" in err_str or "expired" in err_str.lower():
            return JSONResponse(status_code=401, content={"error": "API_KEY_EXPIRED"})
        return JSONResponse(status_code=500, content={"error": err_str})

@app.post("/v1/analyzer/storyboard")
async def storyboard(req: StoryboardRequest):
    try:
        prompt = "Decide visuales (image/animation) para este guion JSON."
        if req.global_comments:
            prompt = f"{prompt}\n\nCOMENTARIOS ADICIONALES DEL USUARIO:\n{req.global_comments}"

        full_prompt = f"{prompt}\n\nGuion actual:\n{json.dumps(req.script_data, indent=2, ensure_ascii=False)}"
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _safe_json_loads(response.text)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": redact_sensitive(str(e))})

@app.post("/v1/analyzer/refine")
async def refine(req: RefineRequest):
    try:
        prompt = f"""
        Refina el siguiente guion basado en este feedback: "{req.feedback}"
        Guion Actual:
        {json.dumps(req.current_script, indent=2)}
        """
        if req.global_comments:
            prompt += f'\n\nCONSIDERACIÓN GLOBAL ADICIONAL:\n{req.global_comments}'

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _safe_json_loads(response.text)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": redact_sensitive(str(e))})

@app.api_route("/v1/comfyui/proxy/{path:path}", methods=["GET", "POST"])
async def comfyui_proxy(path: str, request: Request):
    """Proxy requests to local ComfyUI server."""
    url = f"{COMFYUI_URL}/{path}"
    
    # Forward query parameters
    params = dict(request.query_params)
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            if request.method == "GET":
                resp = await client.get(url, params=params)
            else:
                body = await request.body()
                headers = dict(request.headers)
                # Remove host to avoid conflicts
                headers.pop("host", None)
                resp = await client.post(url, content=body, params=params, headers=headers)
                
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.content
            )
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": f"ComfyUI Proxy Error: {redact_sensitive(str(e))}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
