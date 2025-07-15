from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException


from src.api.admin.schemas.subscription import CreateStoreSubscription
from src.api.shared_schemas.store import Roles
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore
from src.core.models import Store
from src.api.app.services import payment as payment_services

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")


@router.post("")
def new_subscription(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
    subscription: CreateStoreSubscription,
):
    plan = db.query(models.SubscriptionPlan).filter_by(id=subscription.plan_id, available=True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found/available")

    previous_subscription = db.query(models.StoreSubscription).filter(models.StoreSubscription.status.in_(['active', 'new_charge']), models.StoreSubscription.store_id == store.id).first()

    if plan.price > 0:
        efi_payment_plans = payment_services.list_plans(plan.name)
        efi_payment_plan = next(iter(p for p in efi_payment_plans if p['interval'] == plan.interval
                                     and p['repeats'] == plan.repeats), None)

        if not efi_payment_plan:
            efi_payment_plan = payment_services.create_plan(plan.name, plan.repeats, plan.interval)

        subscription = payment_services.create_subscription(efi_payment_plan['plan_id'], plan,
                                                            subscription.card.payment_token,
                                                            subscription.customer, subscription.address)

        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            subscription_id=subscription['subscription_id'],
            status=subscription['status'],
        )
    else:
        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            subscription_id=None,
            status='active',
        )

    if previous_subscription.subscription_id:
        payment_services.cancel_subscription(previous_subscription.subscription_id)

    db.add(db_subscription)
    db.commit()

    return db_subscription