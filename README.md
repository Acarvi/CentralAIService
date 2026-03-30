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

## Seguridad y Errores
- **Protección de Secretos**: Todas las claves se manejan vía `.env` (excluido de Git).
- **Sanitización**: Los mensajes de error de la API de Google son procesados para eliminar cualquier rastro de la `GEMINI_API_KEY` antes de ser devueltos al cliente o registrados en logs.
- **Validación de JSON**: Incluye lógica de recuperación para respuestas de LLM malformadas o truncadas.

## Instalación
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```
