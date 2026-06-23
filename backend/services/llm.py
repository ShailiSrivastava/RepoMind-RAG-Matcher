import os
import logging
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

# 1. SETUP LOGGING
# We configure logging to output info-level logs to the terminal.
# This helps developers monitor when retries are happening, which models are failing,
# and how the fallback mechanism resolves errors in real time.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GeminiClient")

# 2. INITIALIZE GEMINI CLIENT
# The unified google-genai SDK client automatically searches the environment variables
# for "GEMINI_API_KEY". We don't need to pass the key explicitly, keeping credentials safe.
client = genai.Client()

# 3. CORE RETRY DECORATOR (Tenacity)
# We wrap the raw API call with a retry decorator.
# - stop: Limits retries to 2 attempts per model (3 calls total) to prevent long user waiting times.
# - wait: Exponential backoff (wait_exponential) multiplies wait time by a power of 2.
#         It starts by waiting 1s, then 2s, up to 3s. This gives the API breathing room.
# - before_sleep: Logs a warning message right before it enters a sleep state, alerting the server console.
# - reraise: If all retry attempts fail, it throws the original exception so the parent code knows it failed.
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def _call_gemini_raw(model: str, contents: str, config: types.GenerateContentConfig):
    """
    Core function that makes the raw API call to Gemini.
    If it throws a transient error (e.g. 503 Unavailable or 429 Rate Limit),
    the @retry decorator will intercept the error and repeat the function call.
    """
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )

# 4. CASCADING FALLBACK ROUTING
# RAG systems in production must be highly reliable. If a specific model family (like Gemini 2.5 Flash)
# is completely overloaded (spikes in demand), we must gracefully redirect requests to a fallback model.
def generate_content_with_retry(model: str, contents: str, config: types.GenerateContentConfig):
    """
    A robust LLM router that runs retries on the primary model, and if it fails completely,
    gracefully cascades through a series of fallback models (2.0 Flash, 1.5 Flash, 2.5 Pro)
    until one succeeds.
    """
    # We establish a chain of fallback models that support structured JSON output schemas:
    # 1. Primary Model (e.g., gemini-2.5-flash) - the user's/code's preference
    # 2. gemini-2.0-flash - next-generation fast model with separate API resources
    # 3. gemini-flash-latest - stable 1.5 Flash production instance (highly available)
    # 4. gemini-2.5-pro - high-capacity reasoning model
    fallback_chain = [model, "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-pro"]
    
    # Deduplicate the model names in case the input model is already in the fallback list,
    # ensuring we don't try the same model twice in a row.
    seen = set()
    models_to_try = []
    for m in fallback_chain:
        if m not in seen:
            seen.add(m)
            models_to_try.append(m)
            
    last_err = None
    # Iterate through the cascade chain
    for target_model in models_to_try:
        try:
            logger.info(f"Attempting API call using model: {target_model}")
            # Try to run the API call (which includes its own internal retry loop)
            return _call_gemini_raw(target_model, contents, config)
        except Exception as e:
            # If the call fails after retries, log the fallback transition and continue
            logger.warning(f"Model '{target_model}' failed with error: {e}. Moving to next fallback...")
            last_err = e
            continue
            
    # If all models in the chain fail, raise the last exception to the client
    logger.critical("All Gemini models in the fallback chain failed.")
    raise last_err

