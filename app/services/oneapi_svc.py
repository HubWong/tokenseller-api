from __future__ import annotations

# 标准库
import json
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, AsyncIterator, TYPE_CHECKING
import httpx
import tiktoken
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from starlette.requests import ClientDisconnect
from app.core.config import settings

# 项目内部模块
if TYPE_CHECKING:
    from app.core.deps import TransacDeps
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.features.biz.apikey.apikey_schema import ApiKeyResp
from app.core.abc_biz import ConsumeService
from app.features.biz.usage.token_usage_repo import TokenUsageRepo

logger = logging.getLogger(__name__)

# 从配置读取主密钥，避免硬编码
MASTER_KEY = getattr(settings, "ONE_API_MASTERKEY", None)
create_userapi = f"{settings.ONEAPI_URL}/api/user"

PRICE_INPUT = Decimal("0.002")
PRICE_OUTPUT = Decimal("0.004")



def resolve_model(tier: str, model_price_cache: dict) -> List[str]:
    switcher = {
        "free": 1,
        "cheap": 2,
        "pro": 3
        }
    target_level = switcher.get(tier)
    default_models = model_price_cache[0]["name"]
    models =[m["name"] for m in model_price_cache if m.get("level") == target_level] if target_level else []
    return models if models else [default_models]


# ================= 异步迭代器包装器 =================
class StreamIterator:
    """将异步生成器与 tracker/full_text 状态绑定，支持直接 async for 遍历"""

    def __init__(self, async_gen: AsyncIterator[dict], tracker: "UsageTracker", full_text: List[str]):
        self._gen = async_gen
        self.tracker = tracker
        self.full_text = full_text

    def __aiter__(self) -> AsyncIterator[dict]:
        return self._gen


