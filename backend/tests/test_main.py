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
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession)

@pytest_asyncio.fixture(scope="module")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Pre-seed genres and authors for testing
    async with TestSessionLocal() as db:
        genre1 = models.Genre(name="Sci-Fi")
        genre2 = models.Genre(name="Fantasy")
        author1 = models.Author(name="Frank Herbert")
        author2 = models.Author(name="J.R.R. Tolkien")
        
        book1 = models.Book(title="Dune", synopsis="Desert planet", rating=4.8)
        book1.genres = [genre1]
        book1.authors = [author1]
        
        book2 = models.Book(title="The Hobbit", synopsis="Small person adventure", rating=4.9)
        book2.genres = [genre2]
        book2.authors = [author2]
        
        db.add_all([genre1, genre2, author1, author2, book1, book2])
        await db.commit()
        
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_root(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Book Recommender API"}

@pytest.mark.asyncio
async def test_create_user(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/users/", json={
            "username": "newuser",
            "preferred_genre_ids": [1],
            "preferred_author_ids": [1]
        })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert len(data["preferred_genres"]) > 0

@pytest.mark.asyncio
async def test_read_books(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/books/")
    assert response.status_code == 200
    books = response.json()
    assert len(books) >= 2
    assert books[0]["title"] == "Dune"

@pytest.mark.asyncio
async def test_recommendations_success(setup_db):
    # Mocking the recommendation logic to avoid real API calls
    with patch("app.recommendation.calculate_user_vector") as mock_calc:
        with patch("app.recommendation.get_recommendations") as mock_get_rec:
            mock_calc.return_value = [0.1] * 768 # Dummy vector
            mock_get_rec.return_value = {
                "ids": [["1", "2"]]
            }
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                # We know user 1 was created in previous test or we can create one
                response = await ac.get("/recommendations/1")
            
            assert response.status_code == 200
            recs = response.json()
            assert len(recs) == 2
            assert recs[0]["id"] == 1
            assert recs[1]["id"] == 2

@pytest.mark.asyncio
async def test_interactions_and_exclusion(setup_db):
    # 1. User 1 likes Book 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/interactions/?user_id=1", json={
            "book_id": 1,
            "interaction_type": "like"
        })
    
    # 2. Check that Book 1 is excluded from next recommendations call
    with patch("app.recommendation.calculate_user_vector") as mock_calc:
        with patch("app.recommendation.get_recommendations") as mock_get_rec:
            mock_calc.return_value = [0.1] * 768
            mock_get_rec.return_value = {"ids": [["2"]]}
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/recommendations/1")
            
            # Verify mock_get_rec was called with exclude_ids=["1"]
            mock_get_rec.assert_called_once()
            args, kwargs = mock_get_rec.call_args
            assert "1" in kwargs["exclude_ids"]
            
            assert response.status_code == 200
            recs = response.json()
            assert len(recs) == 1
            assert recs[0]["id"] == 2

@pytest.mark.asyncio
async def test_create_dislike_interaction(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/interactions/?user_id=1", json={
            "book_id": 2,
            "interaction_type": "dislike"
        })
    assert response.status_code == 200
    assert response.json()["interaction_type"] == "dislike"
