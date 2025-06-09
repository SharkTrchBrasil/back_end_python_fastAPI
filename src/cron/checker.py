from datetime import datetime

from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.models import Coupon, Banner


def verificar_cupons_e_banners():
    db: Session = SessionLocal()  # <--- aqui você instancia

    agora = datetime.now()

    try:
        # CUPONS
        cupons_ativos = db.query(Coupon).filter(
            Coupon.start_date <= agora,
            Coupon.end_date >= agora,
            Coupon.available == False
        ).all()

        cupons_expirados = db.query(Coupon).filter(
            Coupon.end_date < agora,
            Coupon.available == True
        ).all()

        for c in cupons_ativos:
            c.available = True

        for c in cupons_expirados:
            c.available = False

        # BANNERS
        banners_ativos = db.query(Banner).filter(
            Banner.start_date <= agora,
            Banner.end_date >= agora,
            Banner.is_active == False
        ).all()

        banners_expirados = db.query(Banner).filter(
            Banner.end_date < agora,
            Banner.is_active == True
        ).all()

        for b in banners_ativos:
            b.is_active = True

        for b in banners_expirados:
            b.is_active = False

        db.commit()
        print(f"Cupons ativados: {len(cupons_ativos)}, expirados: {len(cupons_expirados)}")
        print(f"Banners ativados: {len(banners_ativos)}, expirados: {len(banners_expirados)}")

    except Exception as e:
        db.rollback()
        print("Erro ao verificar cupons/banners:", e)

    finally:
        db.close()


if __name__ == "__main__":
    verificar_cupons_e_banners()
