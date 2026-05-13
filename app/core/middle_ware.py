from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from contextvars import ContextVar

from socketio import AsyncServer

request_id = ContextVar("request_id")
 


class EnhancedServer(AsyncServer):
    async def emit(self, event, data=None, **kwargs):
        if data and isinstance(data, dict):
            data["metadata"] = {
                "request_id": request_id.get(),
                "trace_id": kwargs.pop("trace_id", None)
            }
        return await super().emit(event, data, **kwargs)

 

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, time_window: int):
        super().__init__(app)
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()
        print('client:',client_ip)
        # Clean up old requests
        self.requests[client_ip] = [
            timestamp for timestamp in self.requests[client_ip]
            if current_time - timestamp < self.time_window
        ]
        # Check if the request limit has been exceeded
        if len(self.requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Please try again in {self.time_window} seconds.",
                    "data": None
                }
            )

        # Record the current request
        self.requests[client_ip].append(current_time)

        response = await call_next(request)
        return response