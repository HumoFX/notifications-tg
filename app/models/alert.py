from sqlalchemy import (Column, Integer, String, Sequence,
                        Numeric, ForeignKey, Boolean, TIMESTAMP,
                        CheckConstraint, Date, BigInteger, JSON, and_)

from app.core.database import db
from datetime import datetime


class FaceIDAlert(db.Model):
    __tablename__ = 'face_id_alert'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False)
    type = Column(String(20), nullable=True, default=None)
    topic = Column(Integer, nullable=True, default=None)
    pinfl = Column(String(14), nullable=True, default=None)
    error_code = Column(Integer, nullable=True, default=None)
    error_message = Column(String(512), nullable=True, default=None)
    created_at = Column(TIMESTAMP, default=datetime.now, nullable=False)
    face_id_admin = Column(BigInteger, ForeignKey("FaceIdAdmin.user_id"), nullable=True)

    # async def create(self):
    #     db.session.add(self)
    #     db.session.commit()
    #     return self
    #


class FaceIdAdmin(db.Model):
    __tablename__ = 'face_id_admin'
    user_id = Column(BigInteger, primary_key=True)
    first_name = Column(String(64))
    last_name = Column(String(64))
    username = Column(String(32))
    data = Column(JSON, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, default=datetime.now())
