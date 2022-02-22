from gino import Gino
from gino.schema import GinoSchemaVisitor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

db = Gino()
engine = create_engine(settings.POSTGRES_URI)
Session = sessionmaker()
Session.configure(bind=engine)


async def create_db():
    # Устанавливаем связь с базой данных
    await db.set_bind(settings.POSTGRES_URI)
    # await db.gino.create_all()

    db.gino: GinoSchemaVisitor
