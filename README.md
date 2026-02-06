# Streamlit Hello World

A minimal Streamlit app configured for **Streamlit Community Cloud** deployment.

## Project files

- `app.py` — hello-world Streamlit app.
- `requirements.txt` — Python dependencies installed by Streamlit Cloud.
- `runtime.txt` — Python runtime version for reproducible deploys.
- `.streamlit/config.toml` — app theme and UI defaults.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. Open [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
3. Select **Create app** (or **New app**).
4. Configure:
   - **Repository:** this repo
   - **Branch:** your deployment branch (usually `main`)
   - **Main file path:** `app.py`
5. Click **Deploy**.

Streamlit Community Cloud will automatically read `requirements.txt` and `runtime.txt` during build.

## Optional next steps

- Add widgets and charts.
- Add `.streamlit/secrets.toml` values from the Cloud app settings (do not commit secrets).
- Add tests/linting in CI before deployment.
