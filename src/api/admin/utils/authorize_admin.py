import jwt
from src.core import models
from src.core.security.security import SECRET_KEY, ALGORITHM


# ✅ CORREÇÃO: Importa as constantes do local correto


# Esta função é para autorizar TOTENS, não admins. Vamos renomeá-la para clareza.
async def authorize_totem_by_device_token(db, token: str):
    totem = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.totem_token == token,
        models.TotemAuthorization.granted.is_(True),
    ).first()
    if not totem or not totem.granted_by_id:
        return None
    return totem

# ✅ NOVA FUNÇÃO: Esta função sabe como lidar com o JWT do admin.
async def authorize_admin_by_jwt(db, token: str):
    """
    Autoriza um administrador decodificando seu JWT.
    Retorna o objeto do usuário (models.User) se o token for válido.
    """
    try:
        # Decodifica o payload do JWT usando a chave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        # Trata ambos os erros de token inválido ou expirado
        print(f"Token JWT inválido ou expirado: {token[:10]}...")
        return None

    # Busca o usuário no banco de dados pelo email (que está no 'sub' do token)
    user = db.query(models.User).filter(models.User.email == username).first()
    return user





# import jwt
# from src.core import models
# # ✅ CORREÇÃO: Importa as constantes do local correto
# from src.core.security import SECRET_KEY, ALGORITHM
#
# # Esta função é para autorizar TOTENS, não admins. Vamos renomeá-la para clareza.
# async def authorize_totem_by_device_token(db, token: str):
#     totem = db.query(models.TotemAuthorization).filter(
#         models.TotemAuthorization.totem_token == token,
#         models.TotemAuthorization.granted.is_(True),
#     ).first()
#     if not totem or not totem.granted_by_id:
#         return None
#     return totem
#
# # ✅ NOVA FUNÇÃO: Esta função sabe como lidar com o JWT do admin.
# async def authorize_admin_by_jwt(db, token: str):
#     """
#     Autoriza um administrador decodificando seu JWT.
#     Retorna o objeto do usuário (models.User) se o token for válido.
#     """
#     try:
#         # Decodifica o payload do JWT usando a chave secreta
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             return None
#
#     except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
#         # Trata ambos os erros de token inválido ou expirado
#         print(f"Token JWT inválido ou expirado: {token[:10]}...")
#         return None
#
#     # Busca o usuário no banco de dados pelo email (que está no 'sub' do token)
#     user = db.query(models.User).filter(models.User.email == username).first()
#     return user