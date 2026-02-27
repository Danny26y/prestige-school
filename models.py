from sqlalchemy import Column, String, Boolean
from database import Base
import uuid

class User(Base):
    __tablename__ = "User"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    passwordHash = Column(String)
    role = Column(String, default="STUDENT") # Values: STUDENT, ADMIN, SUPER_ADMIN
    isPasswordChanged = Column(Boolean, default=False)

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Admission(Base):
    __tablename__ = "Admission"

    id = Column(String, primary_key=True, index=True)
    userId = Column(String, ForeignKey("User.id"))
    fullName = Column(String)
    phoneNumber = Column(String)
    stateOfOrigin = Column(String)
    passportUrl = Column(String)  # Path to the uploaded photo
    resultsUrl = Column(String)   # Path to the uploaded PDF/Image
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED
    createdAt = Column(DateTime(timezone=True), server_default=func.now())