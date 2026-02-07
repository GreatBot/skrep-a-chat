# Regulated Support Chat POC (Streamlit)

A one-page Streamlit demo proving a **no-free-text chat UX** can still be flexible with LLM-driven flow.

## Highlights

- Sidebar setup for OpenAI-compatible chat completions (`url`, token, model).
- Configurable chat title, description, greeting, starter questions.
- Optional **Accept terms before start** gate on the main page.
- Guided user interaction with `st.pills` choices and structured forms.
- No free-form chat input; structured fields only.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Use `app.py` as the entrypoint in Streamlit Community Cloud.
