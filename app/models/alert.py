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

    # async def create(self):
    #     db.session.add(self)
    #     db.session.commit()
    #     return self
    #
