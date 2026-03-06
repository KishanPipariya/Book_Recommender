from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class GenreBase(BaseModel):
    name: str

class GenreCreate(GenreBase):
    pass

class Genre(GenreBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AuthorBase(BaseModel):
    name: str

class AuthorCreate(AuthorBase):
    pass

class Author(AuthorBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class BookBase(BaseModel):
    title: str
    synopsis: str
    rating: float = 0.0

class BookCreate(BookBase):
    genre_ids: List[int]
    author_ids: List[int]

class Book(BookBase):
    id: int
    genres: List[Genre]
    authors: List[Author]
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    preferred_genre_ids: List[int]
    preferred_author_ids: List[int]

class User(UserBase):
    id: int
    preferred_genres: List[Genre]
    preferred_authors: List[Author]
    model_config = ConfigDict(from_attributes=True)

class InteractionCreate(BaseModel):
    book_id: int
    interaction_type: str # "like", "dislike"

class Interaction(InteractionCreate):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)