# ================= Token 统计器 =================
class UsageTracker:
    def __init__(self, messages: Optional[List[dict]] = None, model: str = "gpt-3.5-turbo"):
        self.messages = messages or []
        self.model = model
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.has_real_usage = False

    def update_from_chunk(self, chunk: dict):
        if isinstance(chunk, dict):
            usage = chunk.get("usage")
            if usage:
                self.usage.update({
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                })
                self.has_real_usage = True

    def finalize(self, full_text: str = "") -> Dict[str, int]:
        if self.has_real_usage:
            return self.usage

        try:
            enc = tiktoken.encoding_for_model(self.model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")  # 安全 fallback

        prompt_tokens = sum(len(enc.encode(msg.get("content", ""))) for msg in self.messages)
        completion_tokens = len(enc.encode(full_text)) if full_text else 0

        self.usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        return self.usage


json_lib = json  # 与原代码保持一致


# 自定义异常（建议统一管理）
class OneAPIError(Exception):
    """基础 OneAPI 异常"""


class RetryableAPIError(OneAPIError):
    """可重试的 OneAPI 异常（如 5xx / 429 等）"""


class OneAPISvc:
    def __init__(
        self,
        base_url: str = settings.ONEAPI_URL,
        api_key: Optional[str] = MASTER_KEY,
        timeout: int = 30,
    ):
        # 清理URL，统一格式
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
        self.embeddings_url = f"{self.base_url}/embeddings"
        self.models_url = f"{self.base_url}/models"
        self.api_key = api_key 
        self.timeout = httpx.Timeout(timeout)

        # 连接池配置：更合理的生产参数，避免资源浪费
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=10,
                keepalive_expiry=10,
            ),
        )
        logger.info("OneAPI service initialized")

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_default_headers(api_key: str) -> Dict[str, str]:
        """缓存请求头，避免重复创建字典"""
        logger.debug("OneAPISvc: using api_key prefix: %s", api_key and api_key[:8])
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _headers(self) -> Dict[str, str]:
        """系统默认请求头（带缓存）"""
        return self._get_default_headers(self.api_key)

    @staticmethod
    def _get_user_headers(access_token: str) -> Dict[str, str]:
        """用户身份请求头（依赖注入，不再使用全局变量）"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=8, exp_base=2, jitter=1.0),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            RetryableAPIError,
        )),
        reraise=True,
    )
    async def _stream(self, payload: dict) -> StreamIterator:
        tracker = UsageTracker(
            messages=payload.get("messages", []),
            model=payload.get("model", "gpt-3.5-turbo"),
        )
        full_text: List[str] = []

        async def _inner_gen():
            async with self.client.stream(
                "POST",
                self.chat_url,
                headers=self._headers(),
                json={**payload, "stream": True},
            ) as response:
                # 提前校验响应状态
                if response.status_code >= 400:
                    body = await response.aread()
                    error_msg = f"Stream HTTP {response.status_code}: {body}"
                    if response.status_code in (429, 500, 502, 503, 504):
                        raise RetryableAPIError(error_msg)
                    raise OneAPIError(error_msg)

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break

                    try:
                        chunk = json_lib.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Invalid chunk JSON: %s", raw[:100])
                        continue

                    tracker.update_from_chunk(chunk)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if content := delta.get("content"):
                        full_text.append(content)
                    yield chunk

        return StreamIterator(_inner_gen(), tracker, full_text)

    async def _request(
        self,
        json_data: Dict[str, Any] | None,
        method: str = "POST",
        url: Optional[str] = None,
    ) -> Tuple[Dict, Dict]:
        """统一请求方法：增强健壮性"""
        url = url or self.chat_url
        json_data = json_data or {}
        tracker = UsageTracker( messages=json_data.get("messages"), model=json_data.get("model",'default'))
        logger.debug("\n [*]:requesting url => %s", url)
        resp = await self.client.request(
            method=method,
            url=url,
            headers=self._headers(),
            json=json_data,
        )

        # 统一错误处理
        if resp.status_code >= 400:
            text = await resp.aread()
            error_msg = f"HTTP {resp.status_code}: {text[:800]}"
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RetryableAPIError(error_msg)
            raise OneAPIError(error_msg)

        try:
            data = resp.json()
        except Exception:
            # 非 JSON 响应，包装为 OneAPIError
            text = await resp.aread()
            raise OneAPIError(f"Invalid JSON response HTTP {resp.status_code}: {text[:800]}")

        usage = data.get("usage") or tracker.finalize(
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return data, usage

    async def embeddings(self, model: str, input_text: str | List[str]) -> Tuple[Dict, Dict]:
        return await self._request(
            method="POST",
            url=self.embeddings_url,
            json_data={"model": model, "input": input_text},
        )

    async def models(self) -> Tuple[Dict, Dict]:
        return await self._request(method="GET", 
                                   url=self.models_url,
                                   json_data={})

    async def oneapi_request(self,  
                                url: str,
                                json_data: Dict[str, Any] | None,
                                method: str = "POST"
                                ) -> Tuple[Dict, Dict]:
        
        """外部调用的统一请求接口，自动重试"""
        try:
            logger.debug("\n [*]:requesting url => %s", url)
            resp = await self.client.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_data,
            )
            if resp.status_code >= 400:
                text = await resp.aread()
                error_msg = f"HTTP {resp.status_code}: {text[:800]}"
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RetryableAPIError(error_msg)
                raise OneAPIError(error_msg)
            return resp.json()
        
        except RetryableAPIError as e:
            logger.warning("Retryable error occurred: %s", str(e))
            raise
        except OneAPIError as e:
            logger.error("OneAPI error occurred: %s", str(e))
            raise
        except Exception as e:
            logger.exception("Unexpected error in request_with_retry")
            raise OneAPIError("Unexpected error") from e

    async def create_model(self, model_name: str, input_cost: float, output_cost: float) -> Tuple[Dict, Dict]:
        return await self.oneapi_request(
            url=f"{self.base_url}/api/model",
            json_data={"name": model_name, "input_cost": input_cost, "output_cost": output_cost},
            method="POST"
        )

    async def create_oneapi_user(self, username: str, pwd: str, access_token: str) -> Dict:
        """全局 access_token 改为参数注入，完善异常处理"""
        json_data = {"username": username, "password": pwd}
        headers = self._get_user_headers(access_token)

        try:
            resp = await self.client.post(
                url=create_userapi,
                headers=headers,
                json=json_data,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"Create user failed: {e.response.status_code} | {e.response.text[:800]}"
            logger.error(error_msg)
            #raise HTTPException(status_code=e.response.status_code, detail=error_msg) from e
            return {"error": error_msg}
        except Exception as e:
            logger.exception("Unexpected error creating user")
            #raise HTTPException(status_code=500, detail="Internal server error") from e
            return {"error": "Internal server error"}

    async def close(self):
        """优雅关闭客户端"""
        if hasattr(self, "client"):
            try:
                await self.client.aclose()
            except Exception:
                logger.exception("Error closing OneAPI client")
            else:
                logger.info("OneAPI service closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self):
        await self.close()

    async def chat_llm(
        self,
        request: Request,
        consume_svc: ConsumeService,
        db: AsyncSession,
        trans_repo: TransacDeps,
        token_repo: TokenUsageRepo,
        stream: bool,
    ):
        """核心聊天接口：结构优化、异常安全、日志增强"""
        # 1. 认证与参数解析
        rst = await apikey_crud.auth_user(db=db, request=request, balance_repo=trans_repo)
        
        if rst is None:
            raise HTTPException(status_code=403,detail = "Invalid API Key")
        
        key_data = ApiKeyResp.model_validate(rst)

        body = await request.json()
        messages = body.get("messages", [])

        if not messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")

        # 2. 模型与参数组装
        tier = key_data.tier
        model = resolve_model(tier, request.app.state.model_price_cache)
        common_params = {
            "model": model[0],
            "messages": messages,
            "temperature": 0.7,
            "stream": stream,
        }

        # 3. 日志记录
        token_log = await token_repo.add_token_log(
            db=db,
            uid=key_data.user_id,
            json_data=common_params,
            resp_data="api request received",
        )

        # 4. 非流式请求
        if not stream:
            data, usage = await self._request(json_data=common_params)

            await consume_svc.charge(
                token_usage=token_log,
                user_data=key_data,
                usage=usage,
                request_model=model,
                session=db,
            )
            return data

        # 5. 流式响应（安全封装）
        async def event_generator():
            stream_iter = await self._stream(payload=common_params)
            usage = None

            try:
                async for chunk in stream_iter:
                    yield f"data: {json_lib.dumps(chunk, ensure_ascii=False)}\n\n"
                usage = stream_iter.tracker.finalize("".join(stream_iter.full_text))

            except ClientDisconnect:
                logger.info("Client disconnected | user_id=%s", key_data.user_id)
            except Exception as e:
                logger.error("Stream error | user_id=%s, error=%s", key_data.user_id, str(e))
                yield f"data: {json_lib.dumps({'error': 'stream error'})}\n\n"
            finally:
                # 确保计费一定执行
                if usage:
                    try:
                        await consume_svc.charge(
                            token_usage=token_log,
                            user_data=key_data,
                            usage=usage,
                            request_model=model,
                            session=db,
                        )
                    except Exception as charge_error:
                        logger.critical(
                            "Charge failed | user_id=%s, error=%s", key_data.user_id, str(charge_error)
                        )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
