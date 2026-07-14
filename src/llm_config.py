"""
Central place to configure the LLM used by all agents.

Using a locally-hosted Ollama model (Llama 3.2 3B) for fully offline,
zero-cost inference. The 3B model is chosen for speed on CPU — it's
roughly 3x faster than the 8B variant with acceptable accuracy for
structured extraction tasks.

Make sure Ollama is running:  ollama serve
Pull the model if needed:     ollama pull llama3.2:3b
"""

import crewai.llms.cache as _crewai_cache

_crewai_cache.mark_cache_breakpoint = lambda msg: msg
# --------------------------------------------------------------------

from crewai import LLM

fleeai_llm = LLM(
    model="ollama/llama3.2:3b",
    base_url="http://localhost:11434",
    temperature=0.1,  # very low temperature: smaller models need tighter control for structured output
)
