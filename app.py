import streamlit as st
import os
import json
import re
from datetime import datetime, timedelta

# SECTION 1 - Page config (must be first Streamlit call)
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

# SECTION 3 - SECRETS HANDLING FOR STREAMLIT CLOUD
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

if not OPENAI_API_KEY or not GROQ_API_KEY:
    st.error("API keys not configured. Add OPENAI_API_KEY and GROQ_API_KEY to Streamlit secrets.")
    st.stop()

# SECTION 2 - Startup loading with spinner
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

def detect_answer_topic(chunks: list) -> str:
    # Returns topic of top retrieved chunk
    # Used to select correct card template
    if not chunks:
        return "general"
    top_chunk = chunks[0]
    topic = top_chunk.get("topic", "general")
    return topic

def render_answer_card(topic: str, answer: str, source_url: str, source_label: str, date_fetched: str, scheme: str) -> str:
    colors = {
        "expense_ratio": "#00d09c",
        "exit_load": "#f5a623",
        "min_sip": "#4a90d9",
        "lock_in": "#9b59b6",
        "riskometer": "#e74c3c",
        "benchmark": "#2ecc71",
        "statement_download": "#1abc9c",
        "scheme_category": "#95a5a6",
        "general": "#bdc3c7",
        "refusal": "#e74c3c",
        "pii": "#e74c3c"
    }
    
    topic_color = colors.get(topic, "#bdc3c7")
    
    base_style = f"background: white; border-radius: 12px; border-left: 4px solid {topic_color}; padding: 16px; margin: 4px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.07); font-family: sans-serif;"
    
    badge_html = ""
    if topic not in ["statement_download", "general", "refusal", "pii"]:
        badges = {
            "SBI Large Cap": {"bg": "#e8f4fd", "color": "#2980b9"},
            "SBI Flexi Cap": {"bg": "#fef9e7", "color": "#f39c12"},
            "SBI ELSS": {"bg": "#eafaf1", "color": "#27ae60"},
            "General": {"bg": "#f2f3f4", "color": "#7f8c8d"}
        }
        b = badges.get(scheme, badges["General"])
        if scheme != "General":
            badge_html = f"<span style='background:{b['bg']}; color:{b['color']}; font-size:11px; font-weight:600; padding:3px 10px; border-radius:20px; display:inline-block; margin-bottom:10px;'>{scheme}</span><br>"
    
    source_row = ""
    if topic not in ["pii", "refusal"] and (source_url or source_label or date_fetched):
        source_link = f"<a href='{source_url}' target='_blank' style='font-size:11px; color:#00d09c; text-decoration:none;'>🔗 {source_label}</a>" if (source_url and source_label) else ""
        date_span = f"<span style='font-size:10px; color:#999;'>Last updated: {date_fetched}</span>" if date_fetched else ""
        source_row = f"<div style='margin-top:12px; padding-top:10px; border-top:1px solid #f0f0f0; display:flex; justify-content:space-between; align-items:center;'>{source_link}{date_span}</div>"

    content_html = ""
    
    if topic == "expense_ratio":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>💰 Expense Ratio</div>"
        reg_match = re.search(r"Regular[^0-9]*([0-9]+\.[0-9]+)%", answer, re.IGNORECASE)
        dir_match = re.search(r"Direct[^0-9]*([0-9]+\.[0-9]+)%", answer, re.IGNORECASE)
        extracted_html = ""
        if reg_match or dir_match:
            reg_val = reg_match.group(1) + "%" if reg_match else "N/A"
            dir_val = dir_match.group(1) + "%" if dir_match else "N/A"
            extracted_html = f"<div style='display:flex; gap:10px; margin-top:10px;'><div style='flex:1; background:#f9f9f9; padding:10px; border-radius:8px; border:1px solid #eaeaea;'><div style='font-size:11px; color:#666;'>Regular Plan</div><div style='font-size:16px; font-weight:bold; color:#333;'>{reg_val}</div></div><div style='flex:1; background:#f9f9f9; padding:10px; border-radius:8px; border:1px solid #eaeaea;'><div style='font-size:11px; color:#666;'>Direct Plan</div><div style='font-size:16px; font-weight:bold; color:#333;'>{dir_val}</div></div></div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + extracted_html
        
    elif topic == "exit_load":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>🚪 Exit Load</div>"
        timeline_html = ""
        if "days" in answer.lower():
            if "90" in answer:
                m1 = re.search(r"([0-9.]+%)[^0-9]*30 days", answer)
                m2 = re.search(r"([0-9.]+%)[^0-9]*90 days", answer)
                v1 = m1.group(1) if m1 else "X%"
                v2 = m2.group(1) if m2 else "X%"
                timeline_html = f"<div style='background:#fdf5e6; padding:10px; border-radius:8px; margin-top:10px; font-size:13px; font-weight:500; text-align:center;'>[0-30 days: {v1}] &rarr; [31-90 days: {v2}] &rarr; [90+ days: Nil]</div>"
            else:
                m1 = re.search(r"([0-9.]+%)[^0-9]*30 days", answer)
                v1 = m1.group(1) if m1 else "X%"
                timeline_html = f"<div style='background:#fdf5e6; padding:10px; border-radius:8px; margin-top:10px; font-size:13px; font-weight:500; text-align:center;'>[0-30 days: {v1}] &rarr; [30+ days: Nil]</div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + timeline_html
        
    elif topic == "min_sip":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>📅 Minimum Investment</div>"
        sip_match = re.search(r"SIP[^₹]*₹\s*([0-9,]+)", answer, re.IGNORECASE)
        lump_match = re.search(r"(?:lump.sum|one.time)[^₹]*₹\s*([0-9,]+)", answer, re.IGNORECASE)
        boxes_html = ""
        if sip_match and lump_match:
            boxes_html = f"<div style='display:flex; gap:10px; margin-top:10px;'><div style='flex:1; background:#eaf2f8; padding:10px; border-radius:8px; border:1px solid #d4e6f1;'><div style='font-size:11px; color:#2980b9;'>SIP</div><div style='font-size:15px; font-weight:bold; color:#1f618d;'>₹{sip_match.group(1)}</div></div><div style='flex:1; background:#eaf2f8; padding:10px; border-radius:8px; border:1px solid #d4e6f1;'><div style='font-size:11px; color:#2980b9;'>Lump Sum</div><div style='font-size:15px; font-weight:bold; color:#1f618d;'>₹{lump_match.group(1)}</div></div></div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + boxes_html
        
    elif topic == "lock_in":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>🔒 Lock-in Period</div>"
        highlight = "<div style='background:#f3e8ff; border:1px solid #9b59b6; padding:10px; border-radius:8px; margin-top:10px; font-size:13px; color:#5b2c6f;'><b>⏳ 3 Years from date of each allotment</b><br><b>📋 Section 80C tax benefit applicable</b></div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + highlight
        
    elif topic == "riskometer":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>⚠️ Risk Level</div>"
        is_very_high = "very high" in answer.lower()
        active_color = "#e74c3c"
        segments = ["Low", "Low-Mod", "Mod", "Mod-High", "High", "Very High"]
        bars = []
        for s in segments:
            if s == "Very High" and is_very_high:
                bars.append(f"<div style='flex:1; text-align:center; background:{active_color}; color:white; font-size:10px; padding:4px 0; border-radius:4px; font-weight:bold;'>{s}</div>")
            elif "high" in answer.lower() and not is_very_high and s == "High":
                 bars.append(f"<div style='flex:1; text-align:center; background:{active_color}; color:white; font-size:10px; padding:4px 0; border-radius:4px; font-weight:bold;'>{s}</div>")
            else:
                bars.append(f"<div style='flex:1; text-align:center; background:#ecf0f1; color:#95a5a6; font-size:10px; padding:4px 0; border-radius:4px;'>{s}</div>")
        bar_html = f"<div style='display:flex; gap:4px; margin-top:12px;'>{''.join(bars)}</div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + bar_html

    elif topic == "benchmark":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>📊 Benchmark Index</div>"
        idx = ""
        if "BSE 100 TRI" in answer: idx = "BSE 100 TRI"
        elif "S&P BSE 500 TRI" in answer: idx = "S&P BSE 500 TRI" 
        elif "BSE 500 TRI" in answer: idx = "BSE 500 TRI"
        idx_html = ""
        if idx:
            idx_html = f"<div style='background:#eafaf1; border:1px solid #2ecc71; padding:10px; border-radius:8px; margin-top:10px; font-size:14px; color:#1d8348; text-align:center;'><b>{idx}</b></div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + idx_html

    elif topic == "statement_download":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px;'>📥 Download Statement</div>"
        steps_html = "<div style='margin-top:12px; display:flex; flex-direction:column; gap:6px;'><div style='background:#e8f8f5; border-left:3px solid #1abc9c; padding:6px 10px; font-size:12px; color:#117864;'><b>Step 1 &rarr;</b> Visit camsonline.com</div><div style='background:#e8f8f5; border-left:3px solid #1abc9c; padding:6px 10px; font-size:12px; color:#117864;'><b>Step 2 &rarr;</b> Select Consolidated Account Statement</div><div style='background:#e8f8f5; border-left:3px solid #1abc9c; padding:6px 10px; font-size:12px; color:#117864;'><b>Step 3 &rarr;</b> Enter PAN and registered email</div><div style='background:#e8f8f5; border-left:3px solid #1abc9c; padding:6px 10px; font-size:12px; color:#117864;'><b>Step 4 &rarr;</b> Select financial year</div><div style='background:#e8f8f5; border-left:3px solid #1abc9c; padding:6px 10px; font-size:12px; color:#117864;'><b>Step 5 &rarr;</b> Statement sent to email</div></div>"
        content_html = header + badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>" + steps_html

    elif topic == "refusal":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px; color:#e74c3c;'>🚫 Outside Scope</div>"
        content_html = header + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div><div style='margin-top:10px;'><a href='https://amfiindia.com/investor-corner' target='_blank' style='font-size:12px; color:#00d09c; text-decoration:none;'>amfiindia.com/investor-corner</a></div>"

    elif topic == "pii":
        header = "<div style='font-weight:bold; font-size:16px; margin-bottom:8px; color:#e74c3c;'>🔒 Personal Data Detected</div>"
        content_html = header + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>"

    else:
        content_html = badge_html + f"<div style='font-size:14px; color:#444; line-height:1.5;'>{answer}</div>"

    card = f"<div style='{base_style}'>{content_html}{source_row}</div>"
    return card

