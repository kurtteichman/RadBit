import json
import os
from datetime import datetime
import streamlit as st
from agents import set_default_openai_key, InputGuardrailTripwireTriggered
from radbit import triage_and_get_support_info, generate_faqs, load_backend_json

set_default_openai_key(st.secrets["OPENAI_API_KEY"])
st.set_page_config(page_title="Radiology Support", layout="wide")

backend_meta = load_backend_json()
ts = backend_meta["timestamp"]

with st.sidebar:
    st.markdown("### System Timestamp")
    st.markdown(f"**Date:** {ts['date']}")
    st.markdown(f"**Time:** {ts['time']}")
    st.markdown(f"**Day:** {ts['day_of_week']}")

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

st.divider()
left, right = st.columns([1.25, 1.75], gap="large")

with left:
    st.subheader("Describe Your Issue")
    current_input = st.text_area("Your issue", value=st.session_state.user_input, height=200)
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
                        "Availability": result.hours,
                        "Support Available": "Yes" if result.support_available else "No",
                        "Fallback": result.fallback_department or "None"
                    }
                }
                st.session_state.history.append(entry)
                with open(HISTORY_FILE, "w") as f:
                    json.dump(st.session_state.history, f, indent=2)
        except InputGuardrailTripwireTriggered:
            st.session_state.triage_result = None
            st.session_state.show_email_draft = False
            st.error("This tool only supports questions related to radiology support — please enter a relevant issue.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

    if st.session_state.triage_result:
        r = st.session_state.triage_result
        st.markdown("### Recommended Support Contact")
        st.markdown(f"**Department:** {r.department}")
        st.markdown(f"**Phone:** {r.phone}")
        if "\n" in r.email:
            for line in r.email.strip().split("\n"):
                if line.strip():
                    st.markdown(f"{line}")
        else:
            st.markdown(f"**Email:** {r.email}")
        st.markdown(f"**Other Info:** {r.other}")
        st.markdown(f"**Note:** {r.note}")
        st.markdown(f"**Availability:** {r.hours}")
        if not r.support_available:
            st.warning("This department is currently unavailable based on the time or holiday schedule.")
            if r.fallback_department:
                st.info(f"Recommended alternative: **{r.fallback_department}** (currently available)")

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
            info = entry["contact_info"]
            for k, v in info.items():
                if v and v != "N/A":
                    st.markdown(f"**{k}:** {v}")

st.divider()

faqs = generate_faqs(st.session_state.history)
with st.expander("24-Hour Digest & FAQs", expanded=False):
    if not st.session_state.history:
        st.markdown("No requests have been submitted yet for the digest.")
    elif not faqs:
        st.markdown("Requests found, but no FAQs could be generated.")
    else:
        for faq in faqs:
            st.markdown(f"**Q: {faq['question']}**")
            st.markdown(f"A: {faq['answer']}")
            st.markdown("---")
