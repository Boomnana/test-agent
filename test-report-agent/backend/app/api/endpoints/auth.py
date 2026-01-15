from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter()

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq):
    # Simple dev-only auth using env credentials if provided
    expected_user = getattr(settings, "AUTH_USERNAME", "admin")
    expected_pass = getattr(settings, "AUTH_PASSWORD", "admin")
    if req.username != expected_user or req.password != expected_pass:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(subject=req.username)
    return {"access_token": token, "token_type": "bearer"}
