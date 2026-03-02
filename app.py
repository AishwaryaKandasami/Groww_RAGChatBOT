import streamlit as st
import os
import json
from datetime import datetime, timedelta

# SECTION 1 — Page config (must be first Streamlit call)
st.set_page_config(
  page_title="SBI MF Facts Assistant",
  page_icon="📊",
  layout="centered",
  initial_sidebar_state="collapsed"
)

st.markdown(
    "<style>"
    "a { color: #00d09c !important; }"
    "</style>",
    unsafe_allow_html=True
)

# SECTION 3 — SECRETS HANDLING FOR STREAMLIT CLOUD
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

if not OPENAI_API_KEY or not GROQ_API_KEY:
    st.error("API keys not configured. Add OPENAI_API_KEY and GROQ_API_KEY to Streamlit secrets.")
    st.stop()

# SECTION 2 — Startup loading with spinner
from guardrails import classify_query
from retriever import _get_qdrant, _get_reranker, retrieve
from generator import generate

@st.cache_resource(show_spinner=False)
def initialize_backend():
    _get_qdrant()
    _get_reranker()
    return True

if "backend_initialized" not in st.session_state:
    with st.spinner("Setting up retrieval engine..."):
        initialize_backend()
    st.session_state.backend_initialized = True
    st.sidebar.success("✓ Knowledge base loaded")

