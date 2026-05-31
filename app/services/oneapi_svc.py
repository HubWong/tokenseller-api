# 标准库
import json
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional,  Tuple, AsyncIterator
import httpx
from app.services.oneapi.token_usage_proc import UsageTracker
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from app.core.config import settings
logger = logging.getLogger(__name__)

# 从配置读取主密钥，避免硬编码
MASTER_KEY = getattr(settings, "ONE_API_MASTERKEY", None)
create_userapi = f"https://one-api-production-dd42.up.railway.app/api/user"

PRICE_INPUT = Decimal("0.002")
PRICE_OUTPUT = Decimal("0.004")


# ================= 异步迭代器包装器 =================
class StreamIterator:
    """将异步生成器与 tracker/full_text 状态绑定，支持直接 async for 遍历"""

    def __init__(self, async_gen: AsyncIterator[dict], tracker: "UsageTracker", full_text: List[str]):
        self._gen = async_gen
        self.tracker = tracker
        self.full_text = full_text

    def __aiter__(self) -> AsyncIterator[dict]:
        return self._gen

# 自定义异常（建议统一管理）
class OneAPIError(Exception):
    """基础 OneAPI 异常"""


class RetryableAPIError(OneAPIError):
    """可重试的 OneAPI 异常（如 5xx / 429 等）"""


class OneApiSvc:
    def __init__(
        self,
        base_url: str = https://one-api-production-dd42.up.railway.app,
        api_key: Optional[str] = MASTER_KEY,
        timeout: int = 30,
    ):
        # 清理URL，统一格式
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.embeddings_url = f"{self.base_url}/embeddings"
        self.models_url = f"{self.base_url}/v1/models"
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
        logger.debug("OneApiSvc: using api_key prefix: %s", api_key and api_key[:8])
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
    async def _chat_llm_stream(self, payload: dict) -> StreamIterator:
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
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Invalid chunk JSON: %s", raw[:100])
                        continue

                    tracker.update_from_chunk(chunk)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if content := delta.get("content"):
                        full_text.append(content)
                    yield chunk

        return StreamIterator(_inner_gen(), tracker, full_text)

    async def _chat_llm(
            self,
            json_data: Dict[str, Any] | None,
            method: str = "POST",
            url: Optional[str] = None,
    ) -> Tuple[Dict, Dict]:
        url = url or self.chat_url
        json_data = json_data or {}
        tracker = UsageTracker(messages=json_data.get("messages"), model=json_data.get("model", 'default'))
        
        resp = await self.client.request(
            method=method,
            url=url,
            headers=self._headers(),
            json=json_data,
        )
    
        # ✅ 先读取一次原始内容，全程使用异步读取
        raw_content = await resp.aread()  # 只读一次！
        
        # 统一错误处理
        if resp.status_code >= 400:
            error_msg = f"HTTP {resp.status_code}: {raw_content[:800]}"
            print("【错误返回】", raw_content)  # 调试用
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RetryableAPIError(error_msg)
            raise OneAPIError(error_msg)

        try:
            # ✅ 从已读取的 bytes 数据解析 JSON（关键修复）
            import json
            data = json.loads(raw_content)
        except Exception as e:
                # 打印原始请求体
            logger.warning("🔥 请求体 json_data = %s", json_data)
            # 打印原始响应信息
            logger.warning("🔥 resp.status_code = %s", resp.status_code)
            raw_content=await resp.aread()
            logger.warning("🔥 raw_content = %r", raw_content)  # 看真实字节
            logger.warning("🔥 resp.headers = %s", resp.headers)

            logger.error("Non-JSON response HTTP %s: %s", resp.status_code, raw_content)
            raise OneAPIError(f"Invalid JSON response HTTP {resp.status_code}: {str(e)} | content={raw_content[:200]}")

        usage = data.get("usage") or tracker.finalize(
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return data, usage


    # async def embeddings(self, model: str, input_text: str | List[str]) -> Tuple[Dict, Dict]:
    #     return await self._request(
    #         method="POST",
    #         url=self.embeddings_url,
    #         json_data={"model": model, "input": input_text},
    #     )

    @staticmethod
    async def channels():
        chan_url = https://one-api-production-dd42.up.railway.app+'/api/channel/'
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url=chan_url,
                    headers= {
                        "Authorization": f"Bearer {settings.ONE_API_ADMIN_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", []) if isinstance(data, dict) else []
        except httpx.TimeoutException:
            print(f"get_one_api_channels timeout: {chan_url}")
            return []
        except Exception as ex:
            print(f"[*error*]get_one_api_channels error: {ex}")
            return []
        pass

    @staticmethod
    async def models(models_url,timeout:int=10) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url=models_url,
                    headers= {
                        "Authorization": f"Bearer {settings.ONE_API_MASTERKEY}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", []) if isinstance(data, dict) else []
        except httpx.TimeoutException:
            print(f"get_one_api_models timeout: {models_url}")
            return []
        except Exception as ex:
            print(f"[*error*]get_one_api_models error: {ex}")
            return []
        
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
            return {"error": error_msg}
        except Exception as e:
            logger.exception("Unexpected error creating user")
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

