import os
import sys

# --- SENTINEL API BOOTSTRAP ---
SENTINEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SentinelAPI"))
if SENTINEL_PATH not in sys.path:
    sys.path.insert(0, SENTINEL_PATH)
try:
    from bootstrap import activate_security
    activate_security()
except ImportError:
    print("⚠️ Warning: SentinelAPI module not found. Proceeding with caution.")

import json
import re
import time
import httpx
import logging
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CentralAI")

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

class AiGenerateRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.0-flash"
    response_mime_type: str = "text/plain"
    system_instruction: Optional[str] = None

def _safe_json_loads(text: str) -> dict:
    """Robust JSON parsing for LLM responses using contextual repair."""
    processed_text = text.strip()
    if processed_text.startswith("```"):
        start = processed_text.find("{")
        end = processed_text.rfind("}")
        if start != -1 and end != -1:
            processed_text = processed_text[start:end+1]
    
    # Simple attempts first
    try:
        return json.loads(processed_text)
    except Exception:
        pass

    # Stage 2: Contextual Repair of Internal Quotes
    repaired_text = ""
    in_string = False
    escape = False
    
    for i, char in enumerate(processed_text):
        if char == '\\' and not escape:
            escape = True
            repaired_text += char
            continue
            
        if char == '"' and not escape:
            is_structural = False
            prev_chars = processed_text[:i].strip()
            next_chars = processed_text[i+1:].strip()
            
            if not in_string:
                # Potential Value/Key opening
                if not prev_chars or prev_chars[-1] in '{[:,' :
                    is_structural = True
            else:
                # Potential Value/Key closing
                if not next_chars or next_chars[0] in '}\],:':
                    is_structural = True
            
            if is_structural:
                in_string = not in_string
                repaired_text += char
            else:
                repaired_text += '\\"' # Escape internal quote
        else:
            repaired_text += char
            
        escape = False

    # Stage 3: Common structural cleanup
    repaired_text = re.sub(r',\s*}', '}', repaired_text)
    repaired_text = re.sub(r',\s*\]', ']', repaired_text)
    
    try:
        return json.loads(repaired_text)
    except Exception as e:
        logger.error(f"❌ Failed to parse JSON even after contextual repair. Original: {processed_text[:100]}")
        raise ValueError(f"Invalid JSON response from model: {str(e)}")

@app.get("/health")
async def health():
    comfy_status = "offline"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client_http:
            resp = await client_http.get(f"{COMFYUI_URL}/queue")
            if resp.status_code == 200:
                comfy_status = "online"
    except Exception:
        pass

    gemini_status = "offline"
    try:
        # Check if client is initialized
        if GEMINI_API_KEY:
             for _ in client.models.list(config=types.ListModelsConfig(page_size=1)):
                 gemini_status = "online"
                 break
    except Exception as e:
        logger.error(f"❌ Gemini Health Check Failed: {e}")

    # Sentinel Check
    sentinel_status = "offline"
    try:
        from log_sanitizer import RedactedStream
        if isinstance(sys.stdout, RedactedStream):
            sentinel_status = "active"
    except: pass

    return {
        "status": "ok" if gemini_status == "online" else "error",
        "timestamp": time.time(),
        "sentinel": sentinel_status,
        "dependencies": {
            "comfyui": comfy_status,
            "gemini": gemini_status
        }
    }

