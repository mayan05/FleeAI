"""
Central place to configure the LLM used by all agents.

Using Groq's free tier (Llama 3.3 70B) keeps this project at $0 cost.
CrewAI routes non-OpenAI providers through LiteLLM automatically when
you prefix the model string with the provider name, e.g. "groq/...".

Get a free key at: https://console.groq.com/keys

--------------------------------------------------------------------
Groq / cache_breakpoint compatibility patch
--------------------------------------------------------------------
CrewAI 1.15.x tags every system/user message with an internal
`cache_breakpoint: true` marker to support Anthropic prompt caching.
Only the Anthropic provider adapter strips that marker before sending
the request. Every other provider reached through the generic LiteLLM
path -- including Groq -- forwards the raw marker straight through,
and Groq's strict message-schema validation rejects it with:

    GroqException - 'messages.0': property 'cache_breakpoint' is unsupported

This is a confirmed, currently-open upstream bug:
https://github.com/crewAIInc/crewAI/issues/5886

The fix is to no-op the marker function at its source, before any
agent builds its first message. crewai's executor does a *local*
import of `mark_cache_breakpoint` inside the method that assembles
messages, so patching the module attribute here (which runs once,
before any Agent/Crew is constructed) is enough -- every agent that
imports `fleeai_llm` from this file automatically gets the fix, with
no per-script or per-test monkeypatching needed.

Safe to delete this block once crewAI ships a real fix for #5886 --
at that point it becomes a harmless no-op override of their own fix,
so it's not urgent to remove it, but worth a comment/reminder.
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
    temperature=0.2,  # low temperature: we want reliable structured extraction, not creativity
)
