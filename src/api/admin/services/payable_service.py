# src/api/admin/services/payable_service.py

from sqlalchemy import func, case
from sqlalchemy.orm import Session
from src.api.schemas.analytics.dashboard import DashboardMetrics
from src.core.models import StorePayable, Store
from src.api.schemas.store.store_payable import PayableCreate, PayableUpdate, PayableResponse
from src.core.utils.enums import PayableStatus
# O import de 'timezone' já está aqui, o que é ótimo.
from datetime import date, datetime, timezone


class PayableService:
    def get_payable_by_id(self, db: Session, payable_id: int, store_id: int) -> StorePayable | None:
        return db.query(StorePayable).filter(
            StorePayable.id == payable_id,
            StorePayable.store_id == store_id
        ).first()

    def list_payables(self, db: Session, store_id: int, status: PayableStatus | None, supplier_id: int | None, start_date: date | None, end_date: date | None, skip: int = 0, limit: int = 100) -> list[StorePayable]:
        query = db.query(StorePayable).filter(StorePayable.store_id == store_id)
        if status:
            query = query.filter(StorePayable.status == status)
        # ... outros filtros ...
        return query.order_by(StorePayable.due_date.asc()).offset(skip).limit(limit).all()

    def create_payable(self, db: Session, store: Store, payload: PayableCreate) -> StorePayable:
        payable = StorePayable(**payload.model_dump(exclude={"recurrence"}), store_id=store.id)
        db.add(payable)
        db.commit()
        db.refresh(payable)
        return payable

    def update_payable(self, db: Session, payable: StorePayable, payload: PayableUpdate) -> StorePayable:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(payable, key, value)
        db.commit()
        db.refresh(payable)
        return payable

    def delete_payable(self, db: Session, payable: StorePayable):
        db.delete(payable)
        db.commit()

    def mark_as_paid(self, db: Session, payable: StorePayable) -> StorePayable:
        if payable.status != PayableStatus.paid:
            payable.status = PayableStatus.paid
            # ✅ CORREÇÃO APLICADA
            # Substituímos date.today() pela versão com fuso horário para consistência.
            payable.payment_date = datetime.now(timezone.utc).date()
            db.commit()
            db.refresh(payable)
        return payable

    def get_payables_metrics(self, db: Session, store_id: int) -> DashboardMetrics:
        # Esta parte do seu código já estava correta!
        today = datetime.now(timezone.utc).date()
        start_of_month = today.replace(day=1)

        metrics_query = db.query(
            func.sum(case((PayableStatus.pending == StorePayable.status, StorePayable.amount), else_=0)).label("total_pending"),
            func.sum(case((PayableStatus.overdue == StorePayable.status, StorePayable.amount), else_=0)).label("total_overdue"),
            func.sum(case((StorePayable.payment_date >= start_of_month, StorePayable.amount), else_=0)).label("total_paid_month"),
            func.count(case((PayableStatus.pending == StorePayable.status, StorePayable.id))).label("pending_count"),
            func.count(case((PayableStatus.overdue == StorePayable.status, StorePayable.id))).label("overdue_count"),
        ).filter(StorePayable.store_id == store_id).one()

        next_dues = db.query(StorePayable).filter(
            StorePayable.store_id == store_id,
            StorePayable.status == PayableStatus.pending,
            StorePayable.due_date >= today
        ).order_by(StorePayable.due_date.asc()).limit(5).all()

        return DashboardMetrics(
            total_pending=metrics_query.total_pending or 0,
            total_overdue=metrics_query.total_overdue or 0,
            total_paid_month=metrics_query.total_paid_month or 0,
            pending_count=metrics_query.pending_count or 0,
            overdue_count=metrics_query.overdue_count or 0,
            next_due_payables=[PayableResponse.model_validate(p) for p in next_dues],
        )


payable_service = PayableService()