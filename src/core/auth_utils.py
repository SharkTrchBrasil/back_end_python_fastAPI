import jwt
from jwt import InvalidTokenError

from src.api.admin.services.auth import SECRET_KEY, ALGORITHM


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        return email
    except InvalidTokenError as e:
        return None