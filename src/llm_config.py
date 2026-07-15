"""
Central place to configure the LLM used by all agents.

Using a local Ollama model — no API key, no cost, runs fully offline.
"""

import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg
# --------------------------------------------------------------------

from crewai import LLM

fleeai_llm = LLM(
    model="ollama/llama3.2:3b",
    base_url="http://localhost:11434",
    temperature=0.2,
)