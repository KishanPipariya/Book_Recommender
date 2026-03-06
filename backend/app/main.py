from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from contextlib import asynccontextmanager

from . import models, schemas, database, recommendation
from sqlalchemy.orm import selectinload

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    # Shutdown: Clean up resources if needed
    await database.engine.dispose()

app = FastAPI(title="Book Recommender API", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Book Recommender API"}

@app.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    db_user = models.User(username=user.username)
    
    # Fetch genres and authors to link
    if user.preferred_genre_ids:
        result = await db.execute(select(models.Genre).filter(models.Genre.id.in_(user.preferred_genre_ids)))
        db_user.preferred_genres = result.scalars().all()
    
    if user.preferred_author_ids:
        result = await db.execute(select(models.Author).filter(models.Author.id.in_(user.preferred_author_ids)))
        db_user.preferred_authors = result.scalars().all()

    db.add(db_user)
    await db.flush() # Ensure ID is generated
    user_id = db_user.id
    await db.commit()
    
    # Re-fetch with eager loading to avoid lazy loading issues in response serialization
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.preferred_genres), selectinload(models.User.preferred_authors))
        .filter(models.User.id == user_id)
    )
    db_user = result.scalar_one()
    return db_user

@app.get("/books/", response_model=List[schemas.Book])
async def read_books(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(select(models.Book).options(selectinload(models.Book.genres), selectinload(models.Book.authors)).offset(skip).limit(limit))
    return result.scalars().all()

@app.post("/interactions/", response_model=schemas.Interaction)
async def create_interaction(user_id: int, interaction: schemas.InteractionCreate, db: AsyncSession = Depends(database.get_db)):
    db_interaction = models.Interaction(
        user_id=user_id,
        book_id=interaction.book_id,
        interaction_type=interaction.interaction_type
    )
    db.add(db_interaction)
    await db.commit()
    await db.refresh(db_interaction)
    return db_interaction

@app.get("/recommendations/{user_id}", response_model=List[schemas.Book])
async def get_recommendations_for_user(user_id: int, db: AsyncSession = Depends(database.get_db)):
    # 1. Fetch user, their preferences and interactions
    result = await db.execute(
        select(models.User)
        .options(
            selectinload(models.User.preferred_genres),
            selectinload(models.User.preferred_authors),
            selectinload(models.User.interactions).joinedload(models.Interaction.book)
        )
        .filter(models.User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Prepare preference data for embedding
    pref_genres = [g.name for g in user.preferred_genres]
    pref_authors = [a.name for a in user.preferred_authors]
    interactions = [{"title": i.book.title, "type": i.interaction_type} for i in user.interactions]

    # 3. Calculate user preference vector
    try:
        user_vector = recommendation.calculate_user_vector(pref_genres, pref_authors, interactions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate user vector: {str(e)}")

    # 4. Get recommendations from ChromaDB
    exclude_ids = [str(i.book_id) for i in user.interactions]
    results = recommendation.get_recommendations(user_vector, n_results=5, exclude_ids=exclude_ids)
    
    if not results or not results['ids']:
        return []

    # 5. Fetch full book details from DB for recommended IDs
    book_ids = [int(id) for id in results['ids'][0]]
    result = await db.execute(
        select(models.Book)
        .options(selectinload(models.Book.genres), selectinload(models.Book.authors))
        .filter(models.Book.id.in_(book_ids))
    )
    recommended_books = result.scalars().all()
    
    # Sort by the order returned by ChromaDB
    book_map = {b.id: b for b in recommended_books}
    return [book_map[bid] for bid in book_ids if bid in book_map]
