from sqlalchemy import (Column, Integer, String, Sequence,
                        Numeric, ForeignKey, Boolean, TIMESTAMP,
                        CheckConstraint, Date, BigInteger, JSON, and_)

from app.core.database import db
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    first_name = Column(String(64))
    last_name = Column(String(64))
    username = Column(String(32))

    region_id = Column(Integer, ForeignKey("regions.id"))
    notification = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, default=datetime.now())
    lang = Column(String(2), CheckConstraint("lang in ('ru', 'uz')"), nullable=False)
    data = Column(JSON, nullable=True)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._user_views = list()

    @property
    def user_views(self):
        return self._user_views

    @user_views.setter
    def add_views(self, user_view):
        self._user_views.add(user_view)

    @property
    def token(self):
        token = ''
        print(f"data = {self.data}")
        if self.data and self.data.get('client'):
            token = self.data['client'].get('token')
        return token

    @property
    def refresh_token(self):
        token = ''
        print(f"data = {self.data}")
        if self.data and self.data.get('client'):
            token = self.data['client'].get('refreshToken')
        return token

    @property
    def client_customer_id(self):
        customer_id = None
        if self.data and self.data.get('client'):
            customer_id = self.data['client'].get('customerId')

        print(customer_id)
        return customer_id

    @property
    def non_client_customer_id(self):
        customer_id = None
        if self.data and self.data.get('customer_id'):
            customer_id = self.data['customer_id']
        return customer_id


class UserCustomer(db.Model):
    __tablename__ = "user_customer"
    customer_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    token = Column(String(64))
    refresh_token = Column(String(64))
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, default=datetime.now())

    def __init__(self, **kw):
        super().__init__(**kw)
        self._user = None

    @property
    def user(self):
        return self._user

    @user.setter
    def set_user(self, user):
        self._user = user
