"""
NagarDrishti — Gemini Client with Auto-Fallback
agents/gemini_client.py

Manages multiple Gemini models with automatic fallback.
If primary model hits quota or fails, switches to next.

Model priority based on free tier quotas (April 2026):
  Text tasks : gemini-3.1-flash-lite (500 RPD) → gemini-3-flash (20 RPD)
  Vision tasks: gemini-2.5-flash (20 RPD) → gemini-3-flash (20 RPD)
"""

import time
from google import genai
from config import GEMINI_API_KEY

# Text generation models — ordered by free tier quota (best first)
TEXT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash",
]

# Vision/multimodal models — need image understanding
VISION_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash",
]


def call_with_fallback(
    client,
    contents,
    model_list: list,
    task_name: str = "API call"
) -> str:
    """
    Tries each model in order until one succeeds.
    Returns the response text or raises if all fail.
    
    Args:
        client     : genai.Client instance
        contents   : prompt string or list (for multimodal)
        model_list : ordered list of model strings to try
        task_name  : name for logging
    
    Returns:
        str: response text from first successful model
    """
    last_error = None
    
    for model in model_list:
        try:
            print(f"  [Gemini] Trying {model} for {task_name}...")
            resp = client.models.generate_content(
                model=model,
                contents=contents
            )
            print(f"  [Gemini] ✓ {model} succeeded")
            return resp.text.strip()
            
        except Exception as e:
            error_str = str(e)
            last_error = e
            
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"  [Gemini] ⚠ {model} quota exceeded — trying next model")
                time.sleep(1)   # Brief pause before retry
                continue
                
            elif "404" in error_str or "not found" in error_str.lower():
                print(f"  [Gemini] ⚠ {model} not available — trying next model")
                continue
                
            else:
                print(f"  [Gemini] ✗ {model} error: {error_str[:80]}")
                continue
    
    raise Exception(
        f"All Gemini models failed for {task_name}. "
        f"Last error: {last_error}"
    )
