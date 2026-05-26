from fastapi import APIRouter
from app.api import sessions, interview, feedback, upload

api_router = APIRouter(prefix="/api")
api_router.include_router(sessions.router)
api_router.include_router(interview.router)
api_router.include_router(feedback.router)
api_router.include_router(upload.router)