@app.post("/v1/analyzer/draft")
async def draft_video(req: DraftRequest):
    logger.info(f"📥 Petición recibida: /v1/analyzer/draft | Video: {os.path.basename(req.video_path)}")
    if not os.path.exists(req.video_path):
        logger.warning(f"❌ Video no encontrado: {req.video_path}")
        raise HTTPException(status_code=404, detail=f"Video file not found: {req.video_path}")

    try:
        logger.info("📤 Subiendo video a Gemini...")
        video_file = client.files.upload(
            file=req.video_path,
            config=types.UploadFileConfig(
                display_name=os.path.basename(req.video_path), mime_type="video/mp4"
            ),
        )

        while video_file.state == "PROCESSING":
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)

        if video_file.state == "FAILED":
            logger.error(f"❌ Gemini falló al procesar el video: {video_file.name}")
            raise HTTPException(status_code=500, detail="Gemini failed to process the video file.")

        prompt = req.custom_prompt or "Analiza este video y crea un guion JSON con escenas (solo narración)."
        if req.global_comments:
            prompt = f"{prompt}\n\nCOMENTARIOS ADICIONALES DEL USUARIO:\n{req.global_comments}"
        
        prompt += f"\n\nTU TAREA ACTUAL: Genera el guion en FORMATO: {req.target_format.upper()}."
        if req.target_format.lower() == "reel" and req.context_script:
            prompt += f"\n\nBASA EL REEL EN ESTE GUION LARGO (CONTEXTO): \n{req.context_script}"

        logger.info("🧠 Consultando Gemini para el script...")
        start_time = datetime.now()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✨ Gemini respondió en {duration:.2f}s")
        
        try:
            return _safe_json_loads(response.text)
        except ValueError as ve:
            logger.error(f"💥 Error de parseo JSON: {ve}")
            return JSONResponse(status_code=500, content={"error": str(ve), "raw_response": response.text[:500]})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error en /analyzer/draft: {e}")
        traceback.print_exc()
        err_str = redact_sensitive(str(e))
        if "API_KEY_INVALID" in err_str or "expired" in err_str.lower():
            return JSONResponse(status_code=401, content={"error": "API_KEY_EXPIRED"})
        return JSONResponse(status_code=500, content={"error": err_str})

@app.post("/v1/analyzer/storyboard")
async def storyboard(req: StoryboardRequest):
    logger.info("📥 Petición recibida: /v1/analyzer/storyboard")
    try:
        prompt = "Decide visuales (image/animation) para este guion JSON."
        if req.global_comments:
            prompt = f"{prompt}\n\nCOMENTARIOS ADICIONALES DEL USUARIO:\n{req.global_comments}"

        full_prompt = f"{prompt}\n\nGuion actual:\n{json.dumps(req.script_data, indent=2, ensure_ascii=False)}"
        
        logger.info("🧠 Consultando Gemini para el storyboard...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _safe_json_loads(response.text)
    except Exception as e:
        logger.error(f"💥 Error en /analyzer/storyboard: {e}")
        return JSONResponse(status_code=500, content={"error": redact_sensitive(str(e))})

@app.post("/v1/analyzer/refine")
async def refine(req: RefineRequest):
    logger.info("📥 Petición recibida: /v1/analyzer/refine")
    try:
        prompt = f"""
        Refina el siguiente guion basado en este feedback: "{req.feedback}"
        Guion Actual:
        {json.dumps(req.current_script, indent=2)}
        """
        if req.global_comments:
            prompt += f'\n\nCONSIDERACIÓN GLOBAL ADICIONAL:\n{req.global_comments}'

        logger.info("🧠 Consultando Gemini para la refinación...")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _safe_json_loads(response.text)
    except Exception as e:
        logger.error(f"💥 Error en /analyzer/refine: {e}")
        return JSONResponse(status_code=500, content={"error": redact_sensitive(str(e))})

@app.post("/v1/ai/generate")
async def generate_content(req: AiGenerateRequest):
    """Generic AI generation endpoint for peripheral services."""
    logger.info(f"📥 Petición genérica de IA recibida.")
    try:
        config = types.GenerateContentConfig(
            response_mime_type=req.response_mime_type,
            system_instruction=req.system_instruction if req.system_instruction else None
        )
        
        start_time = datetime.now()
        response = client.models.generate_content(
            model=req.model,
            contents=req.prompt,
            config=config
        )
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✨ Gemini respondió en {duration:.2f}s")
        
        return {"text": response.text}
    except Exception as e:
        logger.error(f"💥 Error en /v1/ai/generate: {e}")
        return JSONResponse(status_code=500, content={"error": redact_sensitive(str(e))})

@app.api_route("/v1/comfyui/proxy/{path:path}", methods=["GET", "POST"])
async def comfyui_proxy(path: str, request: Request):
    """Proxy requests to local ComfyUI server."""
    logger.info(f"🔄 Proxying request to ComfyUI: {path}")
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
