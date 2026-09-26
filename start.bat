@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install dependencies first: uv sync --extra test
  exit /b 1
)
".venv\Scripts\python.exe" -m baynumber.cli serve
