import uuid
from starlette.middleware.base import BaseHTTPMiddleware


class CorrelationIdMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request, call_next):
		cid = request.headers.get('x-correlation-id') or f"fa-{uuid.uuid4()}"
		request.state.correlation_id = cid
		response = await call_next(request)
		response.headers['x-correlation-id'] = cid
		return response


