from app.core.application import fapp
from app.core.config import settings
from app.api.v1 import api_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.core.req_limiter import rate_limit_middleware
from fastapi import FastAPI

domain_url = settings.FRONTEND_URL

allowed_origins = [
    "https://tokenmaker.ccwu.cc",
    "http://localhost:5173",
    "http://localhost:3000",
]
if domain_url:
    allowed_origins.append(domain_url)

def create_app()->FastAPI:

    # HTTPS redirect (respects X-Forwarded-Proto from Railway proxy)
    if settings.APP_ENV != "development":
        fapp.add_middleware(HTTPSRedirectMiddleware)

    fapp.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
    )
    # CORS middleware
    fapp.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fapp.middleware("http")(rate_limit_middleware)
    # ============== Register Routers ==============

    fapp.include_router(api_router, prefix="")
    return fapp
