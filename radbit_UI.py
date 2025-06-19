import streamlit as st
from agents import set_default_openai_key, InputGuardrailTripwireTriggered
from radbit import triage_and_get_support_info

set_default_openai_key(st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Radiology Support", layout="wide")

st.title("Radiology Support Portal")

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

if "triage_result" not in st.session_state:
    st.session_state.triage_result = None

if "show_email_draft" not in st.session_state:
    st.session_state.show_email_draft = False

if "last_submitted_input" not in st.session_state:
    st.session_state.last_submitted_input = ""

if "manual_send_clicked" not in st.session_state:
    st.session_state.manual_send_clicked = False

st.markdown("---")

top_col1, top_col2 = st.columns([1.25, 1.75], gap="large")

with top_col1:
    st.markdown("### Describe Your Issue")
    current_input = st.text_area("Request", value=st.session_state.user_input, height=200, label_visibility="collapsed")
    submit = st.button("Submit Request", use_container_width=True)

    if current_input.strip() != st.session_state.user_input.strip():
        st.session_state.triage_result = None
        st.session_state.show_email_draft = False
        st.session_state.manual_send_clicked = False

    st.session_state.user_input = current_input

    if submit and current_input.strip():
        try:
            with st.spinner("Identifying your request..."):
                result = triage_and_get_support_info(current_input.strip())
                st.session_state.triage_result = result
                st.session_state.show_email_draft = True
                st.session_state.last_submitted_input = current_input.strip()
                st.session_state.manual_send_clicked = False
        except InputGuardrailTripwireTriggered:
            st.session_state.triage_result = None
            st.session_state.show_email_draft = False
            st.session_state.manual_send_clicked = False
            st.error("This tool only supports questions related to radiology support — please enter a relevant issue.")

    st.markdown("---")

    if st.session_state.triage_result:
        result = st.session_state.triage_result
        st.markdown("### Recommended Support Contact")
        st.markdown(f"**Department:** {result.department}")
        st.markdown(f"**Phone:** {result.phone}")
        st.markdown(f"**Email:** {result.email}")
        st.markdown(f"**Other Info:** {result.other}")
        st.markdown(f"**Note:** {result.note}")
        st.markdown(f"**Availability:** {result.hours}")

with top_col2:
    if st.session_state.triage_result and st.session_state.show_email_draft:
        st.markdown("### Email Draft")
        st.text_area("Edit before sending", value=st.session_state.triage_result.email_draft, height=400, key="email_draft_box")
        st.button("Send Email", disabled=True)
