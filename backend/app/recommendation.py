import os
import chromadb
from chromadb.utils import embedding_functions
from google import genai
from typing import List, Dict
import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure GenAI Client
api_key = os.getenv("GOOGLE_API_KEY")
client_genai = None
if api_key:
    client_genai = genai.Client(api_key=api_key)

class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    def __call__(self, input: List[str]) -> List[List[float]]:
        if not client_genai:
            raise ValueError("GOOGLE_API_KEY not set")
        
        # Use Gemini's embedding model with the new SDK
        result = client_genai.models.embed_content(
            model='models/gemini-embedding-001', 
            contents=input
        )
        return [embedding.values for embedding in result.embeddings]

# Initialize ChromaDB
client_chroma = chromadb.PersistentClient(path="./chroma_db")
collection = client_chroma.get_or_create_collection(
    name="books",
    embedding_function=GeminiEmbeddingFunction() if api_key else None
)

def add_book_to_vector_db(book_id: int, title: str, synopsis: str, genres: List[str], authors: List[str]):
    if not api_key:
        print("Warning: GOOGLE_API_KEY not set. Book not added to Vector DB.")
        return
    
    content = f"Title: {title}. Authors: {', '.join(authors)}. Genres: {', '.join(genres)}. Synopsis: {synopsis}"
    collection.add(
        documents=[content],
        metadatas=[{"book_id": book_id, "title": title}],
        ids=[str(book_id)]
    )

def get_recommendations(user_preference_vector: List[float], n_results: int = 5, exclude_ids: List[str] = []):
    if not api_key or collection.count() == 0:
        return {"ids": [[]]}
    
    # Chroma query
    actual_n_results = min(n_results, collection.count())
    if actual_n_results == 0:
        return {"ids": [[]]}

    results = collection.query(
        query_embeddings=[user_preference_vector],
        n_results=actual_n_results,
        where={"book_id": {"$nin": [int(id) for id in exclude_ids]}} if exclude_ids else None
    )
    return results

def calculate_user_vector(preferred_genres: List[str], preferred_authors: List[str], interactions: List[Dict]):
    if not client_genai:
        raise ValueError("GOOGLE_API_KEY not set")
        
    pref_text = f"I like genres: {', '.join(preferred_genres)}. I like authors: {', '.join(preferred_authors)}."
    
    liked_books = [i for i in interactions if i['type'] == 'like']
    disliked_books = [i for i in interactions if i['type'] == 'dislike']
    
    if liked_books:
        pref_text += " I liked books similar to: " + ", ".join([b['title'] for b in liked_books])
    
    if disliked_books:
        pref_text += " I disliked books similar to: " + ", ".join([b['title'] for b in disliked_books])

    result = client_genai.models.embed_content(
        model='models/gemini-embedding-001',
        contents=pref_text
    )
    return result.embeddings[0].values
