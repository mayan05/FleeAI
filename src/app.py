"""
FleeAI — Streamlit Chat UI

Provides a conversational interface for the flight booking pipeline:
    1. User types a flight request
    2. Agent 1 parses it; if info is missing, asks a clarification question
    3. Once complete, searches for flights and displays ranked results as cards
    4. User selects a flight (booking wired in Day 3)

Run with:  streamlit run src/app.py
"""

import sys
import os

# Ensure the project root (parent of this file's directory) is on the path
# so `from src.xxx import ...` works when Streamlit runs this file directly.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Load .env before any agent/API imports so DUFFEL_ACCESS_TOKEN and
# GROQ_API_KEY are available in os.environ when the modules are imported.
from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"))

import streamlit as st
# pyrefly: ignore [missing-import]
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

    /* Search form panel — style the native Streamlit form container directly */
    div[data-testid="stForm"] {
        background: linear-gradient(145deg, #13111c 0%, #1e1b4b 100%) !important;
        border: 1px solid #4338ca !important;
        border-radius: 20px !important;
        padding: 1.75rem 2rem 1.25rem 2rem !important;
        margin-bottom: 1.75rem !important;
    }

    /* Style the Streamlit text_input & date_input labels inside the panel */
    div[data-testid="stForm"] label {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        color: #94a3b8 !important;
    }
    div[data-testid="stForm"] input {
        background: #0f0e1a !important;
        border: 1px solid #3730a3 !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
    }
    div[data-testid="stForm"] input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
    }
    /* Search button */
    div[data-testid="stForm"] button[kind="primaryFormSubmit"],
    div[data-testid="stForm"] button[data-testid="baseButton-primaryFormSubmit"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        border: none !important;
        border-radius: 10px !important;
        color: #fff !important;
        font-weight: 600 !important;
        width: 100% !important;
        padding: 0.6rem 0 !important;
        margin-top: 0.5rem !important;
        transition: opacity 0.2s ease !important;
    }
    div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
        opacity: 0.88 !important;
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

    /* Booking confirmation card */
    .booking-card {
        background: linear-gradient(145deg, #052e16 0%, #14532d 100%);
        border: 1px solid #16a34a;
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1rem;
        color: #dcfce7;
    }
    .booking-card .pnr {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        color: #4ade80;
        margin-bottom: 0.5rem;
    }
    .booking-card .booking-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #86efac;
        margin-bottom: 0.2rem;
    }
    .booking-card .booking-route {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    .booking-card .booking-meta {
        display: flex;
        gap: 2rem;
        font-size: 0.9rem;
        color: #bbf7d0;
        margin-bottom: 0.75rem;
    }
    .booking-card .booking-summary {
        font-size: 0.9rem;
        color: #86efac;
        border-top: 1px solid #166534;
        padding-top: 0.75rem;
        margin-top: 0.5rem;
    }
    .status-confirmed {
        background: #dcfce7;
        color: #14532d;
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
if "search_submitted" not in st.session_state:
    st.session_state.search_submitted = False


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


def render_booking_confirmation(confirmation):
    """Render a booking confirmation as a premium green card."""
    f = confirmation.selected_flight
    dep_time = f.departure_time.split("T")[-1][:5] if "T" in f.departure_time else f.departure_time
    arr_time = f.arrival_time.split("T")[-1][:5] if "T" in f.arrival_time else f.arrival_time
    stops_text = "Direct" if f.stops == 0 else f"{f.stops} stop{'s' if f.stops > 1 else ''}"
    status_class = "status-confirmed" if confirmation.status == "CONFIRMED" else "status-badge"

    st.markdown(
        f"""
        <div class="booking-card">
            <div class="booking-label">Booking Reference (PNR)</div>
            <div class="pnr">{confirmation.pnr}</div>
            <div class="booking-route">
                ✈ {f.airline} &nbsp;·&nbsp; {f.origin} → {f.destination}
            </div>
            <div class="booking-meta">
                <span>🕐 {dep_time} – {arr_time}</span>
                <span>🔄 {stops_text}</span>
                <span>👥 {confirmation.passenger_count} passenger{'s' if confirmation.passenger_count > 1 else ''}</span>
                <span>💰 ₹{confirmation.total_price_inr:,}</span>
                <span class="status-badge {status_class}">{confirmation.status}</span>
            </div>
            <div class="booking-summary">📋 {confirmation.itinerary_summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Render chat history ─────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

        # Re-render flight cards if this message had them
        if msg.get("ranked_flights"):
            render_flight_cards(msg["ranked_flights"])

        if msg.get("flight_query"):
            render_query_summary(msg["flight_query"])

        if msg.get("booking_confirmation"):
            render_booking_confirmation(msg["booking_confirmation"])


# ── Search form (shown only while session is idle / not yet submitted) ───────
if not st.session_state.search_submitted:
    st.markdown('<div class="search-panel-title" style="font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:#6366f1;margin-bottom:0.5rem;">🔍 Plan your trip</div>', unsafe_allow_html=True)

    with st.form(key="flight_search_form", border=False):
        col1, col2, col3 = st.columns([2, 2, 1.5])
        with col1:
            form_origin = st.text_input(
                "From",
                placeholder="e.g. Bangalore, BLR",
                key="form_origin",
            )
        with col2:
            form_destination = st.text_input(
                "To",
                placeholder="e.g. Delhi, DEL",
                key="form_destination",
            )
        with col3:
            import datetime
            form_date = st.date_input(
                "Departure date",
                value=None,
                min_value=datetime.date.today(),
                key="form_date",
                format="YYYY-MM-DD",
            )

        search_clicked = st.form_submit_button("✈ Search Flights", use_container_width=True)

    if search_clicked:
        if not form_origin or not form_destination:
            st.warning("Please fill in both **From** and **To** fields before searching.")
        else:
            # Build a natural-language query the orchestrator understands
            date_part = f" on {form_date}" if form_date else ""
            auto_prompt = f"I want to fly from {form_origin} to {form_destination}{date_part}."

            st.session_state.search_submitted = True
            st.session_state.messages.append({"role": "user", "content": auto_prompt})

            session: FleeAISession = st.session_state.session
            with st.spinner("🧠 Understanding your request..."):
                response = session.start(auto_prompt)

            # --- identical response-handling logic used in the chat block below ---
            if response.stage == "clarification":
                msg_content = f"🤔 {response.clarification_question}"
                st.session_state.messages.append({"role": "assistant", "content": msg_content})
                st.session_state.awaiting_selection = False

            elif response.stage == "query_complete":
                msg_content = response.message
                if response.flight_query:
                    query_json = response.flight_query.model_dump_json(indent=2)
                    msg_content += "\n\n```json\n" + query_json + "\n```"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": msg_content,
                    "flight_query": response.flight_query,
                })
                st.session_state.awaiting_selection = False
                st.session_state.session = FleeAISession()

            elif response.stage == "results":
                is_mock = "MOCK" in (response.ranked_flights.options[0].flight_id if response.ranked_flights and response.ranked_flights.options else "")
                mock_badge = ' <span class="status-badge status-mock">⚠ Mock Data</span>' if is_mock else ""
                summary_msg = f"### 🔍 Search Results{mock_badge}\n\n{response.message}"
                if response.ranked_flights and response.ranked_flights.options:
                    select_prompt = f"\n\n👆 **Enter a number (1–{len(response.ranked_flights.options)}) to select a flight.**"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": summary_msg + select_prompt,
                        "ranked_flights": response.ranked_flights,
                        "flight_query": response.flight_query,
                    })
                    st.session_state.awaiting_selection = True
                else:
                    st.session_state.messages.append({"role": "assistant", "content": summary_msg})
                    st.session_state.awaiting_selection = False
                    st.session_state.session = FleeAISession()

            elif response.stage == "error":
                st.session_state.messages.append({"role": "assistant", "content": f"❌ {response.message}"})
                st.session_state.awaiting_selection = False
                st.session_state.session = FleeAISession()

            else:
                st.session_state.messages.append({"role": "assistant", "content": response.message})

            st.rerun()


# ── Chat input (only shown after a search has been submitted) ────────────────
if st.session_state.search_submitted and (prompt := st.chat_input(
    "Select a flight number..." if st.session_state.awaiting_selection
    else "Add more details or ask a question..."
)):
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
                # No options to select from (no flights / budget too low) --
                # reset so the user's next message starts a fresh search
                # instead of hitting "I wasn't expecting input at this point."
                st.session_state.session = FleeAISession()

        elif response.stage == "booking":
            # Agent 3 succeeded — render full booking confirmation card
            st.markdown(f"### 🎉 {response.message}")
            if response.booking_confirmation:
                render_booking_confirmation(response.booking_confirmation)
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"### 🎉 {response.message}",
                "booking_confirmation": response.booking_confirmation,
            })
            st.session_state.awaiting_selection = False
            # Reset session for the next search
            st.session_state.session = FleeAISession()

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

        elif response.stage == "reset":
            # User asked to restart mid-flow (e.g. typed "restart" while
            # answering a clarification question or picking a flight)
            st.markdown(f"🔄 {response.message}")
            st.session_state.messages.append({"role": "assistant", "content": f"🔄 {response.message}"})
            st.session_state.awaiting_selection = False

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
    )
    st.divider()
    if st.button("🔄 New Search", use_container_width=True):
        st.session_state.session = FleeAISession()
        st.session_state.messages = []
        st.session_state.awaiting_selection = False
        st.session_state.search_submitted = False
        st.rerun()