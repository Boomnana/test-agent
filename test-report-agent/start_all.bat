@echo off
setlocal
set "ROOT=%~dp0"
start "Backend" cmd /c "cd /d %ROOT%backend && uvicorn app.main:app --reload"
start "Frontend" cmd /c "cd /d %ROOT%frontend && npm install && npm run dev"
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
start "" "http://127.0.0.1:8000/api/v1/docs"
start "" "http://localhost:5173/"
exit /b 0
