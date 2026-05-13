import httpx
import json as json_lib
from fastapi import Request
import logging
from typing import Any, Dict, List, Tuple, AsyncIterator
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
from ast import Dict
from typing import Optional, List
from decimal import Decimal
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
import logging
from fastapi.responses import StreamingResponse
from app.core.config import settings
from starlette.requests import ClientDisconnect
from app.features.biz.apikey.apikey_crud import apikey_crud

from app.core.abc_biz import  ConsumeService

logger = logging.getLogger(__name__)

MASTER_KEY = settings.ONE_API_MASTERKEY
create_userapi = f'{settings.ONEAPI_URL}/api/user/'
access_token =f'{settings.ONEAPI_ACCESS_TOKEN}'
MODEL_MAP = {
    "free": ["deepseek-chat"],
    "cheap": ["gpt-3.5", "deepseek-chat"],
    "pro": ["gpt-4", "claude-3"],
    "ultra": ["claude-3"],
}
PRICE_INPUT = Decimal("0.002")
PRICE_OUTPUT = Decimal("0.004")


def resolve_model(tier: str) -> str:
    models = MODEL_MAP.get(tier, MODEL_MAP["free"])
    return models[0] if models else "deepseek-chat"


class OneAPIError(Exception):
    pass

class RetryableAPIError(OneAPIError):
    pass


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
    def __init__(self, messages: List[dict], model: str = "gpt-3.5-turbo"):
        self.messages = messages
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

    def finalize(self, full_text: str = "") -> dict[str, int]:
        if self.has_real_usage:
            return self.usage

        import tiktoken
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


# ================= 核心异步服务类 =================
class OneAPISvc:
    def __init__(
        self,
        base_url: str = settings.ONEAPI_BASE_URL,
        api_key: str = "",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or MASTER_KEY
        self.timeout = httpx.Timeout(timeout)
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        print("one api started..")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _user_header(self)->dict[str,str]:
        return  {
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
        tracker = UsageTracker(messages=payload.get("messages", []), model=payload.get("model", "gpt-3.5-turbo"))
        full_text = []

        async def _inner_gen():
            async with self.client.stream(
                "POST", self.base_url, headers=self._headers(), json={**payload, "stream": True}
            ) as response:
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json_lib.loads(raw)
                    except Exception:
                        continue

                    tracker.update_from_chunk(chunk)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta:
                        full_text.append(delta["content"])
                    yield chunk

        return StreamIterator(_inner_gen(), tracker, full_text)

    async def _request(self, json_data: dict[str, Any], method: str = "POST") -> Tuple[Dict, Dict]:
        tracker = UsageTracker(json_data.get("messages"), json_data.get("model"))
    
        resp = await self.client.request(method=method, url=self.base_url, headers=self._headers(), json=json_data)
        if resp.status_code >= 400:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:800]}"
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RetryableAPIError(error_msg)
            raise OneAPIError(error_msg)

        data = resp.json()
        if "usage" in data:
            return data, data["usage"]

        full_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return data, tracker.finalize(full_text)

    async def embeddings(self, model: str, input_text: str | List[str]) -> Dict:
        return await self._request("POST", f"{self.base_url}/embeddings", {"model": model, "input": input_text})

    async def models(self) -> Dict:
        return await self._request("GET", f"{self.base_url}/models", {})

    async def aclose(self):
        print('one api closed..')
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def create_oneapi_user(self,username:str,pwd:str):
        json_data ={
            "username": username,
            "password": pwd
        }
        
        try:
            resp = await self.client.request(method='post', 
                url= create_userapi, 
                headers=self._user_header(), 
                json=json_data)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:800]}"
            print(error_msg)
            # if e.response.status_code in (429, 500, 502, 503, 504):
            #     raise RetryableAPIError(error_msg)
            # raise OneAPIError(error_msg)

        pass

    async def chat_llm(self, request: Request, 
        consume_svc: ConsumeService,        
        db:AsyncSession,
        token_repo:TokenUsageRepo,
        stream: bool):                              
        key_data = await apikey_crud.auth_user(db=db, request=request,token_respo=token_repo)
        body = await request.json()
        messages = body.get("messages", [])
        
        tier = key_data["tier"]
        model = resolve_model(tier)

        common_params = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "stream": stream,
        }       
        request = await token_repo.add_token_log(db=db, uid=key_data["user_id"],json_data=common_params,resp_data='api request:')
        if not stream:
            data, usage = await self._request(json_data=common_params)
            await consume_svc.charge(token_usage=request,
                        user_id=key_data["user_id"],
                        usage=usage,
                        request_model=model,
                        session=db)
            return data
        else:
            async def event_generator():
                stream_iter = await self._stream(payload=common_params)
                usage = None
                try:
                    async for chunk in stream_iter:
                        # ✅ 统一使用 json_lib 保证 SSE 协议合法（自动转义引号/换行）
                        yield f"data: {json_lib.dumps(chunk)}\n\n"

                    usage = stream_iter.tracker.finalize("".join(stream_iter.full_text))

                except ClientDisconnect:
                    logger.info("Client disconnected stream")
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    yield f"data: {json_lib.dumps({'error': str(e)})}\n\n"
                finally:
                    # Charge for usage even if stream fails
                    if usage:
                        try:
                            await consume_svc.charge(token_usage=request,
                                                    user_id=key_data["user_id"],
                                                    usage=usage,
                                                    request_model=model,
                                                    session=db)
                        except Exception as charge_error:
                            logger.error(f"Failed to charge after stream: {charge_error}")

            return StreamingResponse(event_generator(), media_type="text/event-stream")

