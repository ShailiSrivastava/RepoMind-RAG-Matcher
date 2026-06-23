import pdfplumber # Library for extracting text and data from PDF files
import os # Built-in Python library for interacting with the operating system
from google.genai import types # Provides type definitions for Gemini API configuration
from pydantic import BaseModel, Field # Provides data validation and settings management via Python type annotations
from typing import List, Optional # Supports type hinting for complex structures
from dotenv import load_dotenv # Utility for loading environment variables from a .env file

# 1. LOAD CONFIGURATION
# Load environment variables from the .env file (primarily for GEMINI_API_KEY).
load_dotenv()

# 2. DEFINE CANDIDATE PROFILE SCHEMA (Pydantic)
# In RAG pipelines, extracting structured details from unstructured inputs (like PDFs) is key.
# We define a Pydantic model (BaseModel) to serve as a strict target schema.
# Gemini will be forced to return JSON that matches this exact class structure.
class CandidateProfile(BaseModel):
    name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address of the candidate")
    phone: Optional[str] = Field(description="Phone number of the candidate", default="")
    skills: List[str] = Field(description="List of technical skills, programming languages, libraries, tools, frameworks, and soft skills")
    experience_years: float = Field(description="Total years of professional work experience")
    summary: str = Field(description="A brief professional summary of the candidate")
    target_roles: List[str] = Field(description="List of target job titles or roles the candidate is suitable for based on their profile")

# 3. PARSE RESUME PDF FUNCTION
def parse_resume_pdf(pdf_path: str) -> CandidateProfile:
    """
    Reads a PDF resume file, extracts its text, and utilizes Gemini to transform
    messy, multi-layout text into a structured, typed CandidateProfile object.
    """
    # -- STEP A: PDF Text Extraction --
    # pdfplumber is a reliable PDF library that extracts text page-by-page while respecting layouts.
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    
    # Check if we got text. If it is a scanned image PDF, text will be empty, requiring OCR (which we catch here).
    if not text.strip():
        raise ValueError("Could not extract any text from the PDF file. The file may be empty or image-only.")
        
    # -- STEP B: structured LLM Query --
    # We import our robust LLM call client which implements retries and fallback models.
    from services.llm import generate_content_with_retry
    
    # We construct a precise instruction prompt. We tell the model to analyze the text
    # and map it into the JSON schema defined below.
    prompt = f"""
    You are an expert HR recruitment assistant. Analyze the following raw text from a candidate's resume and extract their profile into a structured schema.
    Ensure technical skills are clearly isolated, and make a sensible estimate of total years of experience.
    
    Raw Resume Text:
    ---
    {text}
    ---
    """
    
    # We call Gemini with GenerateContentConfig:
    # - response_mime_type="application/json" instructs the model to return raw JSON only.
    # - response_schema=CandidateProfile tells Gemini the exact fields and types to output.
    # - temperature=0.1 ensures the output is highly deterministic (low creativity, high factual extraction).
    response = generate_content_with_retry(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CandidateProfile,
            temperature=0.1,
        ),
    )
    
    # -- STEP C: Pydantic Validation --
    # response.text is a JSON string. CandidateProfile.model_validate_json reads it,
    # verifies that all types match (e.g., experience_years is a float), and returns
    # a verified Python class instance.
    return CandidateProfile.model_validate_json(response.text)
