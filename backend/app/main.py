from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.api import api_router
from app.core.logging import get_logger
from app.db.base import Base
import os

logger = get_logger("main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
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

reports_dir = os.path.join(project_root, "reports")
os.makedirs(reports_dir, exist_ok=True)
app.mount("/reports", StaticFiles(directory=reports_dir, html=True), name="reports")

@app.get("/")
def root():
    return {"message": "Welcome to Test Report Agent API"}

# Unified error response
@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": str(exc)}},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
