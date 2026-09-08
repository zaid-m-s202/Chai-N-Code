"""Test configuration and fixtures."""

import os
import sys

# Set in-memory SQLite before importing app config
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, get_db
from app.api.deps import create_access_token, get_password_hash
from app.models.user import User
from app.main import app

# In-memory SQLite with static pool for fast, isolated tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def setup_sqlite_spatialite_mocks(dbapi_connection, connection_record):
    """Register mock SpatiaLite functions so GeoAlchemy2 DDL and DML run cleanly on SQLite."""
    dbapi_connection.create_function("RecoverGeometryColumn", 5, lambda *args: 1)
    dbapi_connection.create_function("DiscardGeometryColumn", 2, lambda *args: 1)
    dbapi_connection.create_function("CreateSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("DisableSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("CheckSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("InitSpatialMetaData", 0, lambda: 1)
    dbapi_connection.create_function("InitSpatialMetaData", 1, lambda *args: 1)
    def mock_geom_from_ewkt(val):
        if not val:
            return None
        try:
            from shapely import wkt, wkb
            wkt_str = str(val).split(";", 1)[-1]
            geom = wkt.loads(wkt_str)
            return wkb.dumps(geom, hex=True, srid=4326)
        except Exception:
            return val

    dbapi_connection.create_function("GeomFromEWKT", 1, mock_geom_from_ewkt)
    dbapi_connection.create_function("GeomFromWKB", 1, lambda val: val)
    dbapi_connection.create_function("AsEWKB", 1, lambda val: val)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """Create fresh tables for every test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a database session for each test."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def verifying_officer(db_session) -> User:
    """Seed and return a verifying officer user."""
    user = User(
        username="officer_sharma",
        password_hash=get_password_hash("securepass123"),
        role="VERIFYING_OFFICER",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def field_surveyor(db_session) -> User:
    """Seed and return a field surveyor user."""
    user = User(
        username="surveyor_patel",
        password_hash=get_password_hash("securepass123"),
        role="FIELD_SURVEYOR",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def officer_token(verifying_officer) -> str:
    """JWT token for verifying officer."""
    return create_access_token(data={"sub": verifying_officer.username, "role": verifying_officer.role})


@pytest.fixture
def surveyor_token(field_surveyor) -> str:
    """JWT token for field surveyor."""
    return create_access_token(data={"sub": field_surveyor.username, "role": field_surveyor.role})
