# [CORE] Fix 500 Internal Server Error in /v1/analyzer/draft

## Summary
The endpoint `/v1/analyzer/draft` is crashing with a 500 status code when called. A reproduction script exists at `tests/reproduce_500.py`.

## Acceptance Criteria
- [ ] Running `python tests/reproduce_500.py` devuelve un 200 OK.
- [ ] Cobertura del 100% sobre la lógica afectada en `main.py`.
- [ ] Registro en `memory_log.md` completado.

## Microservicios Afectados
- **CentralAIService** (CORE - **REQUIERE APROBACIN PREVIA**)

## Pasos
1. Ejecutar `python tests/reproduce_500.py` para confirmar el crash.
2. Analizar `main.py` y logs para encontrar la causa raíz.
3. Aplicar corrección en una nueva rama `fix/analyzer-500`.
4. Ejecutar suite completa de pytest.
5. Preparar Pull Request.