# SECTION — DATA FRESHNESS (Run Once)
if "freshness_data" not in st.session_state:
    freshness = {}
    try:
        with open("extracted_facts.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                scheme = item.get("scheme")
                if scheme in ["SBI Large Cap", "SBI Flexi Cap", "SBI ELSS", "General"]:
                    date_fetched = item.get("date_fetched")
                    if date_fetched:
                        # Keep the most recent date if multiple entries exist
                        if scheme not in freshness or date_fetched > freshness[scheme]:
                            freshness[scheme] = date_fetched
    except Exception as e:
        print(f"Error loading freshness data: {e}")
    st.session_state.freshness_data = freshness

# PAGE LAYOUT: TWO COLUMNS
left_col, right_col = st.columns([2.2, 1])

with left_col:
    # Header
    st.title("SBI MF Facts Assistant")
    st.markdown("<p style='font-size: 0.8em; color: gray; margin-top: -15px; margin-bottom: 15px;'>Built for Groww users · Powered by official AMC & SEBI data</p>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:16px; color:#444; margin-top:-10px;'>"
        "Get instant factual answers on SBI MF schemes on Groww "
        "— expense ratios, exit loads, SIP minimums, ELSS lock-in."
        "</p>",
        unsafe_allow_html=True
    )
    st.info("ℹ️  Facts only · No investment advice · For Groww users researching SBI MF schemes · Sources: SBIMF / AMFI / SEBI · Do not share PAN, Aadhaar or account numbers.")

    # Chat history initialization
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Welcome message if no chat history
    if len(st.session_state.messages) == 0:
        st.markdown(
            "<div style='background:#fffbea; border-left:4px solid "
            "#f5a623; padding:12px 16px; border-radius:6px; "
            "font-size:14px; color:#555;'>"
            "👋 Welcome, Groww user. Ask me any factual question "
            "about SBI Large Cap, SBI Flexi Cap, or SBI ELSS Tax "
            "Saver Fund. Answers come with a verified source link. "
            "No investment advice or recommendations."
            "</div>",
            unsafe_allow_html=True
        )

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("source_label") and msg.get("source_url"):
                st.markdown(f"Source: [{msg['source_label']}]({msg['source_url']})")
            if msg.get("date_fetched"):
                st.markdown(f"Last updated from sources: {msg['date_fetched']}")

    # Example question chips
    cols = st.columns(3)
    with cols[0]:
        if st.button("SBI Large Cap expense ratio?"):
            st.session_state.preset_query = "SBI Large Cap expense ratio?"
    with cols[1]:
        if st.button("ELSS lock-in and 80C benefit?"):
            st.session_state.preset_query = "ELSS lock-in and 80C benefit?"
    with cols[2]:
        if st.button("Download capital gains from CAMS?"):
            st.session_state.preset_query = "Download capital gains from CAMS?"

with right_col:
    # SCHEME SELECTOR CARD
    st.markdown(
        """
        <div style='background:#f0fdf9; border:1.5px solid #00d09c; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,209,156,0.10);'>
            <p style='font-size:13px; font-weight:700; color:#00d09c; margin-bottom:10px;'>🎯 Select Scheme</p>
        """,
        unsafe_allow_html=True
    )
    
    st.selectbox(
        label="",
        options=[
            "All Schemes",
            "SBI Large Cap Fund",
            "SBI Flexi Cap Fund",
            "SBI ELSS Tax Saver Fund"
        ],
        key="selected_scheme",
        help="Filter answers to a specific scheme. Conflict with your question is auto-detected.",
        label_visibility="collapsed"
    )
    
    # Dynamic description logic
    selected_scheme = st.session_state.get("selected_scheme", "All Schemes")
    if selected_scheme == "All Schemes":
        desc = "Search across all 3 SBI MF schemes"
    elif selected_scheme == "SBI Large Cap Fund":
        desc = "Large cap equity · BSE 100 TRI · Very High risk"
    elif selected_scheme == "SBI Flexi Cap Fund":
        desc = "Dynamic equity · BSE 500 TRI · Very High risk"
    elif selected_scheme == "SBI ELSS Tax Saver Fund":
        desc = "Tax saving · 3-yr lock-in · 80C benefit"
    else:
        desc = "Search across all 3 SBI MF schemes"
        
    st.markdown(f"<p style='font-size:11px; color:#666; margin-top:4px;'>{desc}</p></div>", unsafe_allow_html=True)
    
    # DATA HEALTH CARD
    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    
    # Helper for formatting freshness row
    def format_freshness_row(scheme_key, short_name):
        date_str = st.session_state.freshness_data.get(scheme_key, None)
        if not date_str:
            return "🔴", short_name, "Unknown", "Unknown"
            
        try:
            last_updated_dt = datetime.strptime(date_str, "%Y-%m-%d")
            next_refresh_dt = last_updated_dt + timedelta(days=30)
            
            days_since = (datetime.now() - last_updated_dt).days
            
            if days_since <= 7:
                icon = "🟢"
            elif days_since <= 30:
                icon = "🟡"
            else:
                icon = "🔴"
                
            return icon, short_name, last_updated_dt.strftime("%d %b %Y"), next_refresh_dt.strftime("%d %b %Y")
        except:
            return "🔴", short_name, "Unknown", "Unknown"

    lc_icon, _, lc_updated, lc_next = format_freshness_row("SBI Large Cap", "Large Cap")
    fc_icon, _, fc_updated, fc_next = format_freshness_row("SBI Flexi Cap", "Flexi Cap")
    elss_icon, _, elss_updated, elss_next = format_freshness_row("SBI ELSS", "ELSS")
    gen_icon, _, gen_updated, gen_next = format_freshness_row("General", "AMFI / SEBI")

    st.markdown(f"""
    <div style='background:#fafafa; border:1px solid #e0e0e0; border-radius:12px; padding:16px; box-shadow:0 2px 6px rgba(0,0,0,0.06);'>
      <p style='font-size:13px; font-weight:700; color:#444; margin-bottom:12px;'>📅 Data Health</p>
      
      <p style='font-size:12px; color:#333; margin:4px 0;'>{lc_icon} <b>Large Cap</b></p>
      <p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {lc_updated} · Next: {lc_next}</p>
      
      <p style='font-size:12px; color:#333; margin:4px 0;'>{fc_icon} <b>Flexi Cap</b></p>
      <p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {fc_updated} · Next: {fc_next}</p>
      
      <p style='font-size:12px; color:#333; margin:4px 0;'>{elss_icon} <b>ELSS</b></p>
      <p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {elss_updated} · Next: {elss_next}</p>
      
      <p style='font-size:12px; color:#333; margin:4px 0;'>{gen_icon} <b>AMFI / SEBI</b></p>
      <p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {gen_updated} · Next: {gen_next}</p>
      
      <hr style='border:none; border-top:1px solid #eee; margin:10px 0;'/>
      <p style='font-size:10px; color:#999; margin:0;'>TER and riskometer refresh monthly. Exit load and SIP minimums are stable.</p>
    </div>
    """, unsafe_allow_html=True)


with left_col:
    # Use the preset query if a button was clicked
    user_input = st.chat_input("Ask about SBI MF schemes on Groww...")
    preset_query = st.session_state.pop("preset_query", None)
    if preset_query:
        user_input = preset_query

    def detect_query_scheme(query: str):
        # Returns scheme name if detected in query text
        # Returns None if no scheme detected
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["large cap", "largecap", "bluechip", "blue chip"]):
            return "SBI Large Cap Fund"
        
        if any(term in query_lower for term in ["flexi cap", "flexicap", "flexi-cap"]):
            return "SBI Flexi Cap Fund"
        
        if any(term in query_lower for term in ["elss", "tax saver", "long term equity", "80c"]):
            return "SBI ELSS Tax Saver Fund"
        
        return None

    # SECTION 6 — Chat input and pipeline
    if user_input:
        # 1. Display user message immediately
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        selected = st.session_state.selected_scheme
        detected = detect_query_scheme(user_input)

        # Case 1 — No conflict: All Schemes selected
        if selected == "All Schemes":
            scheme_filter = None
            conflict = False

        # Case 2 — No conflict: selection matches query
        elif detected is None or detected == selected:
            scheme_filter = selected
            conflict = False

        # Case 3 — CONFLICT: query mentions different scheme
        else:
            scheme_filter = None
            conflict = True
            conflict_message = (
                f"Your question mentions {detected} but "
                f"your filter is set to {selected}. "
                f"Searching across all schemes to give "
                f"you the most relevant answer."
            )

        SCHEME_FILTER_MAP = {
            "All Schemes": None,
            "SBI Large Cap Fund": "SBI Large Cap",
            "SBI Flexi Cap Fund": "SBI Flexi Cap",
            "SBI ELSS Tax Saver Fund": "SBI ELSS"
        }
        scheme_filter = SCHEME_FILTER_MAP[selected] if not conflict else None

        # 2. Show spinner for retrieval
        if conflict:
            st.warning(conflict_message)

        with st.chat_message("assistant"):
            with st.spinner("Retrieving answer..."):
                try:
                    # 3. Call classify_query
                    classification = classify_query(user_input)
                    action = classification.get("action")

                    if action == "retrieve":
                        chunks = retrieve(
                            user_input,
                            scheme_filter=scheme_filter,
                            api_key=OPENAI_API_KEY
                        )
                        result = generate(user_input, chunks, api_key=GROQ_API_KEY)
                        
                        answer = result["answer"]
                        source_label = result.get("source_label", "")
                        source_url = result.get("source_url", "")
                        date_fetched = result.get("date_fetched", "")

                        st.markdown(answer)
                        if source_label and source_url:
                            st.markdown(f"Source: [{source_label}]({source_url})")
                        if date_fetched:
                            st.markdown(f"Last updated from sources: {date_fetched}")
                            
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "source_label": source_label,
                            "source_url": source_url,
                            "date_fetched": date_fetched
                        })

                    elif action == "refuse_advice":
                        answer = "I cannot provide investment advice. Please consult a registered investment advisor."
                        link = "amfiindia.com/investor-corner"
                        st.markdown(answer)
                        st.markdown(f"[{link}](https://{link})")
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer + f"\n\n[{link}](https://{link})"
                        })

                    elif action == "fallback":
                        answer = "This query is outside my current scope (SBI Large Cap, Flexi Cap, ELSS only). Please visit sbimf.com for other schemes."
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})

                    elif action == "block_pii":
                        answer = "Please do not share personal identifiers. I can only answer factual questions about scheme features."
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        
                except Exception as e:
                    # ERROR HANDLING
                    print(f"Pipeline error: {e}")
                    st.error("Unable to retrieve answer. Please try again or visit sbimf.com directly.")

# SECTION 7 — Footer
st.markdown("---")
st.markdown(
    "<div style='font-size:11px; color:#888; "
    "padding:16px 0; line-height:1.6;'>"
    "For Groww users only &nbsp;·&nbsp; "
    "Facts sourced from sbimf.com, amfiindia.com, "
    "sebi.gov.in &nbsp;·&nbsp; "
    "This tool is not affiliated with or endorsed by Groww "
    "&nbsp;·&nbsp; "
    "Mutual fund investments are subject to market risks "
    "&nbsp;·&nbsp; "
    "Read all scheme documents carefully before investing."
    "</div>",
    unsafe_allow_html=True
)
