from datetime import datetime
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.core.models import Coupon, Banner


def verificar_cupons_e_banners():
    agora = datetime.now()  # Use UTC para evitar problemas de timezone

    db: Session = SessionLocal()  # Abre sessão com o banco

    try:
        # Cupons que devem estar disponíveis agora
        cupons_ativos = db.query(Coupon).filter(
            Coupon.start_date <= agora,
            Coupon.end_date >= agora,
            Coupon.available == False
        ).all()

        # Cupons expirados que ainda estão marcados como disponíveis
        cupons_expirados = db.query(Coupon).filter(
            Coupon.end_date < agora,
            Coupon.available == True
        ).all()

        for cupom in cupons_ativos:
            cupom.available = True

        for cupom in cupons_expirados:
            cupom.available = False

        # Banners que devem estar ativos agora
        banners_ativos = db.query(Banner).filter(
            Banner.start_date <= agora,
            Banner.end_date >= agora,
            Banner.is_active == False
        ).all()

        # Banners expirados que ainda estão ativos
        banners_expirados = db.query(Banner).filter(
            Banner.end_date < agora,
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
