import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.auth.security import hash_password, create_access_token

# Test database in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
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
def admin_user(db_session):
    admin = User(
        email="test_admin@digitalomr.edu",
        full_name="Test Administrator",
        hashed_password=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def teacher_user(db_session):
    teacher = User(
        email="test_teacher@digitalomr.edu",
        full_name="Test Teacher 1",
        hashed_password=hash_password("TeacherPass123!"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return teacher


@pytest.fixture
def second_teacher(db_session):
    teacher = User(
        email="other_teacher@digitalomr.edu",
        full_name="Test Teacher 2",
        hashed_password=hash_password("TeacherPass123!"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return teacher


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token(
        data={"sub": str(admin_user.id), "email": admin_user.email, "role": "ADMIN"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def teacher_headers(teacher_user):
    token = create_access_token(
        data={"sub": str(teacher_user.id), "email": teacher_user.email, "role": "TEACHER"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_teacher_headers(second_teacher):
    token = create_access_token(
        data={"sub": str(second_teacher.id), "email": second_teacher.email, "role": "TEACHER"}
    )
    return {"Authorization": f"Bearer {token}"}
