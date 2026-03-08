import bcrypt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

from . import models, schemas, database, recommendation
from sqlalchemy.orm import selectinload

# Security config
SECRET_KEY = "your-secret-key" # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    await database.engine.dispose()

app = FastAPI(title="Book Recommender API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.preferred_genres), selectinload(models.User.preferred_authors))
        .filter(models.User.username == token_data.username)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

@app.post("/signup", response_model=schemas.User)
async def signup(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(select(models.User).filter(models.User.username == user.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    
    # Eager reload
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.preferred_genres), selectinload(models.User.preferred_authors))
        .filter(models.User.id == db_user.id)
    )
    return result.scalar_one()

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(select(models.User).filter(models.User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.post("/users/preferences", response_model=schemas.User)
async def update_preferences(prefs: schemas.UserCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    # Re-fetch user attached to this session with collections loaded
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.preferred_genres), selectinload(models.User.preferred_authors))
        .filter(models.User.id == current_user.id)
    )
    user = result.scalar_one()

    if prefs.preferred_genre_ids is not None:
        result = await db.execute(select(models.Genre).filter(models.Genre.id.in_(prefs.preferred_genre_ids)))
        user.preferred_genres = result.scalars().all()
    
    if prefs.preferred_author_ids is not None:
        result = await db.execute(select(models.Author).filter(models.Author.id.in_(prefs.preferred_author_ids)))
        user.preferred_authors = result.scalars().all()

    await db.commit()
    
    # Eager reload for response
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.preferred_genres), selectinload(models.User.preferred_authors))
        .filter(models.User.id == user.id)
    )
    return result.scalar_one()

@app.get("/books/", response_model=List[schemas.Book])
async def read_books(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(select(models.Book).options(selectinload(models.Book.genres), selectinload(models.Book.authors)).offset(skip).limit(limit))
    return result.scalars().all()

@app.post("/interactions/", response_model=schemas.Interaction)
async def create_interaction(interaction: schemas.InteractionCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    db_interaction = models.Interaction(
        user_id=current_user.id,
        book_id=interaction.book_id,
        interaction_type=interaction.interaction_type
    )
    db.add(db_interaction)
    await db.flush()
    interaction_id = db_interaction.id
    await db.commit()
    
    result = await db.execute(select(models.Interaction).filter(models.Interaction.id == interaction_id))
    return result.scalar_one()

@app.get("/recommendations/", response_model=List[schemas.Book])
async def get_recommendations_for_user(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    # 1. Re-fetch user with eager loaded relationships
    result = await db.execute(
        select(models.User)
        .options(
            selectinload(models.User.preferred_genres),
            selectinload(models.User.preferred_authors),
            selectinload(models.User.interactions).joinedload(models.Interaction.book)
        )
        .filter(models.User.id == current_user.id)
    )
    user = result.scalar_one()

    # 2. Prepare preference data
    pref_genres = [g.name for g in user.preferred_genres]
    pref_authors = [a.name for a in user.preferred_authors]
    interactions = [{"title": i.book.title, "type": i.interaction_type} for i in user.interactions]

    # 3. Calculate vector
    try:
        user_vector = recommendation.calculate_user_vector(pref_genres, pref_authors, interactions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate user vector: {str(e)}")

    # 4. Query ChromaDB
    try:
        exclude_ids = [str(i.book_id) for i in user.interactions]
        results = recommendation.get_recommendations(user_vector, n_results=5, exclude_ids=exclude_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query recommendations: {str(e)}")
    
    if not results or not results.get('ids') or not results['ids'][0]:
        return []

    # 5. Fetch full book details
    book_ids = [int(id) for id in results['ids'][0]]
    result = await db.execute(
        select(models.Book)
        .options(selectinload(models.Book.genres), selectinload(models.Book.authors))
        .filter(models.Book.id.in_(book_ids))
    )
    recommended_books = result.scalars().all()
    
    book_map = {b.id: b for b in recommended_books}
    return [book_map[bid] for bid in book_ids if bid in book_map]
