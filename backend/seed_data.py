import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, database, recommendation

async def seed():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)

    async with database.AsyncSessionLocal() as db:
        # Create Genres
        genres = [
            models.Genre(name="Sci-Fi"),
            models.Genre(name="Fantasy"),
            models.Genre(name="Mystery"),
            models.Genre(name="Non-Fiction"),
            models.Genre(name="Thriller")
        ]
        db.add_all(genres)
        await db.commit()
        
        # Create Authors
        authors = [
            models.Author(name="Frank Herbert"),
            models.Author(name="J.R.R. Tolkien"),
            models.Author(name="Agatha Christie"),
            models.Author(name="Stephen King"),
            models.Author(name="Yuval Noah Harari")
        ]
        db.add_all(authors)
        await db.commit()

        # Fetch them back to use
        await db.refresh(genres[0]) # Sci-Fi
        await db.refresh(genres[1]) # Fantasy
        await db.refresh(genres[2]) # Mystery
        await db.refresh(authors[0]) # Herbert
        await db.refresh(authors[1]) # Tolkien
        await db.refresh(authors[2]) # Christie

        # Create Books
        books = [
            models.Book(
                title="Dune",
                synopsis="A story of political intrigue and survival on the desert planet Arrakis.",
                rating=4.8,
                genres=[genres[0]],
                authors=[authors[0]]
            ),
            models.Book(
                title="The Hobbit",
                synopsis="Bilbo Baggins' unexpected adventure across Middle-earth.",
                rating=4.9,
                genres=[genres[1]],
                authors=[authors[1]]
            ),
            models.Book(
                title="Murder on the Orient Express",
                synopsis="Hercule Poirot investigates a murder on a stranded train.",
                rating=4.5,
                genres=[genres[2]],
                authors=[authors[2]]
            ),
            models.Book(
                title="Project Hail Mary",
                synopsis="A lone astronaut must save Earth from an extinction-level threat.",
                rating=4.7,
                genres=[genres[0]],
                authors=[models.Author(name="Andy Weir")]
            )
        ]
        db.add_all(books)
        await db.commit()
        
        # Add to Vector DB
        for book in books:
            recommendation.add_book_to_vector_db(
                book_id=book.id,
                title=book.title,
                synopsis=book.synopsis,
                genres=[g.name for g in book.genres],
                authors=[a.name for a in book.authors]
            )
        
        print("Database and Vector DB seeded!")

if __name__ == "__main__":
    asyncio.run(seed())
