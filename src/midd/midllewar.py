from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SubdomainMid(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        domain = "meudominio.com"

        subdomain = None
        if host.endswith(domain):
            parts = host.split(".")
            if len(parts) > 2:
                subdomain = parts[0]

        request.scope["subdomain"] = subdomain
        response = await call_next(request)
        return response
