"""
Plain SQLAlchemy engine/session setup, deliberately kept independent of
Flask for now. Stage 3 (the Flask backend) will import `Base` and either
wrap this same engine or move to Flask-SQLAlchemy pointed at the same
tables — either way, the schema defined here doesn't change.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import Config

engine = create_engine(Config.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()
