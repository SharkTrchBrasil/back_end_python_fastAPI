import os
import hmac
import hashlib
import json
import time
from fastapi import Request, HTTPException
from typing import Optional

_redis = None
_redis_url = os.getenv('REDIS_URL') or os.getenv('REDIS_PUBLIC_URL')
if _redis_url:
    try:
        from redis import asyncio as aioredis
        _redis = aioredis.from_url(_redis_url, encoding='utf-8', decode_responses=True)
    except Exception:
        _redis = None

MAX_SKEW_MS = 5 * 60 * 1000
CHATBOT_SECRET = os.getenv('CHATBOT_WEBHOOK_SECRET', '')

# Simple nonce store; uses Redis if available, otherwise in-memory
_nonces = {}
_last_cleanup = 0

def _cleanup_nonces():
	global _last_cleanup
	now = int(time.time() * 1000)
	if now - _last_cleanup < 60_000:
		return
	to_delete = []
	for nonce, ts in _nonces.items():
		if now - ts > MAX_SKEW_MS:
			to_delete.append(nonce)
	for n in to_delete:
		_nonces.pop(n, None)
	_last_cleanup = now

async def verify_hmac_signature(request: Request):
	if not CHATBOT_SECRET:
		raise HTTPException(status_code=500, detail='Server misconfigured')

	signature = request.headers.get('x-signature')
	timestamp = request.headers.get('x-timestamp')
	nonce = request.headers.get('x-nonce')

	if not signature or not timestamp or not nonce:
		raise HTTPException(status_code=403, detail='Missing signature headers')

	try:
		ts = int(timestamp)
	except ValueError:
		raise HTTPException(status_code=408, detail='Invalid timestamp')

	if abs(int(time.time() * 1000) - ts) > MAX_SKEW_MS:
		raise HTTPException(status_code=408, detail='Expired signature')

	# Replay protection (Redis preferred)
	if _redis:
		try:
			key = f"hmac_nonce:{nonce}"
			# set if not exists with PX (ms)
			ok = await _redis.set(key, '1', nx=True, px=MAX_SKEW_MS)
			if not ok:
				raise HTTPException(status_code=409, detail='Replay detected')
		except HTTPException:
			raise
		except Exception:
			# Fallback to memory on Redis issue
			_cleanup_nonces()
			if nonce in _nonces:
				raise HTTPException(status_code=409, detail='Replay detected')
			_nonces[nonce] = ts
	else:
		_cleanup_nonces()
		if nonce in _nonces:
			raise HTTPException(status_code=409, detail='Replay detected')
		_nonces[nonce] = ts

	content_type = request.headers.get('content-type', '')
	if 'application/json' in content_type:
		body_bytes = await request.body()
		try:
			parsed = json.loads(body_bytes or b'{}')
		except Exception:
			parsed = {}
		body_str = json.dumps(parsed, separators=(',', ':'), ensure_ascii=False)
		payload = f"{timestamp}.{nonce}.{body_str}"
	else:
		# multipart/form-data or others: we signed sorted field names meta
		form = await request.form()
		fields = sorted(list(form.keys()))
		meta = json.dumps({ 'fields': fields }, separators=(',', ':'), ensure_ascii=False)
		payload = f"{timestamp}.{nonce}.{meta}"

	expected = hmac.new(CHATBOT_SECRET.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()

	# constant-time compare
	if not hmac.compare_digest(expected, signature):
		raise HTTPException(status_code=403, detail='Invalid signature')

	return True


