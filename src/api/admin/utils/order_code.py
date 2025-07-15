import datetime
import random
import string

from src.core import models


def gerar_sequencial_do_dia(db, store_id: int) -> int:
    hoje = datetime.date.today()
    inicio = datetime.datetime.combine(hoje, datetime.time.min)
    fim = datetime.datetime.combine(hoje, datetime.time.max)

    ultimo_pedido = (
        db.query(models.Order)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at >= inicio,
            models.Order.created_at <= fim,
        )
        .order_by(models.Order.sequential_id.desc())
        .first()
    )

    if ultimo_pedido:
        return ultimo_pedido.sequential_id + 1
    return 1





def generate_public_id(length=6):
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choices(caracteres, k=length))




def generate_unique_public_id(db, store_id, max_attempts=5):
    for _ in range(max_attempts):
        public_id = generate_public_id()
        existe = db.query(models.Order).filter_by(public_id=public_id, store_id=store_id).first()
        if not existe:
            return public_id
    raise Exception("Falha ao gerar código público único")
