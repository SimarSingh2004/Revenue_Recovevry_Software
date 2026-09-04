from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, func, CheckConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RecoveryEvent(Base):
    __tablename__ = "recovery_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    failure_code: Mapped[str] = mapped_column(String, nullable=True)
    failure_category: Mapped[str] = mapped_column(String, nullable=True)
    payment_method: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recovery_case: Mapped["RecoveryCase | None"] = relationship(
        back_populates="recovery_event"
    )

    __table_args__ = (CheckConstraint(
        "attempt_number >= 1",
        name="ck_recovery_events_attempt_number_positive",
    ),)


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("recovery_events.event_id"), unique=True, nullable=False
    )
    payment_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    recovery_event: Mapped[RecoveryEvent] = relationship(back_populates="recovery_case")


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    payment_id: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_method: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__=(
        Index(
            "ix_payment_history_customer_merchant_occurred",
            "customer_id",
            "merchant_id",
            "occurred_at",
        ),
    )


class MerchantContext(Base):
    __tablename__ = "merchant_context"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True)
    recovery_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allowed_recovery_actions: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False
    )
    merchant_segment: Mapped[str] = mapped_column(String, nullable=False)
    retry_cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MerchantHistory(Base):
    __tablename__ = "merchant_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    intervention_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__=(
        Index(
            "ix_merchant_history_merchant_case_occurred",
            "merchant_id",
            "case_id",
            "occurred_at",
        ),
    )


class RecoveryLearningMemory(Base):
    __tablename__ = "recovery_learning_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    failure_code: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_method: Mapped[str] = mapped_column(String, nullable=False)
    payment_attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    llm_p_pred: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    gt_p: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    baseline_p: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    net_recovery_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    financial_impact: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "financial_impact IN ('POSITIVE_RECOVERY', 'FEE_LOSS', 'NO_RECOVERY_ATTEMPT')",
            name="ck_recovery_learning_memory_financial_impact",
        ),
        Index(
            "ix_recovery_memory_failure_code_payment_method",
            "failure_code",
            "payment_method",
        ),
        Index(
            "ix_recovery_memory_failure_category",
            "failure_category",
        ),
    )
