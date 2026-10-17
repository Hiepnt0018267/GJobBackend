import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query, Session

from app.models.payment import (
    PaymentDisposition,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentProvider,
    PaymentTransaction,
)
from app.models.subscription import RecruiterSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User


class PaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_recruiter_for_update(self, recruiter_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == recruiter_id).with_for_update().first()

    def get_plan_for_update(self, plan_id: uuid.UUID) -> SubscriptionPlan | None:
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.id == plan_id)
            .with_for_update()
            .first()
        )

    def active_subscriptions_for_update(
        self, recruiter_id: uuid.UUID
    ) -> list[RecruiterSubscription]:
        return (
            self.db.query(RecruiterSubscription)
            .filter(
                RecruiterSubscription.recruiter_id == recruiter_id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(RecruiterSubscription.created_at, RecruiterSubscription.id)
            .with_for_update()
            .all()
        )

    def pending_orders_for_update(
        self, recruiter_id: uuid.UUID, plan_id: uuid.UUID
    ) -> list[PaymentOrder]:
        return (
            self.db.query(PaymentOrder)
            .filter(
                PaymentOrder.recruiter_id == recruiter_id,
                PaymentOrder.plan_id == plan_id,
                PaymentOrder.status == PaymentOrderStatus.PENDING,
            )
            .order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
            .with_for_update()
            .all()
        )

    def get_owned_order_for_update(
        self, order_id: uuid.UUID, recruiter_id: uuid.UUID
    ) -> PaymentOrder | None:
        return (
            self.db.query(PaymentOrder)
            .filter(PaymentOrder.id == order_id, PaymentOrder.recruiter_id == recruiter_id)
            .with_for_update()
            .first()
        )

    def get_order_by_code_for_update(self, payment_code: str) -> PaymentOrder | None:
        return (
            self.db.query(PaymentOrder)
            .filter(PaymentOrder.payment_code == payment_code)
            .with_for_update()
            .first()
        )

    def get_order_by_code(self, payment_code: str) -> PaymentOrder | None:
        return (
            self.db.query(PaymentOrder)
            .filter(PaymentOrder.payment_code == payment_code)
            .first()
        )

    def payment_code_exists(self, payment_code: str) -> bool:
        return (
            self.db.query(PaymentOrder.id)
            .filter(PaymentOrder.payment_code == payment_code)
            .first()
            is not None
        )

    def get_transaction(
        self, provider: PaymentProvider, provider_transaction_id: str
    ) -> PaymentTransaction | None:
        return (
            self.db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.provider == provider,
                PaymentTransaction.provider_transaction_id == provider_transaction_id,
            )
            .first()
        )

    def list_admin_transactions(
        self,
        *,
        search: str | None,
        disposition: PaymentDisposition | None,
        order_status: PaymentOrderStatus | None,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[PaymentTransaction, PaymentOrder | None, User | None]], int]:
        query = (
            self.db.query(PaymentTransaction, PaymentOrder, User)
            .outerjoin(PaymentOrder, PaymentTransaction.payment_order_id == PaymentOrder.id)
            .outerjoin(User, PaymentOrder.recruiter_id == User.id)
        )
        query = self._filter_admin_query(
            query,
            search=search,
            disposition=disposition,
            order_status=order_status,
            plan_code=plan_code,
            recruiter_id=recruiter_id,
            date_from=date_from,
            date_to=date_to,
            date_column=PaymentTransaction.transaction_date,
        )
        total = query.count()
        items = (
            query.order_by(
                PaymentTransaction.transaction_date.desc(), PaymentTransaction.id.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_admin_transaction(
        self, transaction_id: uuid.UUID
    ) -> tuple[PaymentTransaction, PaymentOrder | None, User | None] | None:
        return (
            self.db.query(PaymentTransaction, PaymentOrder, User)
            .outerjoin(PaymentOrder, PaymentTransaction.payment_order_id == PaymentOrder.id)
            .outerjoin(User, PaymentOrder.recruiter_id == User.id)
            .filter(PaymentTransaction.id == transaction_id)
            .first()
        )

    def list_admin_orders(
        self,
        *,
        search: str | None,
        order_status: PaymentOrderStatus | None,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[PaymentOrder, User]], int]:
        query = self.db.query(PaymentOrder, User).join(User, PaymentOrder.recruiter_id == User.id)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    PaymentOrder.payment_code.ilike(pattern),
                    PaymentOrder.plan_name_snapshot.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        if plan_code:
            query = query.filter(PaymentOrder.plan_code_snapshot == plan_code)
        if recruiter_id:
            query = query.filter(PaymentOrder.recruiter_id == recruiter_id)
        if date_from:
            query = query.filter(PaymentOrder.created_at >= date_from)
        if date_to:
            query = query.filter(PaymentOrder.created_at < date_to)
        query = self._filter_effective_order_status(query, order_status)
        total = query.count()
        items = (
            query.order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_admin_order(self, order_id: uuid.UUID) -> tuple[PaymentOrder, User] | None:
        return (
            self.db.query(PaymentOrder, User)
            .join(User, PaymentOrder.recruiter_id == User.id)
            .filter(PaymentOrder.id == order_id)
            .first()
        )

    def list_order_transactions(self, order_id: uuid.UUID) -> list[PaymentTransaction]:
        return (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.payment_order_id == order_id)
            .order_by(PaymentTransaction.transaction_date.desc(), PaymentTransaction.id.desc())
            .all()
        )

    def admin_payment_summary(
        self,
        *,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> dict[str, int]:
        transaction_query = self.db.query(PaymentTransaction).outerjoin(
            PaymentOrder, PaymentTransaction.payment_order_id == PaymentOrder.id
        )
        order_query = self.db.query(PaymentOrder)
        if plan_code:
            transaction_query = transaction_query.filter(
                PaymentOrder.plan_code_snapshot == plan_code
            )
            order_query = order_query.filter(PaymentOrder.plan_code_snapshot == plan_code)
        if recruiter_id:
            transaction_query = transaction_query.filter(PaymentOrder.recruiter_id == recruiter_id)
            order_query = order_query.filter(PaymentOrder.recruiter_id == recruiter_id)
        if date_from:
            transaction_query = transaction_query.filter(
                PaymentTransaction.transaction_date >= date_from
            )
            order_query = order_query.filter(PaymentOrder.created_at >= date_from)
        if date_to:
            transaction_query = transaction_query.filter(
                PaymentTransaction.transaction_date < date_to
            )
            order_query = order_query.filter(PaymentOrder.created_at < date_to)

        applied = transaction_query.filter(
            PaymentTransaction.disposition == PaymentDisposition.APPLIED
        )
        review = transaction_query.filter(
            PaymentTransaction.disposition.notin_(
                [PaymentDisposition.APPLIED, PaymentDisposition.OUTGOING_IGNORED]
            )
        )
        now = func.now()
        pending = order_query.filter(
            PaymentOrder.status == PaymentOrderStatus.PENDING,
            PaymentOrder.expires_at > now,
        )
        return {
            "successful_transactions": applied.count(),
            "revenue": int(applied.with_entities(func.coalesce(func.sum(PaymentTransaction.amount), 0)).scalar()),
            "needs_review": review.count(),
            "pending_orders": pending.count(),
            "paid_orders": order_query.filter(PaymentOrder.status == PaymentOrderStatus.PAID).count(),
        }

    @staticmethod
    def _filter_effective_order_status(
        query: Query, order_status: PaymentOrderStatus | None
    ) -> Query:
        now = func.now()
        if order_status == PaymentOrderStatus.EXPIRED:
            return query.filter(
                or_(
                    PaymentOrder.status == PaymentOrderStatus.EXPIRED,
                    and_(
                        PaymentOrder.status == PaymentOrderStatus.PENDING,
                        PaymentOrder.expires_at <= now,
                    ),
                )
            )
        if order_status == PaymentOrderStatus.PENDING:
            return query.filter(
                PaymentOrder.status == PaymentOrderStatus.PENDING,
                PaymentOrder.expires_at > now,
            )
        if order_status:
            return query.filter(PaymentOrder.status == order_status)
        return query

    @classmethod
    def _filter_admin_query(
        cls,
        query: Query,
        *,
        search: str | None,
        disposition: PaymentDisposition | None,
        order_status: PaymentOrderStatus | None,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        date_column: object,
    ) -> Query:
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    PaymentTransaction.provider_transaction_id.ilike(pattern),
                    PaymentTransaction.reference_code.ilike(pattern),
                    PaymentTransaction.content.ilike(pattern),
                    PaymentOrder.payment_code.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        if disposition:
            query = query.filter(PaymentTransaction.disposition == disposition)
        if plan_code:
            query = query.filter(PaymentOrder.plan_code_snapshot == plan_code)
        if recruiter_id:
            query = query.filter(PaymentOrder.recruiter_id == recruiter_id)
        if date_from:
            query = query.filter(date_column >= date_from)
        if date_to:
            query = query.filter(date_column < date_to)
        return cls._filter_effective_order_status(query, order_status)

    def add(self, instance: object) -> None:
        self.db.add(instance)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)
