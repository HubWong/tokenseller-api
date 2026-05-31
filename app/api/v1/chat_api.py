# chat_api.py

"""
AI Chat Gateway
"""
import json
import logging
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect
from app.core.config import settings
from app.core.deps import (
    PriceRepoDeps,
    TokenUsageDeps,
    DbSessionDeps,
    TransRepoDeps
)

from app.core.deps_svc import (
    OneApiDeps,
    ConsumeDeps
)

from app.features.biz.apikey.apikey_crud import apikey_crud
from app.features.biz.apikey.apikey_schema import ApiKeyResp

from app.services.oneapi.model_choose import (
    get_models_avialable
)

from app.services.tools_svc import (
    check_api_reachable
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["AI chat gateway"]
)


@router.post("/completions")
async def one_api_llm_test(
        request: Request,
        trans_repo: TransRepoDeps,
        oneSvc: OneApiDeps,
        consume_svc: ConsumeDeps,
        token_repo: TokenUsageDeps,
        model_price_repo: PriceRepoDeps,
        db: DbSessionDeps,
):
    """
    核心流程：

    1. API Key 认证
    2. 获取可用模型
    3. OneAPI 模型映射
    4. 请求 OneAPI
    5. usage 计费
    """

    # =========================================================
    # 1. 检查 OneAPI
    # =========================================================

    is_open = check_api_reachable(
        'https://one-api-production-dd42.up.railway.app',
        6
    )

    if not is_open:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OneAPI unreachable"
        )

    # =========================================================
    # 2. API Key 鉴权
    # =========================================================

    apikey, _ = await apikey_crud.auth_user(
        db=db,
        request=request,
        trans_repo=trans_repo
    )

    if apikey is None:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )

    apikey_data = ApiKeyResp.model_validate(apikey)

    # =========================================================
    # 3. body
    # =========================================================

    body = await request.json()

    messages = body.get("messages", [])

    if not messages:
        raise HTTPException(
            status_code=400,
            detail="messages cannot be empty"
        )

    stream = body.get("stream", False)

    # =========================================================
    # 4. 获取渠道
    # =========================================================

    channels = await oneSvc.channels()

    if not channels:
        raise HTTPException(
            status_code=500,
            detail="No channels found"
        )

    # =========================================================
    # 5. 获取最终模型
    # =========================================================

    model_data = await get_models_avialable(
        tier=apikey_data.tier,
        channels=channels,
        body=body,
        price_repo=model_price_repo
    )

    request_model = model_data["request_model"]

    target_model = model_data["target_model"]

    model_price = model_data["model_price"]

    channel_id = model_data["channel_id"]

    channel_name = model_data["channel_name"]

    logger.info(
        "model selected | user=%s | request=%s | target=%s | channel=%s",
        apikey_data.user_id,
        request_model,
        target_model,
        channel_name
    )

    # =========================================================
    # 6. 请求参数
    # =========================================================

    common_params = {
        "model": target_model,
        "messages": messages,
        "temperature": body.get("temperature", 0.7),
        "top_p": body.get("top_p", 1),
        "presence_penalty": body.get("presence_penalty", 0),
        "frequency_penalty": body.get("frequency_penalty", 0),
        "max_tokens": body.get("max_tokens"),
        "stream": stream,
    }

    # =========================================================
    # 7. token log
    # =========================================================

    token_log = await token_repo.add_token_log(
        db=db,
        uid=apikey_data.user_id,
        json_data=common_params,
        resp_data="api request received",
    )

    # =========================================================
    # 8. 非流式
    # =========================================================

    if not stream:

        try:

            data, usage = await oneSvc._chat_llm(
                json_data=common_params
            )

            await consume_svc.charge(
                token_usage=token_log,
                model_price=model_price,
                user_data=apikey_data,
                usage=usage,
                request_model=request_model,
                session=db,
            )

            return data

        except Exception as e:

            logger.exception(e)

            raise HTTPException(
                status_code=500,
                detail=str(e)
            )

    # =========================================================
    # 9. 流式
    # =========================================================

    async def event_generator():

        usage = None

        try:

            stream_iter = await oneSvc._chat_llm_stream(
                payload=common_params
            )

            async for chunk in stream_iter:

                yield (
                    f"data: "
                    f"{json.dumps(chunk, ensure_ascii=False)}\n\n"
                )

            usage = stream_iter.tracker.finalize(
                "".join(stream_iter.full_text)
            )

        except ClientDisconnect:

            logger.warning(
                "client disconnected | user=%s",
                apikey_data.user_id
            )

        except Exception as e:

            logger.exception(e)

            yield (
                f"data: "
                f"{json.dumps({'error': str(e)})}\n\n"
            )

        finally:

            if usage:

                try:

                    await consume_svc.charge(
                        token_usage=token_log,
                        model_price=model_price,
                        user_data=apikey_data,
                        usage=usage,
                        request_model=request_model,
                        session=db,
                    )

                except Exception as charge_error:

                    logger.critical(
                        "charge failed | user=%s | error=%s",
                        apikey_data.user_id,
                        str(charge_error),
                    )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

