"""
FleeAI — Streamlit Chat UI

Provides a conversational interface for the flight booking pipeline:
    1. User types a flight request
    2. Agent 1 parses it; if info is missing, asks a clarification question
    3. Once complete, searches for flights and displays ranked results as cards
    4. User selects a flight (booking wired in Day 3)

Run with:  streamlit run src/app.py
"""

import streamlit as st
from src.orchestrator import FleeAISession


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FleeAI ✈️",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .fleeai-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    .fleeai-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.25rem;
    }
    .fleeai-header p {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 0;
    }

    /* Flight card */
    .flight-card {
        background: linear-gradient(145deg, #1e1b4b 0%, #312e81 100%);
        border: 1px solid #4338ca;
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        color: #e2e8f0;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .flight-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.25);
    }
    .flight-card .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
    }
    .flight-card .airline {
        font-weight: 600;
        font-size: 1.1rem;
        color: #c7d2fe;
    }
    .flight-card .price {
        font-weight: 700;
        font-size: 1.3rem;
        color: #a78bfa;
    }
    .flight-card .route {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }
    .flight-card .route .arrow {
        color: #6366f1;
        font-size: 1.2rem;
    }
    .flight-card .meta {
        display: flex;
        gap: 1.5rem;
        font-size: 0.85rem;
        color: #94a3b8;
        margin-bottom: 0.5rem;
    }
    .flight-card .rank-reason {
        font-size: 0.85rem;
        color: #a5b4fc;
        font-style: italic;
        border-top: 1px solid #3730a3;
        padding-top: 0.5rem;
        margin-top: 0.5rem;
    }

    /* Query summary chip */
    .query-chip {
        display: inline-block;
        background: #1e1b4b;
        border: 1px solid #4338ca;
        border-radius: 20px;
        padding: 0.35rem 0.9rem;
        margin: 0.15rem;
        font-size: 0.82rem;
        color: #c7d2fe;
    }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-mock {
        background: #fef3c7;
        color: #92400e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session state init ───────────────────────────────────────────────────────
if "session" not in st.session_state:
    st.session_state.session = FleeAISession()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "awaiting_selection" not in st.session_state:
    st.session_state.awaiting_selection = False


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="fleeai-header">
        <h1>✈️ FleeAI</h1>
        <p>Tell me where you want to fly — I'll find the best options.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Helper: render flight cards ──────────────────────────────────────────────
def render_flight_cards(ranked_flights):
    """Render flight results as styled cards."""
    for i, flight in enumerate(ranked_flights.options, 1):
        # Parse times for display
        dep_time = flight.departure_time.split("T")[-1][:5] if "T" in flight.departure_time else flight.departure_time
        arr_time = flight.arrival_time.split("T")[-1][:5] if "T" in flight.arrival_time else flight.arrival_time
        stops_text = "Direct" if flight.stops == 0 else f"{flight.stops} stop{'s' if flight.stops > 1 else ''}"
        hours = flight.duration_minutes // 60
        mins = flight.duration_minutes % 60
        duration_text = f"{hours}h {mins}m" if hours else f"{mins}m"

        st.markdown(
            f"""
            <div class="flight-card">
                <div class="card-header">
                    <span class="airline">#{i} · {flight.airline}</span>
                    <span class="price">₹{flight.price_inr:,}</span>
                </div>
                <div class="route">
                    <strong>{flight.origin}</strong>
                    <span class="arrow">✈ →</span>
                    <strong>{flight.destination}</strong>
                </div>
                <div class="meta">
                    <span>🕐 {dep_time} – {arr_time}</span>
                    <span>⏱ {duration_text}</span>
                    <span>🔄 {stops_text}</span>
                </div>
                <div class="rank-reason">💡 {flight.rank_reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_query_summary(query):
    """Show the parsed query as chips."""
    chips = []
    if query.origin:
        code = f" ({query.origin_iata})" if query.origin_iata else ""
        chips.append(f"📍 From: {query.origin}{code}")
    if query.destination:
        code = f" ({query.destination_iata})" if query.destination_iata else ""
        chips.append(f"📍 To: {query.destination}{code}")
    if query.departure_date:
        chips.append(f"📅 {query.departure_date}")
    if query.budget_inr:
        chips.append(f"💰 ≤ ₹{query.budget_inr:,}")
    if query.cabin_class:
        chips.append(f"💺 {query.cabin_class.replace('_', ' ').title()}")
    if query.passengers and query.passengers > 1:
        chips.append(f"👥 {query.passengers} passengers")

    if chips:
        chip_html = "".join(f'<span class="query-chip">{c}</span>' for c in chips)
        st.markdown(chip_html, unsafe_allow_html=True)


# ── Render chat history ─────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

        # Re-render flight cards if this message had them
        if msg.get("ranked_flights"):
            render_flight_cards(msg["ranked_flights"])

        if msg.get("flight_query"):
            render_query_summary(msg["flight_query"])


# ── Chat input ───────────────────────────────────────────────────────────────
if prompt := st.chat_input(
    "Select a flight number..." if st.session_state.awaiting_selection
    else "Where do you want to fly?"
):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get orchestrator response
    session: FleeAISession = st.session_state.session

    with st.chat_message("assistant"):
        if session.stage == "idle":
            with st.spinner("🧠 Understanding your request..."):
                response = session.start(prompt)
        elif session.stage == "select":
            response = session.respond(prompt)
        else:
            with st.spinner("🧠 Processing..."):
                response = session.respond(prompt)

        # Handle the response based on stage
        if response.stage == "clarification":
            msg_content = f"🤔 {response.clarification_question}"
            st.markdown(msg_content)
            st.session_state.messages.append({"role": "assistant", "content": msg_content})
            st.session_state.awaiting_selection = False

        elif response.stage == "query_complete":
            # Agent 2 not available yet — show Agent 1's output
            st.markdown(response.message)
            if response.flight_query:
                render_query_summary(response.flight_query)
                st.markdown("#### Agent 2 Input (`FlightQuery`)")
                # Show the full structured JSON
                query_json = response.flight_query.model_dump_json(indent=2)
                st.code(query_json, language="json")
            st.info("🚧 Agent 2 (Flight Search & Ranking) is not wired in yet. Once Shashank's code lands, results will appear here automatically.")
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.message + "\n\n```json\n" + (response.flight_query.model_dump_json(indent=2) if response.flight_query else "{}") + "\n```",
                "flight_query": response.flight_query,
            })
            st.session_state.awaiting_selection = False
            st.session_state.session = FleeAISession()

        elif response.stage == "results":
            # Show search summary
            is_mock = "MOCK" in (response.ranked_flights.options[0].flight_id if response.ranked_flights and response.ranked_flights.options else "")
            mock_badge = ' <span class="status-badge status-mock">⚠ Mock Data</span>' if is_mock else ""

            summary_msg = f"### 🔍 Search Results{mock_badge}\n\n{response.message}"
            st.markdown(summary_msg, unsafe_allow_html=True)

            if response.flight_query:
                render_query_summary(response.flight_query)

            if response.ranked_flights and response.ranked_flights.options:
                render_flight_cards(response.ranked_flights)
                select_prompt = f"\n\n👆 **Enter a number (1–{len(response.ranked_flights.options)}) to select a flight.**"
                st.markdown(select_prompt)
                st.session_state.awaiting_selection = True
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": summary_msg + select_prompt,
                    "ranked_flights": response.ranked_flights,
                    "flight_query": response.flight_query,
                })
            else:
                st.session_state.messages.append({"role": "assistant", "content": summary_msg})
                st.session_state.awaiting_selection = False

        elif response.stage == "done":
            st.markdown(response.message)
            st.session_state.messages.append({"role": "assistant", "content": response.message})
            st.session_state.awaiting_selection = False
            # Reset for next search
            st.session_state.session = FleeAISession()

        elif response.stage == "select":
            st.markdown(response.message)
            st.session_state.messages.append({"role": "assistant", "content": response.message})
            st.session_state.awaiting_selection = True

        elif response.stage == "error":
            error_msg = f"❌ {response.message}"
            st.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            st.session_state.awaiting_selection = False
            st.session_state.session = FleeAISession()

    st.rerun()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛠 About")
    st.markdown(
        "**FleeAI** is a multi-agent AI flight booking assistant.\n\n"
        "Three agents collaborate:\n"
        "1. **Query Understanding** — parses your request\n"
        "2. **Flight Search** — finds & ranks flights\n"
        "3. **Booking** — confirms your selection\n\n"
        "Built with CrewAI + Groq (free tier)."
    )
    st.divider()
    if st.button("🔄 New Search", use_container_width=True):
        st.session_state.session = FleeAISession()
        st.session_state.messages = []
        st.session_state.awaiting_selection = False
        st.rerun()
