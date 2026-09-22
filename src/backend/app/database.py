"""SQLAlchemy engine, session factory and FastAPI dependency."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker

from app.config import settings


def setup_sqlite_mocks(dbapi_connection, connection_record):
    """Register mock SpatiaLite functions so GeoAlchemy2 runs cleanly on SQLite."""
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


engine_kwargs = {"pool_pre_ping": True}
if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Tuned for persistent Render web services connecting via Supabase Session Pooler
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,  # recycle connections every 30m to prevent idle disconnects
        "pool_timeout": 30,    # maximum wait time in seconds to obtain a connection from the pool
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)


if "sqlite" in settings.DATABASE_URL:
    event.listen(engine, "connect", setup_sqlite_mocks)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
