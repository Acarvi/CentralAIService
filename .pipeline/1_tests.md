# Pipeline 1: Functional Tests
This pipeline verifies the health and functionality of the CentralAIService.

## Steps
1. **Health Check**: Verify the service is online.
   ```bash
   curl http://localhost:8080/health
   ```
2. **Endpoint Verification**: Test the draft analyzer.
   ```bash
   python tests/reproduce_500.py
   ```
