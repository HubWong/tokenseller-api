


# ================= Token 统计器 =================
from typing import Dict, List, Optional

import tiktoken


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
