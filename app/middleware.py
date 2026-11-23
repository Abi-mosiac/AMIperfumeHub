import asyncio
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

AUTH_LIMITS = {
    "/auth/login": (10, 60),
    "/auth/register": (8, 3600),
    "/auth/vendor-register": (5, 3600),
    "/products/images": (20, 3600),
}
_requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


async def auth_rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/products/images":
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > 5 * 1024 * 1024 + 65536:
            response = JSONResponse(
                status_code=413,
                content={"detail": "Image files must be 5 MB or smaller"},
            )
            _add_security_headers(response)
            return response

    limit = AUTH_LIMITS.get(request.url.path)
    if request.method == "POST" and limit:
        max_requests, window = limit
        address = request.client.host if request.client else "unknown"
        key = (request.url.path, address)
        now = time.monotonic()
        async with _lock:
            attempts = _requests[key]
            while attempts and now - attempts[0] >= window:
                attempts.popleft()
            if len(attempts) >= max_requests:
                retry_after = max(1, int(window - (now - attempts[0])))
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many authentication attempts. Try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
                _add_security_headers(response)
                return response
            attempts.append(now)
            if len(_requests) > 10000:
                expired = [
                    old_key
                    for old_key, values in _requests.items()
                    if not values or now - values[-1] > 3600
                ]
                for old_key in expired:
                    _requests.pop(old_key, None)

    response = await call_next(request)
    _add_security_headers(response)
    return response


def _add_security_headers(response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' https: data:; "
        "style-src 'self'; script-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
