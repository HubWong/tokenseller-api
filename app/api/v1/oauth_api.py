# -*- coding: utf-8 -*-
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.features.biz.user_balance.models import TransactionType
from app.features.user.user_crud import user_crud
from app.features.user.model.user_model import User
from app.core.security import create_access_token, create_refresh_token, generate_invite_code, get_password_hash
from app.core.deps import get_oneapi_svc, get_token_usage_rep,get_transaction_rep
from app.services.oneapi_svc import OneAPISvc
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.features.biz.apikey.apikey_crud import apikey_crud
from authlib.integrations.starlette_client import OAuth
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/oauth", tags=["oauth"])

# OAuth Response Schema
class OAuthResponse(BaseModel):
    success: bool
    message: str
    email: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None


# Initialize OAuth
oauth = OAuth()

# Register GitHub OAuth
oauth.register(
    name='github',
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
    client_session_kwargs={
        "trust_env": False  # 不读取系统代理
    }
)

# Register Google OAuth
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    },
    client_session_kwargs={
        "trust_env": False  # 不读取系统代理
    }
)


async def get_or_create_oauth_user(
    db: AsyncSession,
    email: str,
    provider: str,
    provider_id: str = None,
    name: str = None,
    one_api_svc: OneAPISvc = None,
    transaction_repo: TransactionRepo = None,
) -> User:
    """获取或创建 OAuth 用户"""
    user = await user_crud.get_by_email(db, emailOrTel=email)

    if user:
        # 更新已有用户的 OAuth 字段（如果为空）
        updated = False
        if not getattr(user, 'oauth_provider', None):
            setattr(user, 'oauth_provider', provider)
            updated = True
        if not getattr(user, 'oauth_id', None) and provider_id:
            setattr(user, 'oauth_id', provider_id)
            updated = True
        if updated:
            await db.commit()
            await db.refresh(user)
        return user

    # 创建新 OAuth 用户
    username = name or email.split('@')[0]
    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(f"oauth_{provider}_{provider_id}"),
        is_active=True,
        oauth_provider=provider,
        oauth_id=provider_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 生成邀请码
    user.invite_code = generate_invite_code(user.id)
    await db.commit()
    await db.refresh(user)

    # 赠送免费额度
    if transaction_repo:
        try:
            await transaction_repo.create_transaction(
                session=db,
                maker_id=int(getattr(user,'id')),
                amount=settings.FREE_AMOUNT,transaction_type=TransactionType.RECHARGE_FREE
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to add free tokens for OAuth user: {e}")

    # 生成 API Key
    try:
        await apikey_crud.generate_api_key(db=db, user_id=user.id)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to generate API key for OAuth user: {e}")

    # 同步到 OneAPI
    if one_api_svc:
        try:
            await one_api_svc.create_oneapi_user(username=username, pwd=f"oauth_{provider}_{provider_id}")
        except Exception as e:
            logger.warning(f"Failed to create OneAPI user for OAuth: {e}")

    return user


@router.get("/github")
async def github_login(request: Request):
    """GitHub OAuth 登录入口 - 重定向到 GitHub 授权页"""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    
    redirect_uri = f"{settings.BACKEND_URL}/oauth/callback/github"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/callback/github")
async def github_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    one_api_svc: OneAPISvc = Depends(get_oneapi_svc),
    transaction_repo: TransactionRepo = Depends(get_transaction_rep),
):
    """GitHub OAuth 回调处理"""
    try:
        token = await oauth.github.authorize_access_token(request)

        # 获取用户信息（使用相对路径，基于 api_base_url）
        resp = await oauth.github.get('user', token=token)
        user_data = resp.json()

        # 获取邮箱
        email_resp = await oauth.github.get('user/emails', token=token)
        emails_data = email_resp.json()
        email = next((e["email"] for e in emails_data if e.get("primary")), None)

        if not email:
            email = user_data.get("email") or f"github_{user_data.get('id')}@placeholder.com"

        username = user_data.get("name") or user_data.get("login")

        # 获取或创建用户
        user = await get_or_create_oauth_user(
            db,
            email=email,
            provider="github",
            provider_id=str(user_data.get("id")),
            name=username,
            one_api_svc=one_api_svc,
            transaction_repo=transaction_repo,
        )

        # 生成 JWT tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))[1]

        # 重定向回前端，带上 token 和用户名
        from urllib.parse import urlencode
        params = urlencode({
            "provider": "github",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "email": email,
            "username": username or "",
        })
        frontend_callback = f"{settings.FRONTEND_URL}/oauth/callback?{params}"
        return RedirectResponse(url=frontend_callback)

    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}", exc_info=True)
        error_url = f"{settings.FRONTEND_URL}/login?error=oauth_failed&provider=github"
        return RedirectResponse(url=error_url)


@router.get("/google")
async def google_login(request: Request):
    """Google OAuth 登录入口 - 重定向到 Google 授权页"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    
    redirect_uri = f"{settings.BACKEND_URL}/oauth/callback/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback/google")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    one_api_svc: OneAPISvc = Depends(get_oneapi_svc),
    transaction_repo: TransactionRepo = Depends(get_transaction_rep),
):
    """Google OAuth 回调处理"""
    try:
        token = await oauth.google.authorize_access_token(request)

        # 解析 ID token 获取用户信息
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")

        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="No email from Google")

        username = user_info.get("name")

        # 获取或创建用户
        user = await get_or_create_oauth_user(
            db,
            email=email,
            provider="google",
            provider_id=user_info.get("sub"),
            name=username,
            one_api_svc=one_api_svc,
            transaction_repo=transaction_repo,
        )

        # 生成 JWT tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))[1]

        # 重定向回前端，带上 token 和用户名
        from urllib.parse import urlencode
        params = urlencode({
            "provider": "google",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "email": email,
            "username": username or "",
        })
        frontend_callback = f"{settings.FRONTEND_URL}/oauth/callback?{params}"
        return RedirectResponse(url=frontend_callback)

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        error_url = f"{settings.FRONTEND_URL}/login?error=oauth_failed&provider=google"
        return RedirectResponse(url=error_url)


@router.get("/config")
async def get_oauth_config():
    """获取 OAuth 配置状态（供前端判断是否显示 OAuth 按钮）"""
    return {
        "github": {
            "enabled": bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET),
            "auth_url": "/api/v1/oauth/github"
        },
        "google": {
            "enabled": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            "auth_url": "/api/v1/oauth/google"
        }
    }


@router.get("/debug")
async def debug_oauth():
    """调试 OAuth 配置（仅用于开发）"""
    return {
        "github_client_id_set": bool(settings.GITHUB_CLIENT_ID),
        "github_client_secret_set": bool(settings.GITHUB_CLIENT_SECRET),
        "google_client_id_set": bool(settings.GOOGLE_CLIENT_ID),
        "google_client_secret_set": bool(settings.GOOGLE_CLIENT_SECRET),
        "redirect_url": settings.BACKEND_URL,
        "backend_url": settings.BACKEND_URL,
    }