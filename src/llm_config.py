"""
Central place to configure the LLM used by all agents.

Using Groq's free tier (Llama 3.3 70B) keeps this project at $0 cost.
CrewAI routes non-OpenAI providers through LiteLLM automatically when
you prefix the model string with the provider name, e.g. "groq/...".

Get a free key at: https://console.groq.com/keys
"""

import crewai.llms.cache as _crewai_cache

_crewai_cache.mark_cache_breakpoint = lambda msg: msg
# --------------------------------------------------------------------

import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise EnvironmentError(
        "GROQ_API_KEY not found. Copy .env.example to .env and add your free "
        "Groq API key from https://console.groq.com/keys"
    )

fleeai_llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.2,  # low temperature: for reliable structured extraction, not creativity
)
