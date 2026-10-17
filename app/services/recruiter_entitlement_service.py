from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import (
    RecruiterFeature,
    RecruiterPlanCatalogItem,
    RecruiterPlanFeatureResponse,
    SubscriptionPlanResponse,
)
from app.services.subscription_service import SubscriptionService


FEATURE_LABELS: dict[RecruiterFeature, str] = {
    RecruiterFeature.AI_CANDIDATE_RANKING: "Xếp hạng ứng viên bằng AI",
    RecruiterFeature.DETAILED_CV_JD_MATCH: "Phân tích chi tiết CV và công việc",
}

PLAN_FEATURES: dict[str, frozenset[RecruiterFeature]] = {
    "FREE": frozenset(),
    "PRO_MONTHLY": frozenset(RecruiterFeature),
}


class RecruiterEntitlementService:
    """Single source of truth for recruiter AI feature access."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def for_plan_code(plan_code: str) -> dict[RecruiterFeature, bool]:
        included = PLAN_FEATURES.get(plan_code, frozenset())
        return {feature: feature in included for feature in RecruiterFeature}

    def for_recruiter(self, recruiter: User) -> dict[RecruiterFeature, bool]:
        subscription = SubscriptionService(self.db).get_for_recruiter(recruiter)
        return self.for_plan_code(subscription.effective_plan.code)

    def require_feature(self, recruiter: User, feature: RecruiterFeature) -> None:
        if self.for_recruiter(recruiter).get(feature, False):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_NOT_INCLUDED",
                "feature": feature.value,
                "message": "Tính năng này không có trong gói hiện tại.",
            },
        )

    def list_active_plan_catalog(self) -> list[RecruiterPlanCatalogItem]:
        plans = SubscriptionRepository(self.db).list_active_plans()
        catalog: list[RecruiterPlanCatalogItem] = []
        for plan in plans:
            base = SubscriptionPlanResponse.model_validate(plan).model_dump()
            entitlements = self.for_plan_code(plan.code)
            catalog.append(
                RecruiterPlanCatalogItem(
                    **base,
                    features=[
                        RecruiterPlanFeatureResponse(
                            key=feature,
                            label=FEATURE_LABELS[feature],
                            included=entitlements[feature],
                        )
                        for feature in RecruiterFeature
                    ],
                )
            )
        return catalog
