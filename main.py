# -*- coding: utf-8 -*-
"""
AI Token Hub API - Optimized Version
"""

from fastapi import FastAPI,Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware  # 
from app.core.req_limiter import rate_limit_middleware
from app.back_jobs.schedule import lifespanJob
from app.core.deps import get_price_repo
from app.features.biz.order.price_repo import PriceRepo
from app.api.v1 import api_router
from app.core.config import settings


domain_url = settings.FRONTEND_URL
# ============== FastAPI App ==============

app = FastAPI(
    title=" Token Maker API",
    description="API for purchasing and managing AI tokens from Chinese providers",
    version="2.0.0",
    lifespan=lifespanJob
)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,  
)
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[domain_url,'http://localhost:5173'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)
# ============== Register Routers ==============

app.include_router(api_router, prefix="") 


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "message": "Token Maker API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "providers": "GET /providers",
            "auth": "POST /auth/login",
            "users": "GET /users",
            "tokens": "GET /tokens",
            "orders": "POST /orders",
            "balance": "GET /balance",
            "oauth": "GET /oauth",
            "files": "GET /files",
            "admin": "GET /admin"
        }
    }
 

@app.get('/price',response_model=list)
async def get_model_price(price:PriceRepo=Depends(get_price_repo)): 
    return await price.get_all_pricing()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
