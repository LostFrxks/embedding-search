from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, session



DATABASE_URL = "postgresql+psycopg2://postgres:root@localhost:5432/mbank_lalafo"

engine = create_engine(
    DATABASE_URL, 
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  

    Base.metadata.create_all(bind=engine)