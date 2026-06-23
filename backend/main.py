import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.pdf_parser import parse_resume_pdf, CandidateProfile
from services.job_fetcher import fetch_weworkremotely_jobs
from services.vector_store import VectorStoreManager
from services.matcher import generate_recommendations

app = FastAPI(title="Resume Job Matcher RAG API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins in local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy load Vector Store manager to prevent slow startup times
vector_store = None

def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = VectorStoreManager()
    return vector_store

# Create a temporary folder for resume processing
TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp"))
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/api/upload-resume", response_model=CandidateProfile)
async def upload_resume(file: UploadFile = File(...)):
    """
    Accepts a PDF resume, parses its text, and returns a structured candidate profile.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
        
    temp_file_path = os.path.join(TEMP_DIR, file.filename)
    try:
        # Save file to temp folder
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Extract and parse profile
        profile = parse_resume_pdf(temp_file_path)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

@app.post("/api/sync-jobs")
async def sync_jobs(limit: int = 50):
    """
    Fetches active jobs from WeWorkRemotely feed and indexes them in ChromaDB.
    """
    try:
        # Fetch jobs
        jobs = fetch_weworkremotely_jobs(limit=limit)
        if not jobs:
            return {"status": "success", "message": "No jobs fetched."}
            
        # Add to vector database
        v_store = get_vector_store()
        v_store.add_jobs(jobs)
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(jobs)} jobs in ChromaDB."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync jobs: {str(e)}")

@app.post("/api/match-jobs")
async def match_jobs(profile: CandidateProfile):
    """
    Takes a candidate profile, retrieves top matches, and runs AI similarity evaluation.
    """
    try:
        v_store = get_vector_store()
        # Verify if ChromaDB has anything indexed
        if v_store.collection.count() == 0:
            raise HTTPException(
                status_code=400, 
                detail="No jobs in vector database. Please run /api/sync-jobs first."
            )
            
        recommendations = generate_recommendations(profile, v_store)
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to match jobs: {str(e)}")

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}
