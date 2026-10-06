"""Cloud startup probe: no DB, secrets, assets, or LLM calls."""
import streamlit as st
st.set_page_config(page_title="Deployment check")
st.title("Deployment check passed")
st.write("Python and Streamlit started successfully.")
