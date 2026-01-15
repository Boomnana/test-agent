from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api.api import api_router
from app.core.logging import get_logger
from app.db.base import Base
import os

logger = get_logger("main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

base_dir = os.path.dirname(os.path.dirname(__file__))
project_root = os.path.dirname(base_dir)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

reports_dir = os.path.join(project_root, "reports")
if os.path.isdir(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


@app.get("/app", response_class=FileResponse)
def frontend_app():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/")
def root():
    return {"message": "Welcome to Test Report Agent API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
