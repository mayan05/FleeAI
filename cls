[1mdiff --git a/src/agents/query_agent.py b/src/agents/query_agent.py[m
[1mindex e792d71..e69de29 100644[m
[1m--- a/src/agents/query_agent.py[m
[1m+++ b/src/agents/query_agent.py[m
[36m@@ -1,172 +0,0 @@[m
[31m-"""[m
[31m-Agent 1: Query Understanding Agent[m
[31m-[m
[31m-Job: turn a messy natural-language flight request into a structured[m
[31m-FlightQuery object. If required info is missing, it does NOT guess —[m
[31m-it sets is_complete=False and produces a single clarification_question[m
[31m-for the orchestrator to relay back to the user.[m
[31m-[m
[31m-Date handling: the LLM is NOT trusted to compute actual calendar dates[m
[31m-for relative phrases ("next Friday", "tomorrow") -- it only extracts the[m
[31m-phrase verbatim into raw_date_expression. The actual date math happens[m
[31m-afterward in resolve_relative_date(), which is deterministic Python and[m
[31m-therefore always correct.[m
[31m-"""[m
[31m-[m
[31m-from datetime import date[m
[31m-from crewai import Agent, Task, Crew, Process[m
[31m-from src.llm_config import fleeai_llm[m
[31m-from src.schemas.models import FlightQuery[m
[31m-from src.utils.date_resolver import resolve_relative_date[m
[31m-[m
[31m-query_understanding_agent = Agent([m
[31m-    role="Flight Query Analyst",[m
[31m-    goal=([m
[31m-        "Extract precise, structured flight search parameters from a user's "[m
[31m-        "natural language request. Never invent information the user did not "[m
[31m-        "provide -- if origin, destination, or departure date is missing or "[m
[31m-        "ambiguous, flag it clearly instead of guessing."[m
[31m-    ),[m
[31m-    backstory=([m
[31m-        "You are a meticulous travel-desk analyst. You've seen every way people "[m
[31m-        "describe travel plans -- vague dates, city nicknames, budget ranges -- "[m
[31m-        "and you're excellent at pulling out exactly what's needed for a flight "[m
[31m-        "search while knowing when to ask instead of assume. You know you are "[m
[31m-        "bad at mental weekday arithmetic, so you never try to calculate an "[m
[31m-        "actual date from a phrase like 'next Friday' -- you just capture the "[m
[31m-        "phrase exactly as the user said it and let a separate system resolve "[m
[31m-        "it precisely."[m
[31m-    ),[m
[31m-    llm=fleeai_llm,[m
[31m-    verbose=True,[m
[31m-    allow_delegation=False,[m
[31m-)[m
[31m-[m
[31m-[m
[31m-def build_extraction_task(user_request: str, conversation_context: str = "") -> Task:[m
[31m-    """[m
[31m-    Builds the extraction task for a given user message.[m
[31m-[m
[31m-    conversation_context: pass in prior clarification Q&A here, so the agent[m
[31m-    has full context on multi-turn conversations (e.g. user answering a[m
[31m-    follow-up question).[m
[31m-    """[m
[31m-    context_block = ([m
[31m-        f"\n\nIMPORTANT: The user has already answered a clarification "[m
[31m-        f"question. You MUST extract origin, destination, and date info from "[m
[31m-        f"this answer and merge it with the original request below -- do not "[m
[31m-        f"ask the same question again if the answer already covers it.\n"[m
[31m-        f"{conversation_context}"[m
[31m-        if conversation_context[m
[31m-        else ""[m
[31m-    )[m
[31m-    today_str = date.today().isoformat()[m
[31m-[m
[31m-    return Task([m
[31m-        description=([m
[31m-            f"Today's date is {today_str}. Do NOT use this to calculate a "[m
[31m-            f"final date yourself -- see date rules below.\n\n"[m
[31m-            f"Analyze this flight booking request and extract structured search "[m
[31m-            f"parameters.\n\nUser request: \"{user_request}\"{context_block}\n\n"[m
[31m-            "Rules:\n"[m
[31m-            "- origin, destination, and a date (either departure_date OR "[m
[31m-            "raw_date_expression) are REQUIRED to consider the query complete.\n"[m
[31m-            "- DATE HANDLING: if the user gave an explicit calendar date "[m
[31m-            "('July 20', '20th', '2026-07-20'), put the resolved YYYY-MM-DD in "[m
[31m-            "departure_date. If the user gave a RELATIVE phrase ('next "[m
[31m-            "Friday', 'tomorrow', 'in 2 weeks'), do NOT calculate a date "[m
[31m-            "yourself -- copy the phrase verbatim into raw_date_expression and "[m
[31m-            "leave departure_date null. You are unreliable at weekday math, so "[m
[31m-            "never attempt it.\n"[m
[31m-            "- CRITICAL: If the user's message does not explicitly state an "[m
[31m-            "origin city, destination city, or any date/date-phrase, you MUST "[m
[31m-            "leave that field as null and add it to missing_fields. Never "[m
[31m-            "infer, assume, or invent an origin, destination, or date the "[m
[31m-            "user did not explicitly say -- even if one seems 'likely'.\n\n"[m
[31m-            "EXAMPLE OF WHAT NOT TO DO:\n"[m
[31m-            "User request: \"I need a flight to Mumbai sometime, nothing fancy\"\n"[m
[31m-            "WRONG output: origin=\"Bangalore\", departure_date=\"2026-07-14\", "[m
[31m-            "is_complete=true  <-- WRONG, user never said an origin, and "[m
[31m-            "'sometime' is not a real date.\n"[m
[31m-            "CORRECT output: origin=null, destination=\"Mumbai\", "[m
[31m-            "departure_date=null, raw_date_expression=null, is_complete=false, "[m
[31m-            "missing_fields=[\"origin\", \"departure_date\"], "[m
[31m-            "clarification_question=\"Which city will you be flying from, and "[m
[31m-            "do you have a date in mind?\"\n\n"[m
[31m-            "- Do not fabricate a budget, passenger count, or preference the "[m
[31m-            "user never mentioned -- passengers defaults to 1, cabin_class "[m
[31m-            "defaults to 'economy' only if not specified.\n"[m
[31m-            "- If anything required is missing, set is_complete to false, list "[m
[31m-            "the missing fields, and write exactly ONE clear, friendly "[m
[31m-            "clarification question covering all missing pieces at once."[m
[31m-        ),[m
[31m-        expected_output="A FlightQuery JSON object matching the schema exactly.",[m
[31m-        agent=query_understanding_agent,[m
[31m-        output_pydantic=FlightQuery,[m
[31m-    )[m
[31m-[m
[31m-[m
[31m-def run_query_understanding(user_request: str, conversation_context: str = "") -> FlightQuery:[m
[31m-    """[m
[31m-    Runs Agent 1 and returns a validated, fully-resolved FlightQuery.[m
[31m-[m
[31m-    After the LLM extracts the raw phrase, this function deterministically[m
[31m-    resolves raw_date_expression into a real departure_date. If resolution[m
[31m-    fails (unrecognized phrase), the query is forced back to incomplete[m
[31m-    with a clarification question, rather than silently leaving a bad date.[m
[31m-    """[m
[31m-    task = build_extraction_task(user_request, conversation_context)[m
[31m-    crew = Crew([m
[31m-        agents=[query_understanding_agent],[m
[31m-        tasks=[task],[m
[31m-        process=Process.sequential,[m
[31m-        verbose=True,[m
[31m-    )[m
[31m-    result = crew.kickoff()[m
[31m-    query: FlightQuery = result.pydantic[m
[31m-[m
[31m-    # Deterministic date resolution -- never trust the LLM's date math[m
[31m-    if query.departure_date is None and query.raw_date_expression:[m
[31m-        resolved = resolve_relative_date(query.raw_date_expression)[m
[31m-        if resolved:[m
[31m-            query.departure_date = resolved[m
[31m-        else:[m
[31m-            # Couldn't confidently resolve the phrase -- ask instead of guessing[m
[31m-            query.is_complete = False[m
[31m-            if "departure_date" not in query.missing_fields:[m
[31m-                query.missing_fields.append("departure_date")[m
[31m-            query.clarification_question = ([m
[31m-                f"I couldn't quite pin down '{query.raw_date_expression}' as a "[m
[31m-                f"date -- could you give me an exact date (e.g. 2026-07-17)?"[m
[31m-            )[m
[31m-[m
[31m-    # Recompute completeness ourselves rather than trusting the LLM's flag --[m
[31m-    # it can be stale/wrong even when every required field is actually filled.[m
[31m-    query.missing_fields = [[m
[31m-        f for f in query.missing_fields[m
[31m-        if not ([m
[31m-            (f == "origin" and query.origin)[m
[31m-            or (f == "destination" and query.destination)[m
[31m-            or (f == "departure_date" and query.departure_date)[m
[31m-        )[m
[31m-    ][m
[31m-    has_all_required = bool(query.origin and query.destination and query.departure_date)[m
[31m-    if has_all_required:[m
[31m-        query.is_complete = True[m
[31m-        query.missing_fields = [][m
[31m-        query.clarification_question = None[m
[31m-    else:[m
[31m-        query.is_complete = False[m
[31m-        if not query.origin and "origin" not in query.missing_fields:[m
[31m-            query.missing_fields.append("origin")[m
[31m-        if not query.destination and "destination" not in query.missing_fields:[m
[31m-            query.missing_fields.append("destination")[m
[31m-        if not query.departure_date and "departure_date" not in query.missing_fields:[m
[31m-            query.missing_fields.append("departure_date")[m
[31m-        if not query.clarification_question:[m
[31m-            query.clarification_question = ([m
[31m-                "Could you give me the missing details: "[m
[31m-                + ", ".join(query.missing_fields) + "?"[m
[31m-            )[m
[31m-[m
[31m-    return query[m
\ No newline at end of file[m
