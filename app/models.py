from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func 
from app.db import Base

class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    url = Column(String, unique=True, index=True)
    city = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    embedding = Column(Text, nullable=True)