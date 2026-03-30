# CentralAIService

Servicio centralizado de Inteligencia Artificial para el ecosistema Economika.

## Características
- **FastAPI**: API de alto rendimiento para procesamiento asíncrono.
- **Gemini 2.0 Flash**: Integración con el último modelo de Google para análisis de video y generación de guiones.
- **Robustez**: Manejo avanzado de errores de JSON y recuperación de truncamiento.
- **Seguridad**: Centralización de API Keys en un único punto.

## API Endpoints

### `POST /v1/analyzer/draft`
Analiza un video y genera un borrador de guion.
- **Body**: `{"video_path": "...", "target_format": "reel/youtube"}`

### `POST /v1/analyzer/storyboard`
Genera visuales y beats para un guion.
- **Body**: `{"script_data": {...}}`

### `POST /v1/analyzer/refine`
Refina un guion basado en feedback.
- **Body**: `{"current_script": {...}, "feedback": "..."}`

### `GET /health`
Estado del servicio.

## Instalación
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```
