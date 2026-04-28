import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobPlatform(Base):
    __tablename__ = "job_platforms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    jobs = relationship("Job", back_populates="platform")
    credentials = relationship("PlatformCredential", back_populates="platform")


class PlatformCredential(Base):
    __tablename__ = "platform_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "platform_id", name="uq_user_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_platforms.id"), nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(255))
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary)
    cookies_path: Mapped[str | None] = mapped_column(String(500))
    session_data: Mapped[dict | None] = mapped_column(JSONB)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="platform_credentials")
    platform = relationship("JobPlatform", back_populates="credentials")
