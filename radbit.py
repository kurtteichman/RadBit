# … everything up through Request History stays the same …

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
                if v and v != "N/A":
                    st.markdown(f"**{k}:** {v}")

# --- NEW: always show the FAQs section ---
st.divider()
st.subheader("FAQs (themed from your recent requests)")
faqs = []
try:
    faqs = generate_faqs(st.session_state.history)
except Exception as e:
    st.error(f"Could not generate FAQs: {e}")

if not faqs:
    st.info("No FAQs to show yet. Submit a few requests and this section will populate with grouped questions and self-help answers.")
else:
    for faq in faqs:
        st.markdown(f"**Q: {faq['question']}**")
        st.markdown(f"> {faq['answer']}")
