from fastapi import APIRouter
from app.api.endpoints import upload

api_router = APIRouter()
api_router.include_router(upload.router, prefix="/jobs", tags=["jobs"])