# SECTION - DATA FRESHNESS (Run Once)
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
    st.markdown("<p style='font-size: 0.8em; color: gray; margin-top: -15px; margin-bottom: 15px;'>Built for Groww users &middot; Powered by official AMC & SEBI data</p>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:16px; color:#444; margin-top:-10px;'>"
        "Get instant factual answers on SBI MF schemes on Groww "
        "&mdash; expense ratios, exit loads, SIP minimums, ELSS lock-in."
        "</p>",
        unsafe_allow_html=True
    )
    st.info("ℹ️  Facts only &middot; No investment advice &middot; For Groww users researching SBI MF schemes &middot; Sources: SBIMF / AMFI / SEBI &middot; Do not share PAN, Aadhaar or account numbers.")

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
            if msg.get("is_html"):
                st.markdown(msg["content"], unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])

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
        "<div style='background:#f0fdf9; border:1.5px solid #00d09c; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,209,156,0.10);'>"
        "<p style='font-size:13px; font-weight:700; color:#00d09c; margin-bottom:10px;'>🎯 Select Scheme</p>",
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
        desc = "Large cap equity &middot; BSE 100 TRI &middot; Very High risk"
    elif selected_scheme == "SBI Flexi Cap Fund":
        desc = "Dynamic equity &middot; BSE 500 TRI &middot; Very High risk"
    elif selected_scheme == "SBI ELSS Tax Saver Fund":
        desc = "Tax saving &middot; 3-yr lock-in &middot; 80C benefit"
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

    st.markdown(
        "<div style='background:#fafafa; border:1px solid #e0e0e0; border-radius:12px; padding:16px; box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
        "<p style='font-size:13px; font-weight:700; color:#444; margin-bottom:12px;'>📅 Data Health</p>"
        f"<p style='font-size:12px; color:#333; margin:4px 0;'>{lc_icon} <b>Large Cap</b></p>"
        f"<p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {lc_updated} &middot; Next: {lc_next}</p>"
        f"<p style='font-size:12px; color:#333; margin:4px 0;'>{fc_icon} <b>Flexi Cap</b></p>"
        f"<p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {fc_updated} &middot; Next: {fc_next}</p>"
        f"<p style='font-size:12px; color:#333; margin:4px 0;'>{elss_icon} <b>ELSS</b></p>"
        f"<p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {elss_updated} &middot; Next: {elss_next}</p>"
        f"<p style='font-size:12px; color:#333; margin:4px 0;'>{gen_icon} <b>AMFI / SEBI</b></p>"
        f"<p style='font-size:11px; color:#666; margin:0 0 8px 16px;'>Updated: {gen_updated} &middot; Next: {gen_next}</p>"
        "<hr style='border:none; border-top:1px solid #eee; margin:10px 0;'/>"
        "<p style='font-size:10px; color:#999; margin:0;'>TER and riskometer refresh monthly. Exit load and SIP minimums are stable.</p>"
        "</div>", 
        unsafe_allow_html=True
    )


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

    # SECTION 6 - Chat input and pipeline
    if user_input:
        # 1. Display user message immediately
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        selected = st.session_state.selected_scheme
        detected = detect_query_scheme(user_input)

        # Case 1 - No conflict: All Schemes selected
        if selected == "All Schemes":
            scheme_filter = None
            conflict = False

        # Case 2 - No conflict: selection matches query
        elif detected is None or detected == selected:
            scheme_filter = selected
            conflict = False

        # Case 3 - CONFLICT: query mentions different scheme
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
                        
                        answer_topic = detect_answer_topic(chunks)
                        scheme_val = chunks[0].get("scheme", "General") if chunks else "General"

                        card_html = render_answer_card(
                            topic=answer_topic,
                            answer=answer,
                            source_url=source_url,
                            source_label=source_label,
                            date_fetched=date_fetched,
                            scheme=scheme_val
                        )

                        st.markdown(card_html, unsafe_allow_html=True)
                            
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": card_html,
                            "is_html": True
                        })

                    elif action == "refuse_advice":
                        answer = "I cannot provide investment advice. Please consult a registered investment advisor."
                        
                        card_html = render_answer_card(
                            topic="refusal",
                            answer=answer,
                            source_url="",
                            source_label="",
                            date_fetched="",
                            scheme="General"
                        )
                        st.markdown(card_html, unsafe_allow_html=True)

                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": card_html,
                            "is_html": True
                        })

                    elif action == "fallback":
                        answer = "This query is outside my current scope (SBI Large Cap, Flexi Cap, ELSS only). Please visit sbimf.com for other schemes."
                        card_html = render_answer_card(
                            topic="general",
                            answer=answer,
                            source_url="",
                            source_label="",
                            date_fetched="",
                            scheme="General"
                        )
                        st.markdown(card_html, unsafe_allow_html=True)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": card_html,
                            "is_html": True
                        })

                    elif action == "block_pii":
                        answer = "Please do not share personal identifiers. I can only answer factual questions about scheme features."
                        card_html = render_answer_card(
                            topic="pii",
                            answer=answer,
                            source_url="",
                            source_label="",
                            date_fetched="",
                            scheme="General"
                        )
                        st.markdown(card_html, unsafe_allow_html=True)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": card_html,
                            "is_html": True
                        })
                        
                except Exception as e:
                    # ERROR HANDLING
                    print(f"Pipeline error: {e}")
                    st.error("Unable to retrieve answer. Please try again or visit sbimf.com directly.")

# SECTION 7 - Footer
st.markdown("---")
st.markdown(
    "<div style='font-size:11px; color:#888; "
    "padding:16px 0; line-height:1.6;'>"
    "For Groww users only &nbsp;&middot;&nbsp; "
    "Facts sourced from sbimf.com, amfiindia.com, "
    "sebi.gov.in &nbsp;&middot;&nbsp; "
    "This tool is not affiliated with or endorsed by Groww "
    "&nbsp;&middot;&nbsp; "
    "Mutual fund investments are subject to market risks "
    "&nbsp;&middot;&nbsp; "
    "Read all scheme documents carefully before investing."
    "</div>",
    unsafe_allow_html=True
)
