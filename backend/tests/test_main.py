import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import Base, get_db
from app import models, schemas

# Use a test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="module")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Pre-seed genres and authors for testing
    async with TestSessionLocal() as db:
        genre1 = models.Genre(name="Sci-Fi")
        author1 = models.Author(name="Frank Herbert")
        book1 = models.Book(title="Dune", synopsis="Desert planet", rating=4.8)
        book1.genres = [genre1]
        book1.authors = [author1]
        db.add_all([genre1, author1, book1])
        await db.commit()
        
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_signup(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/signup", json={
            "username": "testuser",
            "password": "testpassword"
        })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

@pytest.mark.asyncio
async def test_signup_duplicate(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/signup", json={
            "username": "testuser",
            "password": "anotherpassword"
        })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_success(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/token", data={
            "username": "testuser",
            "password": "testpassword"
        })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/token", data={
            "username": "testuser",
            "password": "wrongpassword"
        })
    assert response.status_code == 401
    assert "Incorrect username" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_me(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Get token
        login_res = await ac.post("/token", data={"username": "testuser", "password": "testpassword"})
        token = login_res.json()["access_token"]
        
        # Get profile
        response = await ac.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

@pytest.mark.asyncio
async def test_update_preferences(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_res = await ac.post("/token", data={"username": "testuser", "password": "testpassword"})
        token = login_res.json()["access_token"]
        
        response = await ac.post("/users/preferences", 
            json={"username": "testuser", "password": "", "preferred_genre_ids": [1], "preferred_author_ids": [1]},
            headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200
    assert len(response.json()["preferred_genres"]) == 1

@pytest.mark.asyncio
async def test_recommendations_protected(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Without token
        res_no_auth = await ac.get("/recommendations/")
        assert res_no_auth.status_code == 401
        
        # With token
        login_res = await ac.post("/token", data={"username": "testuser", "password": "testpassword"})
        token = login_res.json()["access_token"]
        
        with patch("app.recommendation.calculate_user_vector") as mock_calc:
            with patch("app.recommendation.get_recommendations") as mock_get_rec:
                mock_calc.return_value = [0.1] * 768
                mock_get_rec.return_value = {"ids": [["1"]]}
                
                response = await ac.get("/recommendations/", headers={"Authorization": f"Bearer {token}"})
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == 1
