# Regulated Support Chat POC (Streamlit)

A one-page Streamlit demo that proves a **no-free-text chat UX** can still be flexible by letting an LLM drive:

- next-step button/pill choices,
- dynamic structured forms,
- and conversation flow.

The app connects to any **OpenAI Chat Completions API-compatible** endpoint.

## What this demo does

- Sidebar config for:
  - Chat Completions API URL
  - API token
  - Model name
  - Chat title and greeting
  - Starter questions list
- Uses `st.pills` for guided choice-based interaction (single-select).
- Supports LLM-driven form collection via structured field definitions.
- Prevents long free-form user input in the chat body.

## Files

- `app.py` — full Streamlit app.
- `requirements.txt` — runtime dependencies.
- `runtime.txt` — Python runtime version for deployment.
- `.streamlit/config.toml` — Streamlit UI config.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Expected LLM behavior

The app sends a system instruction asking the model to return JSON with:

- `assistant_message`
- `next_choices`
- `requested_form` (or `null`)
- `final`

This allows the model to decide whether to continue with pills or request structured inputs.

## Deploy

Deploy directly to Streamlit Community Cloud using `app.py` as the main entry point.
