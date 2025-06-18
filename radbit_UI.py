import streamlit as st
from radbit import triage_and_get_support_info
from agents import set_default_openai_key

set_default_openai_key(st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Radiology Support Triage", layout="centered")

st.title("Radiology Support Triage Portal")
st.markdown("Please describe your issue below. We’ll route you to the correct support group and provide contact options.")

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

if "triage_result" not in st.session_state:
    st.session_state.triage_result = None

user_input = st.text_area("Describe your issue", value=st.session_state.user_input, height=200)

col1, col2 = st.columns([1, 2])
with col1:
    submit = st.button("Submit Request", use_container_width=True)
with col2:
    view_email = st.button("View Email Draft", use_container_width=True)

if submit and user_input.strip():
    with st.spinner("Triaging your request..."):
        result = triage_and_get_support_info(user_input.strip())
        st.session_state.triage_result = result
        st.session_state.user_input = user_input.strip()
        view_email = False

if st.session_state.triage_result:
    result = st.session_state.triage_result
    st.markdown("### ✅ Recommended Support Contact")
    st.markdown(f"**Department:** {result.department}")
    st.markdown(f"**Phone:** {result.phone}")
    st.markdown(f"**Email:** {result.email}")
    if result.link and "zoom" in result.link.lower():
        st.markdown(f"**Zoom Link:** [{result.link}]({result.link})")
    elif result.link:
        st.markdown(f"**Note:** {result.link}")
    st.markdown(f"**Available:** {result.hours}")

    st.markdown("---")
    st.markdown("Would you like help composing an email?")
    show_email = view_email

    if show_email:
        st.markdown("### 📄 Email Draft")
        st.code(result.email_draft, language="markdown")

        colA, colB = st.columns([1, 2])
        with colA:
            st.button("Send Email", disabled=True)  # Placeholder
        with colB:
            st.button("I'll Send It Myself", disabled=True)
