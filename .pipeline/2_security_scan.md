# Pipeline 2: Security & Secret Scan
This pipeline ensures no API keys or secrets are leaked in the codebase or git history.

## Steps
1. **Local Secret Scan**: Scan for Gemini API key patterns (AIzaSy...) in the codebase.
   ```powershell
   Get-ChildItem -Recurse -Include *.py,*.env,*.md,*.txt | Select-String "AIzaSy"
   ```
2. **Git Diff Scan**: Scan the current diff before pushing.
   ```bash
   git diff --cached | Select-String "AIzaSy"
   ```
