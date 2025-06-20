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

st.title("Radbit Support Portal")
st.markdown("Please describe your issue below and we’ll route you to the correct support group and provide contact options.")

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
                combined_info = ""
                if result.other and result.other != "N/A":
                    combined_info += result.other.strip()
                if result.note and result.note != "N/A":
                    if combined_info:
                        combined_info += "\n" + result.note.strip()
                    else:
                        combined_info += result.note.strip()
                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "input": current_input.strip(),
                    "department": result.department,
                    "contact_info": {
                        "Department": result.department,
                        "Phone": result.phone,
                        "Email": result.email,
                        "Availability": result.hours,
                        "Additional Info": combined_info
                    }
                }
                st.session_state.history.append(entry)
                with open(HISTORY_FILE, "w") as f:
                    json.dump(st.session_state.history, f, indent=2)
        except InputGuardrailTripwireTriggered:
            st.session_state.triage_result = None
            st.session_state.show_email_draft = False
            st.error("This tool only supports questions related to radiology support — please enter a relevant issue.")
