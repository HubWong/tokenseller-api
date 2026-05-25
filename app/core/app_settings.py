from app.core.application import fapp
from app.core.config import settings
from app.api.v1 import api_router
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.core.req_limiter import rate_limit_middleware
from fastapi import FastAPI

domain_url = settings.FRONTEND_URL

def create_app()->FastAPI:
        
    fapp.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,  
    )
    # CORS middleware
    fapp.add_middleware(
        CORSMiddleware,
        allow_origins=[domain_url,'http://localhost:5173'],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fapp.middleware("http")(rate_limit_middleware)
    # ============== Register Routers ==============

    fapp.include_router(api_router, prefix="") 
    return fapp
