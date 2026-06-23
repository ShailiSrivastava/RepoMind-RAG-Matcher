import requests
import re
import xml.etree.ElementTree as ET
from typing import List
from pydantic import BaseModel

# 1. DEFINE INTERNAL JOB ITEM MODEL
# This Pydantic class standardizes the format of job listings that we index.
# Standardizing the model allows the rest of our application (Vector store and LLM matchers)
# to consume a consistent layout, regardless of which public job feed we read from.
class JobItem(BaseModel):
    id: str
    title: str
    company: str
    description: str
    url: str
    location: str
    category: str

# 2. HTML STRIPPING UTILITY
# Text retrieved from RSS feeds or web scrapes often contains raw HTML tags (e.g., <p>, <strong>, &nbsp;).
# Leaving these tags intact consumes unnecessary LLM tokens and introduces noise to the embedding vectors.
def clean_html(raw_html: str) -> str:
    """
    Cleans up HTML strings, strips out markup tags using regex,
    and condenses multiple tabs/spaces into single characters.
    """
    if not raw_html:
        return ""
    # Regex pattern: Match anything starting with '<' and ending with '>' or HTML entities (like &amp; or &#39;)
    cleanr = re.compile('<.*?>|&[a-zA-Z0-9#]+;')
    cleantext = re.sub(cleanr, ' ', raw_html)
    # Condense consecutive white-spaces or tabs into a single clean space
    cleantext = re.sub(r'\s+', ' ', cleantext)
    return cleantext.strip()

# 3. WEWORKREMOTELY RSS CRAWLER
def fetch_weworkremotely_jobs(limit: int = 50) -> List[JobItem]:
    """
    Downloads the active WeWorkRemotely RSS XML feed, parses the XML nodes,
    and returns a structured list of JobItems.
    """
    # Public RSS endpoint containing active remote jobs
    url = "https://weworkremotely.com/remote-jobs.rss"
    
    # We set a standard User-Agent header so the request resembles a real browser,
    # preventing blockages by standard DDoS protection barriers.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        # Fetch the RSS content
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse the raw XML string into an ElementTree root node
        # ET.fromstring converts XML tags into a traversable Python object tree.
        root = ET.fromstring(response.content)
        
        # Find all `<item>` elements (each represents a job listing in RSS specifications)
        items = root.findall(".//item")
        
        jobs = []
        # Limit processing to the requested limit (e.g., top 50 jobs)
        for item in items[:limit]:
            title_text = item.findtext("title", "")
            
            # WeWorkRemotely formats RSS titles as "Company Name: Job Title"
            # We split the string by the first occurrence of ":" to extract company and title separately.
            if " : " in title_text:
                company, title = title_text.split(" : ", 1)
            elif ":" in title_text:
                company, title = title_text.split(":", 1)
            else:
                company = "Remote Company"
                title = title_text
                
            company = company.strip()
            title = title.strip()
            
            # Get the URL of the job post
            job_url = item.findtext("link", "")
            
            # Since WeWorkRemotely RSS items don't provide a direct unique ID attribute,
            # we generate a stable positive ID by hashing the job URL (using bitwise AND to keep it positive).
            job_id = str(hash(job_url) & 0xffffffff)
            
            # Clean HTML markup from the description
            description = clean_html(item.findtext("description", ""))
            
            # Read category (default to Software Engineering)
            category = item.findtext("category", "Software Engineering")
            location = "Remote"
            
            # Append structured item
            jobs.append(JobItem(
                id=job_id,
                title=title,
                company=company,
                description=description,
                url=job_url,
                location=location,
                category=category
            ))
            
        return jobs
    except Exception as e:
        print(f"Error fetching jobs from WeWorkRemotely RSS: {e}")
        return []


