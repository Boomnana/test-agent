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
   uvicorn backend.app.main:app --reload
   ```
   API Docs: http://localhost:8000/api/v1/docs

5. **Run Celery Worker** (Requires Redis):
   ```bash
   celery -A backend.app.workers.celery_app worker --loglevel=info -P pool
   ```
   *Note: On Windows, use `-P solo` or `-P threads` if `prefork` fails.*

## Architecture

- **Backend**: FastAPI
- **Task Queue**: Celery + Redis
- **Analysis**: GLM-4-Air (ZhipuAI)
- **Reporting**: Jinja2 + Plotly
- **Database**: SQLite (default) / PostgreSQL

## Manual References
See `系统构建手册` for detailed design documents.
