from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.database import Base

class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    is_cached = Column(Boolean, default=False)
    similarity_score = Column(Float, default=0.0)
    latency_ms = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)