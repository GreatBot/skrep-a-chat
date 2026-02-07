import json
import re
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="Regulated Support Chat POC", page_icon="💬", layout="wide")

SYSTEM_PROMPT = """
You are a regulated-environment support assistant.

Return ONLY valid JSON with this exact shape:
{
  "assistant_message": "string",
  "next_choices": ["string"],
  "requested_form": {
    "title": "string",
    "submit_label": "string",
    "fields": [
      {
        "key": "snake_case_id",
        "label": "string",
        "type": "short_text|number|select|multiselect|boolean|date",
        "required": true,
        "help": "string",
        "placeholder": "string",
        "options": ["string"],
        "min": 0,
        "max": 100,
        "max_length": 80
      }
    ]
  },
  "final": false
}

Rules:
- Never ask user for free-form long text.
- Keep next_choices concise and actionable, typically 2-6 options.
- Use requested_form only when structured input is needed.
- For short_text fields, only request short identifiers like first name, policy number fragment, etc.
- If no form is needed, return requested_form as null.
- If chat can finish, set final true and next_choices may be empty.
""".strip()


def _extract_json_object(content: str) -> dict[str, Any] | None:
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _normalize_model_output(raw_content: str) -> dict[str, Any]:
    parsed = _extract_json_object(raw_content)
    if not parsed:
        return {
            "assistant_message": raw_content,
            "next_choices": [],
            "requested_form": None,
            "final": False,
        }

    return {
        "assistant_message": str(parsed.get("assistant_message", "")),
        "next_choices": [str(x) for x in parsed.get("next_choices", []) if str(x).strip()],
        "requested_form": parsed.get("requested_form"),
        "final": bool(parsed.get("final", False)),
    }


def _api_messages(chat_history: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": "system", "content": SYSTEM_PROMPT}, *chat_history]


def _call_chat_completion(
    api_url: str,
    api_token: str,
    model: str,
    chat_history: list[dict[str, str]],
    timeout_s: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": _api_messages(chat_history),
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    if api_token.strip():
        headers["Authorization"] = f"Bearer {api_token.strip()}"

    response = requests.post(api_url, headers=headers, json=payload, timeout=timeout_s)
    response.raise_for_status()
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))

    return _normalize_model_output(str(content))


def _init_state(greeting: str):
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    if "pending_choices" not in st.session_state:
        st.session_state.pending_choices = []
    if "pending_form" not in st.session_state:
        st.session_state.pending_form = None
    if "conversation_done" not in st.session_state:
        st.session_state.conversation_done = False


def _render_form(requested_form: dict[str, Any]) -> dict[str, Any] | None:
    fields = requested_form.get("fields", []) if isinstance(requested_form, dict) else []
    if not fields:
        return None

    with st.form("dynamic_structured_form", clear_on_submit=True):
        st.markdown(f"#### {requested_form.get('title', 'Provide details')}")
        values: dict[str, Any] = {}

        for field in fields:
            key = str(field.get("key", "")).strip()
            if not key:
                continue

            label = str(field.get("label", key))
            field_type = str(field.get("type", "short_text")).lower()
            help_text = str(field.get("help", ""))
            required = bool(field.get("required", False))

            if field_type == "short_text":
                max_length = int(field.get("max_length", 80))
                values[key] = st.text_input(
                    label,
                    help=help_text,
                    placeholder=str(field.get("placeholder", "")),
                    max_chars=max(1, min(max_length, 120)),
                )
            elif field_type == "number":
                values[key] = st.number_input(
                    label,
                    help=help_text,
                    min_value=field.get("min"),
                    max_value=field.get("max"),
                    value=field.get("min", 0),
                )
            elif field_type == "select":
                options = [str(x) for x in field.get("options", [])]
                values[key] = st.selectbox(label, options=options, help=help_text, index=None)
            elif field_type == "multiselect":
                options = [str(x) for x in field.get("options", [])]
                values[key] = st.multiselect(label, options=options, help=help_text)
            elif field_type == "boolean":
                values[key] = st.toggle(label, help=help_text)
            elif field_type == "date":
                values[key] = str(st.date_input(label, help=help_text))
            else:
                st.warning(f"Unsupported field type '{field_type}' was skipped.")
                continue

            if required and values.get(key) in (None, "", []):
                st.caption(f"`{label}` is required.")

        submitted = st.form_submit_button(requested_form.get("submit_label", "Submit details"), type="primary")

    if not submitted:
        return None

    missing_required = []
    for field in fields:
        if field.get("required") and values.get(field.get("key")) in (None, "", []):
            missing_required.append(field.get("label", field.get("key")))
    if missing_required:
        st.error(f"Please complete required fields: {', '.join(map(str, missing_required))}")
        return None

    return values


def _trigger_assistant_turn(api_url: str, token: str, model: str, timeout_s: int):
    with st.spinner("Thinking…"):
        result = _call_chat_completion(api_url, token, model, st.session_state.chat_history, timeout_s)

    assistant_text = result["assistant_message"].strip() or "I can help you continue with structured choices."
    st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
    st.session_state.pending_choices = result["next_choices"]
    st.session_state.pending_form = result["requested_form"]
    st.session_state.conversation_done = result["final"]


st.title("💬 Regulated Support Chat (POC)")
st.caption("No free-form chat input: users proceed with pills and structured form controls.")

with st.sidebar:
    st.header("LLM Setup")
    api_url = st.text_input("Chat Completion API URL", value="https://api.openai.com/v1/chat/completions")
    api_token = st.text_input("API Token", type="password")
    model = st.text_input("Model", value="gpt-4o-mini")
    timeout_s = st.slider("Request timeout (seconds)", min_value=10, max_value=120, value=45)

    st.divider()
    title_text = st.text_input("Chat title", value="Support Assistant")
    greeting_text = st.text_area(
        "Greeting message",
        value="Hi, I can help you with account and service requests using guided options.",
        max_chars=280,
    )
    starters_raw = st.text_area(
        "Starter questions (one per line)",
        value="I need help with billing\nI need to update my contact details\nI want to check application status",
        help="Users choose one starter to begin. You can provide a long list.",
    )

    if st.button("Reset conversation", use_container_width=True):
        for key in ["chat_history", "pending_choices", "pending_form", "conversation_done"]:
            st.session_state.pop(key, None)
        st.rerun()

_init_state(greeting_text)
starters = [line.strip() for line in starters_raw.splitlines() if line.strip()]

st.subheader(title_text)

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(st.session_state.chat_history) == 1 and starters:
    selected_starter = st.pills("Choose a starter question", starters, selection_mode="single")
    if selected_starter:
        st.session_state.chat_history.append({"role": "user", "content": selected_starter})
        try:
            _trigger_assistant_turn(api_url, api_token, model, timeout_s)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.pending_choices and not st.session_state.conversation_done:
    selected_choice = st.pills("Choose your next step", st.session_state.pending_choices, selection_mode="single")
    if selected_choice:
        st.session_state.chat_history.append({"role": "user", "content": selected_choice})
        try:
            _trigger_assistant_turn(api_url, api_token, model, timeout_s)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.pending_form and not st.session_state.conversation_done:
    form_values = _render_form(st.session_state.pending_form)
    if form_values is not None:
        user_payload = json.dumps(form_values, ensure_ascii=False)
        st.session_state.chat_history.append({"role": "user", "content": f"FORM_SUBMISSION: {user_payload}"})
        try:
            _trigger_assistant_turn(api_url, api_token, model, timeout_s)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.conversation_done:
    st.success("Conversation completed. You can reset to start again.")
