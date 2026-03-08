from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Table, Float
from sqlalchemy.orm import relationship
import enum
from .database import Base

# Association tables for many-to-many relationships
book_genres = Table(
    'book_genres', Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id')),
    Column('genre_id', Integer, ForeignKey('genres.id'))
)

book_authors = Table(
    'book_authors', Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id')),
    Column('author_id', Integer, ForeignKey('authors.id'))
)

user_preferred_genres = Table(
    'user_preferred_genres', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('genre_id', Integer, ForeignKey('genres.id'))
)

user_preferred_authors = Table(
    'user_preferred_authors', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('author_id', Integer, ForeignKey('authors.id'))
)

class InteractionType(enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    NONE = "none"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    preferred_genres = relationship("Genre", secondary=user_preferred_genres)
    preferred_authors = relationship("Author", secondary=user_preferred_authors)
    interactions = relationship("Interaction", back_populates="user")

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    synopsis = Column(String)
    rating = Column(Float, default=0.0)
    
    genres = relationship("Genre", secondary=book_genres, back_populates="books")
    authors = relationship("Author", secondary=book_authors, back_populates="books")
    interactions = relationship("Interaction", back_populates="book")

class Genre(Base):
    __tablename__ = "genres"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    books = relationship("Book", secondary=book_genres, back_populates="genres")

class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    books = relationship("Book", secondary=book_authors, back_populates="authors")

class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    interaction_type = Column(String) # "like", "dislike"
    
    user = relationship("User", back_populates="interactions")
    book = relationship("Book", back_populates="interactions")
