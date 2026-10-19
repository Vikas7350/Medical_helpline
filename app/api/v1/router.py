from fastapi import APIRouter
from app.api.v1.admin import router as admin_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.telephony import router as telephony_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(sessions_router)
v1_router.include_router(telephony_router)
v1_router.include_router(admin_router)
