"""SQLAlchemy ORM Models"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, DECIMAL, Enum, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    provider_name = Column(String(255))
    provider_url = Column(String(500))
    version = Column(String(50))
    endpoint_url = Column(String(500))
    agent_card_url = Column(String(500))
    homepage_url = Column(String(500))
    github_url = Column(String(500))
    skills = Column(JSON)
    input_modes = Column(JSON)
    output_modes = Column(JSON)
    supported_protocols = Column(JSON)
    languages = Column(JSON)
    category = Column(String(100))
    tags = Column(JSON)
    pricing_model = Column(String(50))
    trust_score = Column(DECIMAL(5, 2), default=0)
    is_verified = Column(Boolean, default=False)
    verification_method = Column(String(50))
    is_active = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime)
    heartbeat_failures = Column(Integer, default=0)
    registration_source = Column(String(50))
    registered_by = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AgentReview(Base):
    __tablename__ = "agent_reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"))
    reviewer_type = Column(String(10), default="human")
    reviewer_name = Column(String(255))
    reviewer_agent_uuid = Column(String(36))
    rating = Column(Integer)
    comment = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class HeartbeatLog(Base):
    __tablename__ = "heartbeat_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"))
    status = Column(String(10))
    response_time_ms = Column(Integer)
    checked_at = Column(DateTime, server_default=func.now())
