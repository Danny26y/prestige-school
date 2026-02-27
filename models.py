from sqlalchemy import Column, String, Boolean, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime, timezone
from database import Base
import uuid

class User(Base):
    __tablename__ = "User"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    jamb_reg_no = Column(String, unique=True, index=True) # Critical for ICT verification
    passwordHash = Column(String)
    role = Column(String, default="student")
    isPasswordChanged = Column(Boolean, default=False)


class Admission(Base):
    __tablename__ = "Admission"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    userId = Column(String, ForeignKey("User.id"))
    fullName = Column(String)
    phoneNumber = Column(String)
    stateOfOrigin = Column(String)
    passportUrl = Column(String)  # Path to the uploaded photo
    resultsUrl = Column(String)   # Path to the uploaded PDF/Image
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED
    createdAt = Column(DateTime(timezone=True), server_default=func.now())


class News(Base):
    __tablename__ = "News"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String)  # e.g., "Admission", "Exam", "General"
    is_urgent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class VerifiedJAMB(Base):
    __tablename__ = "VerifiedJAMB"

    id = Column(Integer, primary_key=True, index=True)
    jamb_no = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))