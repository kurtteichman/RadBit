import json
import os
from datetime import datetime
import streamlit as st
from agents import set_default_openai_key, InputGuardrailTripwireTriggered
from radbit import triage_and_get_support_info

set_default_openai_key(st.secrets["OPENAI_API_KEY"])
st.set_page_config(page_title="Radiology Support", layout="wide")

HISTORY_FILE = "triage_history.json"

if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "triage_result" not in st.session_state:
    st.session_state.triage_result = None
if "show_email_draft" not in st.session_state:
    st.session_state.show_email_draft = False
if "last_submitted_input" not in st.session_state:
    st.session_state.last_submitted_input = ""
if "history" not in st.session_state:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            st.session_state.history = json.load(f)
    else:
        st.session_state.history = []

st.title("Radiology Support Portal")
st.markdown("Please describe your issue below and we’ll route you to the correct support group and provide contact options.")
st.markdown('<style>textarea, .stTextInput, .stTextArea, .stSelectbox, .stButton > button { border: 1px solid #ccc; border-radius: 4px; }</style>', unsafe_allow_html=True)

st.divider()
left, right = st.columns([1.25, 1.75], gap="large")

with left:
    st.subheader("Describe Your Issue")
    current_input = st.text_area("", value=st.session_state.user_input, height=200, label_visibility="collapsed")
    submit = st.button("Submit Request", use_container_width=True)

    if current_input.strip() != st.session_state.user_input.strip():
        st.session_state.triage_result = None
        st.session_state.show_email_draft = False

    st.session_state.user_input = current_input

    if submit and current_input.strip():
        try:
            with st.spinner("Identifying your request..."):
                result = triage_and_get_support_info(current_input.strip())
                st.session_state.triage_result = result
                st.session_state.show_email_draft = True
                st.session_state.last_submitted_input = current_input.strip()
                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "input": current_input.strip(),
                    "department": result.department,
                    "contact_info": {
                        "Department": result.department,
                        "Phone": result.phone,
                        "Email": result.email,
                        "Other Info": result.other,
                        "Note": result.note,
                        "Availability": result.hours
                    }
                }
                st.session_state.history.append(entry)
                with open(HISTORY_FILE, "w") as f:
                    json.dump(st.session_state.history, f, indent=2)
        except InputGuardrailTripwireTriggered:
            st.session_state.triage_result = None
            st.session_state.show_email_draft = False
            st.error("This tool only supports questions related to radiology support — please enter a relevant issue.")

    if st.session_state.triage_result:
        result = st.session_state.triage_result
        st.markdown("### Recommended Support Contact")
        st.markdown(f"**Department:** {result.department}")
        st.markdown(f"**Phone:** {result.phone}")
        st.markdown(f"**Email:** {result.email}")
        st.markdown(f"**Other Info:** {result.other}")
        st.markdown(f"**Note:** {result.note}")
        st.markdown(f"**Availability:** {result.hours}")

with right:
    if st.session_state.triage_result and st.session_state.show_email_draft:
        st.subheader("Email Draft")
        st.text_area("Edit before sending", value=st.session_state.triage_result.email_draft, height=400, key="email_draft_box")
        st.button("Send Email", disabled=True)

st.divider()
with st.expander("Request History", expanded=False):
    if st.button("Clear History"):
        st.session_state.history = []
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    for entry in reversed(st.session_state.history[-10:]):
        st.markdown(f"**{entry['timestamp']}**")
        st.markdown(f"- Input: {entry['input']}")
        st.markdown(f"- Department: {entry['department']}")
        with st.expander("View Recommended Support Contact"):
            info = entry['contact_info']
            for k, v in info.items():
                st.markdown(f"**{k}:** {v}")
