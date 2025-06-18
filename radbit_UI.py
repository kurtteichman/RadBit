import streamlit as st
from triage_logic import triage_and_get_support_info
from agents import set_default_openai_key

set_default_openai_key(st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="Radiology Support Triage", layout="centered")
st.title("Radiologist Support Request Portal")

st.markdown("""
Enter a description of the issue you are facing. Based on your input, we will direct you to the appropriate support team.
""")

user_input = st.text_area("Describe your issue", height=200)

send_email = False
show_email = False
result = None

if st.button("Submit Request"):
    if not user_input.strip():
        st.warning("Please enter a description of the issue.")
    else:
        with st.spinner("Routing your request to the appropriate team..."):
            result = triage_and_get_support_info(user_input)

if result:
    st.markdown("---")
    st.subheader("Recommended Support Contact")
    st.write(f"**Department**: {result.department}")
    st.write(f"**Phone**: {result.phone}")
    st.write(f"**Email**: {result.email}")

    st.markdown("---")
    st.subheader("Would you like to send an email with your request?")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        show_email = st.button("View Email Draft")
    with col2:
        send_email = st.button("Send Email")
    with col3:
        cancel = st.button("No Thanks")

    if show_email:
        st.markdown("### Email Draft")
        st.text_area("Email Content", result.email_draft, height=300)

    if send_email:
        st.success("The email has been sent to the appropriate support team.")
        st.balloons()

    if cancel:
        st.info("You may use the contact information above to send your own email.")
