import datetime as dt

import streamlit as st

st.set_page_config(page_title="Hello World", page_icon="🌍", layout="centered")

st.title("🌍 Hello, world!")
st.caption("A minimal Streamlit app ready for Streamlit Community Cloud.")

st.write("If you can see this page, your deployment worked.")
st.write(f"Current UTC time: `{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC`")
