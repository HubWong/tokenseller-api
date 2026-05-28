# -*- coding: utf-8 -*-
"""
AI Token Hub API - Optimized Version
"""

from app.core.app_settings import create_app

# ============== FastAPI App ==============
app = create_app()

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
async def get_model_price(): 
    return app.state.oneapi_channels

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
