 
from fastapi import APIRouter
from app.api.v1.auth_api import router as auth_router
from app.api.v1.notify_api import router as notify_router
from app.api.v1.chat_api import router as chat_router
from app.api.v1.order_api import router as orders_router
from app.api.v1.oauth_api import router as oauth_router
from app.api.v1.balance_api import router as balance_router
from app.api.v1.admin_api import router as admin_router
from app.api.v1.usage_api import router as usage_router
from app.api.v1.apikey_api import router as apikey_router
from app.api.v1.models_api import router as models_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(notify_router)
api_router.include_router(chat_router)
api_router.include_router(orders_router)
api_router.include_router(oauth_router)
api_router.include_router(balance_router)
api_router.include_router(admin_router)
api_router.include_router(usage_router)
api_router.include_router(apikey_router)
api_router.include_router(models_router)