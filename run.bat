@echo off
title NeuroChat - AI with Memory
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║         🧠 NeuroChat v1.0             ║
echo  ║   Offline AI with Persistent Memory   ║
echo  ╚═══════════════════════════════════════╝
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama is not running!
    echo Please start Ollama and pull a model:
    echo   ollama pull llama3.2
    echo.
)

:: Install dependencies if needed
if not exist "backend\venv" (
    echo [SETUP] Creating virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt
    cd ..
) else (
    call backend\venv\Scripts\activate.bat
)

:: Create directories
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "data\vectors" mkdir data\vectors
if not exist "frontend\assets\icons" mkdir frontend\assets\icons

:: Start the server
echo.
echo [START] Starting NeuroChat server on http://localhost:8000
echo [INFO]  Press Ctrl+C to stop
echo.
cd backend
python main.py
