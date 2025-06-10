from datetime import datetime
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.core.models import Coupon, Banner


def verificar_cupons_e_banners():
    agora = datetime.now()  # Idealmente use datetime.utcnow() se seu banco salva em UTC

    db: Session = SessionLocal()

    try:
        # Ativar cupons válidos dentro do intervalo
        cupons_ativos = db.query(Coupon).filter(
            Coupon.start_date <= agora,
            Coupon.end_date >= agora,
            Coupon.end_date > Coupon.start_date,
            Coupon.available == False
        ).all()

        # Desativar cupons expirados (após o fim)
        cupons_expirados = db.query(Coupon).filter(
            Coupon.end_date < agora,
            Coupon.end_date > Coupon.start_date,
            Coupon.available == True
        ).all()

        for cupom in cupons_ativos:
            cupom.available = True

        for cupom in cupons_expirados:
            cupom.available = False

        # Ativar banners válidos dentro do intervalo
        banners_ativos = db.query(Banner).filter(
            Banner.start_date <= agora,
            Banner.end_date >= agora,
            Banner.end_date > Banner.start_date,
            Banner.is_active == False
        ).all()

        # Desativar banners expirados (após o fim)
        banners_expirados = db.query(Banner).filter(
            Banner.end_date < agora,
            Banner.end_date > Banner.start_date,
            Banner.is_active == True
        ).all()

        for banner in banners_ativos:
            banner.is_active = True

        for banner in banners_expirados:
            banner.is_active = False

        db.commit()

        print(f"[{agora.isoformat()}] Cupons ativados: {len(cupons_ativos)}, expirados: {len(cupons_expirados)}")
        print(f"[{agora.isoformat()}] Banners ativados: {len(banners_ativos)}, expirados: {len(banners_expirados)}")

    except Exception as e:
        db.rollback()
        print(f"[{agora.isoformat()}] Erro ao verificar cupons/banners: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    verificar_cupons_e_banners()
