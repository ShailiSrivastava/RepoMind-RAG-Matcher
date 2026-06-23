from typing import List, Dict, Any
from google.genai import types
from pydantic import BaseModel, Field
from services.pdf_parser import CandidateProfile
from services.vector_store import VectorStoreManager

# 1. DEFINE DETAILED RECOMMENDATION SCHEMAS
# To get rich, precise feedback for each job match, we define a structured Pydantic schema
# for the LLM evaluation. Each field has a description that guides Gemini's reasoning.
class JobRecommendationDetail(BaseModel):
    job_id: str = Field(description="ID of the matching job listing")
    match_percentage: int = Field(description="Match percentage score from 0 to 100 based on technical fit, experience, and background")
    reason: str = Field(description="A clear 2-3 sentence explanation of why the candidate is a good match for this role")
    skill_gaps: List[str] = Field(description="Technical or domain skills required by the job that appear to be missing or weak on the resume")
    resume_suggestions: List[str] = Field(description="Specific actionable suggestions to customize the resume for this position")
    cover_letter_intro: str = Field(description="A custom 2-3 sentence introductory hook for a cover letter or cold outreach email for this job")

class RAGRecommendations(BaseModel):
    recommendations: List[JobRecommendationDetail]

# 2. GENERATE RECOMMENDATIONS (The RAG Core)
def generate_recommendations(profile: CandidateProfile, vector_store: VectorStoreManager, limit: int = 5) -> Dict[str, Any]:
    """
    Implements the core RAG flow:
    1. Retrieve candidate-relevant jobs from ChromaDB using semantic vector query.
    2. Format the candidate's profile and top retrieved jobs into a context prompt.
    3. Generate a structured match analysis (score, gaps, suggestions) using Gemini.
    4. Merge results with local metadata and return the sorted dashboard payload.
    """
    
    # -- STEP A: Semantic Retrieval --
    # We build a retrieval query text by joining the candidate's target roles and skills.
    # We query the vector database for limit * 2 (top 10) jobs, which we will filter down
    # when feeding to the LLM to manage context window and response speed.
    query_text = f"Target Roles: {', '.join(profile.target_roles)}\nSkills: {', '.join(profile.skills)}\nExperience: {profile.summary}"
    matched_jobs = vector_store.search_jobs(query_text, limit=limit * 2)
    
    if not matched_jobs:
        return {"recommendations": []}
        
    # -- STEP B: Context Prompts Construction --
    # We format the retrieved job documents into a clear XML-like structured string.
    # This serves as the "Augmented Context" (the open-book reference text) for the LLM.
    jobs_context = ""
    for idx, job in enumerate(matched_jobs[:limit]): # Limit to top 5 jobs for LLM context size
        jobs_context += f"""
        --- JOB {idx + 1} ---
        ID: {job['id']}
        Title: {job['title']}
        Company: {job['company']}
        Location: {job['location']}
        Description: {job['document']}
        """
        
    # We assemble the final RAG Prompt, injecting:
    # 1. Candidate's extracted details (Resume profile)
    # 2. Retrieved job descriptions (Augmented database context)
    prompt = f"""
    You are an elite career coach and technical recruiter.
    Analyze the following Candidate Profile and evaluate their fit against the retrieved Job Listings.
    For each job, determine a match score, highlight specific skill gaps (skills the job lists but candidate is missing), and provide highly actionable suggestions on how they can tailor their resume.
    
    CANDIDATE PROFILE:
    Summary: {profile.summary}
    Experience Years: {profile.experience_years}
    Skills: {', '.join(profile.skills)}
    Target Roles: {', '.join(profile.target_roles)}
    
    RETRIEVED JOB LISTINGS:
    {jobs_context}
    """
    
    # -- STEP C: Generation with Fallback --
    # We call our LLM wrapper which retries and cascades through fallback models.
    # We pass RAGRecommendations to enforce the structured JSON output.
    from services.llm import generate_content_with_retry
    
    response = generate_content_with_retry(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RAGRecommendations,
            temperature=0.2,
        ),
    )
    
    # Parse the JSON response into our Pydantic model
    llm_recs = RAGRecommendations.model_validate_json(response.text)
    
    # -- STEP D: Merge & Structure Results --
    # We create a map of job IDs to easily cross-reference matching database items
    # and merge their URLs/metadata with the LLM analysis details.
    job_map = {job["id"]: job for job in matched_jobs}
    final_recommendations = []
    
    for rec in llm_recs.recommendations:
        job_data = job_map.get(rec.job_id)
        if job_data:
            final_recommendations.append({
                "job_id": rec.job_id,
                "title": job_data["title"],
                "company": job_data["company"],
                "url": job_data["url"],
                "location": job_data["location"],
                "category": job_data["category"],
                # Merge the vector search distance rating (semantic_score)
                # with the LLM context-relevance rating (ai_score)
                "semantic_score": job_data["match_score"],
                "ai_score": rec.match_percentage,
                "reason": rec.reason,
                "skill_gaps": rec.skill_gaps,
                "resume_suggestions": rec.resume_suggestions,
                "cover_letter_intro": rec.cover_letter_intro
            })
            
    # Sort matches by the LLM-derived compatibility score in descending order
    final_recommendations.sort(key=lambda x: x["ai_score"], reverse=True)
    
    return {"recommendations": final_recommendations}

