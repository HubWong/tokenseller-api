"""
AI Chat Gateway — endpoint handles auth / model matching / charging,
delegates actual API calls to OneApiSvc.
"""
import json
import logging
from fastapi import APIRouter,  HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect
from app.core.config import settings
from app.core.deps import ( 
    PriceRepoDeps, TokenUsageDeps, DbSessionDeps, TransRepoDeps
)
from app.core.deps_svc import OneApiDeps, ConsumeDeps
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.features.biz.apikey.apikey_schema import ApiKeyResp
from app.services.oneapi.model_choose import  get_models_avialable
from app.services.tools_svc import check_api_reachable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI chat gateway"])


@router.post("/completions")
async def one_api_llm_test(
            request: Request,
            trans_repo: TransRepoDeps ,
            oneSvc: OneApiDeps,
            consume_svc: ConsumeDeps,
            token_repo: TokenUsageDeps,
            model_price_repo: PriceRepoDeps,
            db: DbSessionDeps,
            stream: bool = False,
        ):
    """核心聊天接口：认证 → 模型匹配 → 调用 OneAPI → 计费"""

    is_open = check_api_reachable(settings.ONEAPI_URL, 6)
    if not is_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API unreachable")

    # 1. API Key 认证
    apikey, _ = await apikey_crud.auth_user(db=db, request=request, balance_repo=trans_repo)
    if apikey is None:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    apikey_data = ApiKeyResp.model_validate(apikey)

    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    channels = await oneSvc.channels()
    selected_model,model_price = await get_models_avialable(tier=apikey_data.tier, 
                                                channels=channels,
                                                body=body, price_repo=model_price_repo) 

    common_params = {
        "model": selected_model,
        "messages": messages,
        "temperature": 0.7,
        "stream": stream,
    }

    # 3. 预记录日志
    token_log = await token_repo.add_token_log(
        db=db,
        uid=apikey_data.user_id,
        json_data=common_params,
        resp_data="api request received",
    )

    # 4. 非流式请求
    if not stream:
        data, usage = await oneSvc._chat_llm(json_data=common_params)

        await consume_svc.charge(
            token_usage=token_log,
            model_price=model_price,
            user_data=apikey_data,
            usage=usage,
            request_model=selected_model,
            session=db,
        )
        return data

    # 5. 流式响应
    async def event_generator():
        stream_iter = await oneSvc._chat_llm_stream(payload=common_params)
        usage = None

        try:
            async for chunk in stream_iter:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            usage = stream_iter.tracker.finalize("".join(stream_iter.full_text))

        except ClientDisconnect:
            logger.info("Client disconnected | user_id=%s", apikey_data.user_id)
        except Exception as e:
            logger.error("Stream error | user_id=%s, error=%s", apikey_data.user_id, str(e))
            yield f"data: {json.dumps({'error': 'stream error'})}\n\n"
        finally:
            if usage:
                try:
                    await consume_svc.charge(
                        token_usage=token_log,
                        user_data=apikey_data,
                        usage=usage,
                        model_price=model_price,
                        request_model=selected_model,
                        session=db,
                    )
                except Exception as charge_error:
                    logger.critical(
                        "Charge failed | user_id=%s, error=%s",
                        apikey_data.user_id, str(charge_error),
                    )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
