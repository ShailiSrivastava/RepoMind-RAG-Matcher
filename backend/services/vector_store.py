import os
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb
from services.job_fetcher import JobItem

# 1. DEFINE VECTOR DATABASE CACHE PATH
# We set an absolute path on disk to save ChromaDB's SQLite database.
# This prevents our data from disappearing when the FastAPI server restarts.
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db"))

class VectorStoreManager:
    def __init__(self):
        # -- STEP A: Load SentenceTransformer Model --
        # Sentence Transformers convert text into dense, fixed-size numerical vectors (embeddings).
        # We load "all-MiniLM-L6-v2", which is a highly optimized, lightweight model (~90MB).
        # It maps any text chunk into a 384-dimensional vector, where close vectors represent
        # semantically similar meanings (even if they share zero keyword overlaps).
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # -- STEP B: Initialize Persistent ChromaDB Client --
        # ChromaDB is a fast, developer-friendly local vector database.
        # PersistentClient ensures it writes database indexes directly to DB_PATH on disk.
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # -- STEP C: Create/Access Collection --
        # A collection in vector databases is equivalent to a table in relational SQL.
        # get_or_create_collection looks for a collection called "job_listings", or creates it.
        self.collection = self.client.get_or_create_collection(name="job_listings")

    def add_jobs(self, jobs: List[JobItem]):
        """
        Processes a list of raw job items, generates vector embeddings for each description,
        and saves them inside our local ChromaDB index.
        """
        if not jobs:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for job in jobs:
            ids.append(job.id)
            
            # To get rich semantic search, we combine title, company, and description.
            # Embedding this combined string allows our semantic search to recognize relationships
            # like "Software Engineer at Google" together with the job responsibilities.
            searchable_text = f"Title: {job.title}\nCompany: {job.company}\nDescription: {job.description}"
            documents.append(searchable_text)
            
            # Metadata is stored alongside the vector. It contains the fields we will
            # display directly to the frontend (like apply URLs, location) without needing a SQL join.
            metadatas.append({
                "title": job.title,
                "company": job.company,
                "url": job.url,
                "location": job.location,
                "category": job.category
            })
            
        # -- STEP D: Batch Vectorization --
        # We pass all combined strings to our SentenceTransformer model.
        # encode() runs the neural network feedforward pass. We call .tolist()
        # because ChromaDB expects standard Python float lists rather than NumPy arrays.
        job_embeddings = self.model.encode(documents).tolist()
        
        # -- STEP E: Upsert Database --
        # collection.upsert inserts the documents if they are new, or updates them
        # if the IDs already exist. This prevents duplicate entries.
        self.collection.upsert(
            ids=ids,
            embeddings=job_embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search_jobs(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Runs a semantic similarity query against our indexed job listings.
        Converts query string to a vector, and queries ChromaDB for the closest vectors.
        """
        # 1. Convert user search query text (resume profile summary) into a 384-dimensional vector
        query_vector = self.model.encode(query_text).tolist()
        
        # 2. Query ChromaDB database.
        # Ensure we do not request more results than available in the index to prevent ChromaDB errors.
        total_items = self.collection.count()
        if total_items == 0:
            return []
            
        n_results = min(limit, total_items)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=n_results
        )
        
        formatted_results = []
        
        # ChromaDB query returns arrays grouped inside lists. We flatten and structure them.
        if results and results["ids"] and len(results["ids"][0]) > 0:
            ids = results["ids"][0]
            distances = results["distances"][0] # L2 Euclidean distance list
            metadatas = results["metadatas"][0]
            documents = results["documents"][0]
            
            for i in range(len(ids)):
                # -- DISTANCE TO SIMILARITY SCORE CONVERSION --
                # ChromaDB uses L2 (squared Euclidean) distance by default.
                # A distance of 0 means a perfect identical match. Typical distances range up to 1.2+.
                # We map L2 distance to an easy-to-read similarity score percentage (0-100%) for UI.
                distance = distances[i]
                similarity_percentage = max(0, min(100, int((1.0 - (distance / 2.0)) * 100)))
                
                # Construct clean dictionary output
                formatted_results.append({
                    "id": ids[i],
                    "match_score": similarity_percentage,
                    "document": documents[i],
                    "title": metadatas[i].get("title", ""),
                    "company": metadatas[i].get("company", ""),
                    "url": metadatas[i].get("url", ""),
                    "location": metadatas[i].get("location", ""),
                    "category": metadatas[i].get("category", "")
                })
                
        return formatted_results

