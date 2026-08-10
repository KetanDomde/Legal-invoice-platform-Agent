import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_invoiceiq.db"


engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False
    },
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(
        bind=engine
    )

    yield engine

    Base.metadata.drop_all(
        bind=engine
    )


@pytest.fixture()
def db(db_engine):

    connection = db_engine.connect()

    transaction = connection.begin()

    session = TestingSessionLocal(
        bind=connection
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[
        get_db
    ] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()