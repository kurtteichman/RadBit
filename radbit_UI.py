import streamlit as st
from radbit import triage_and_get_support_info
from agents import set_default_openai_key

st.set_page_config(page_title="Radiology Support Triage", layout="centered")

st.title("Radiology Support Triage Portal")
st.markdown("Please describe your issue below. We’ll route you to the correct support group and provide contact options.")

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

if "triage_result" not in st.session_state:
    st.session_state.triage_result = None

if "show_email_draft" not in st.session_state:
    st.session_state.show_email_draft = False

if "last_submitted_input" not in st.session_state:
    st.session_state.last_submitted_input = ""


current_input = st.text_area("Describe your issue", value=st.session_state.user_input, height=200)

submit = st.button("Submit Request", use_container_width=True)

if current_input.strip() != st.session_state.user_input.strip():
    st.session_state.triage_result = None
    st.session_state.show_email_draft = False

st.session_state.user_input = current_input

if submit and current_input.strip():
    with st.spinner("Triaging your request..."):
        result = triage_and_get_support_info(current_input.strip())
        st.session_state.triage_result = result
        st.session_state.show_email_draft = False
        st.session_state.last_submitted_input = current_input.strip()

if st.session_state.triage_result:
    result = st.session_state.triage_result
    st.markdown("Recommended Support Contact")
    st.markdown(f"**Department:** {result.department}")
    st.markdown(f"**Phone:** {result.phone}")
    st.markdown(f"**Email:** {result.email}")
    if result.link and "zoom" in result.link.lower():
        st.markdown(f"**Zoom Link:** [{result.link}]({result.link})")
    elif result.link:
        st.markdown(f"**Note:** {result.link}")
    st.markdown(f"**Available:** {result.hours}")

    st.markdown("---")
    st.markdown("Would you like help drafting an email to this support group?")

    if st.button("View Email Draft", use_container_width=True):
        st.session_state.show_email_draft = True

    if st.session_state.show_email_draft:
        st.markdown("Email Draft")
        st.code(result.email_draft, language="markdown")

        colA, colB = st.columns([1, 1])
        with colA:
            st.button("Send Email", disabled=True)
        with colB:
            st.button("I'll Send It Myself", disabled=True)
