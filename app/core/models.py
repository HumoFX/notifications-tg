from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, \
    String, Table, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("(lang)::text = ANY ((ARRAY['ru'::character varying, 'uz'::character varying])::text[])"),
    )

    user_id = Column(BigInteger, primary_key=True, server_default=text("nextval('users_user_id_seq'::regclass)"))
    first_name = Column(String(64))
    last_name = Column(String(64))
    username = Column(String(32))
    region_id = Column(ForeignKey('regions.id'))
    notification = Column(Boolean, nullable=False)
    active = Column(Boolean, nullable=False)
    created_at = Column(DateTime)
    lang = Column(String(2), nullable=False)
    data = Column(JSON)
