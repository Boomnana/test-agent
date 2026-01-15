# Test Report Agent

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**:
   - Check `.env` file for LLM keys and Database settings.
   - The system is pre-configured with the provided GLM-4-Air key.

3. **Run Demo (No DB/Redis required)**:
   This script creates a sample Excel file, processes it using the full pipeline (LLM analysis, etc.), and generates an HTML report.
   ```bash
   python demo_run.py
   ```

4. **Run Backend API**:
   ```bash
   uvicorn app.main:app --app-dir backend --reload
   ```
   API Docs: http://localhost:8000/api/v1/docs
   - Auth: POST /api/v1/auth/login （默认 admin/admin，返回 JWT）

5. **Run Celery Worker** (Requires Redis):
   ```bash
   celery -A backend.app.workers.celery_app worker --loglevel=info -P pool
   ```
   *Note: On Windows, use `-P solo` or `-P threads` if `prefork` fails.*

## Architecture

- **Backend**: FastAPI
- **Task Queue**: Celery + Redis
- **Analysis**: GLM-4-Air (ZhipuAI)
- **Reporting**: JSON + Plotly (Frontend)
- **Database**: SQLite (default) / PostgreSQL

## Manual References
See `系统构建手册` for detailed design documents.

### Frontend (SPA) Dev
- In `frontend/`:
  ```bash
  npm install
  npm run dev
  ```
- Dev proxy: Vite 将 `/api` 代理到 `http://127.0.0.1:8000`
- Build: `npm run build` 输出纯静态文件（index.html + assets）

### Separation Notes
- Backend returns JSON only; removed template rendering
- All routes under `/api/v1/...`
- Error format: `{"error":{"code":<int>,"message":"..."}}`
