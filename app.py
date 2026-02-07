import json
import re
from typing import Any

import requests
import streamlit as st

DEFAULT_TIMEOUT_S = 45

st.set_page_config(page_title="Skrepa Chat", page_icon="💬")

SYSTEM_PROMPT_TEMPLATE = """
You are a regulated-environment support assistant.
You MUST respond in __LANGUAGE__.

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
        "max_length": 40
      }
    ]
  },
  "final": false
}

Rules:
- Never ask user for free-form long text.
- Keep next_choices concise and actionable, prefer 1-5 words per option.
- Use requested_form only when structured input is needed.
- For short_text fields, only request short identifiers like first name, policy number fragment, etc.
- If no form is needed, return requested_form as null.
- If chat can finish, set final true and next_choices may be empty.
- Do not repeat the user's latest message at the start of assistant_message.
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


def _api_messages(chat_history: list[dict[str, str]], language: str) -> list[dict[str, str]]:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("__LANGUAGE__", language)
    return [{"role": "system", "content": system_prompt}, *chat_history]


def _call_chat_completion(
    api_url: str,
    api_token: str,
    model: str,
    language: str,
    chat_history: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": _api_messages(chat_history, language),
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    if api_token.strip():
        headers["Authorization"] = f"Bearer {api_token.strip()}"

    response = requests.post(api_url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT_S)
    response.raise_for_status()
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))

    return _normalize_model_output(str(content))


def _reset_conversation():
    for key in ["chat_history", "pending_choices", "pending_form", "conversation_done", "accepted_terms"]:
        st.session_state.pop(key, None)


def _init_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "pending_choices" not in st.session_state:
        st.session_state.pending_choices = []
    if "pending_form" not in st.session_state:
        st.session_state.pending_form = None
    if "conversation_done" not in st.session_state:
        st.session_state.conversation_done = False
    if "accepted_terms" not in st.session_state:
        st.session_state.accepted_terms = False


def _ensure_greeting(greeting: str):
    if not st.session_state.chat_history:
        st.session_state.chat_history = [{"role": "assistant", "content": greeting}]


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
                values[key] = st.text_input(
                    label,
                    help=help_text,
                    placeholder=str(field.get("placeholder", "")),
                    max_chars=40,
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


def _trigger_assistant_turn(api_url: str, token: str, model: str):
    with st.spinner("Thinking…"):
        result = _call_chat_completion(
            api_url,
            token,
            model,
            st.session_state.response_language,
            st.session_state.chat_history,
        )

    assistant_text = result["assistant_message"].strip() or "I can help you continue with structured choices."
    st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
    st.session_state.pending_choices = result["next_choices"]
    st.session_state.pending_form = result["requested_form"]
    st.session_state.conversation_done = result["final"]


with st.sidebar:
    st.title("Skrepa Chat")

    title_text = st.text_input("Chat title", value="Support Assistant")
    description_text = st.text_area(
        "Chat description",
        value="**Guided support** with no free text.",
        help="Markdown is supported and will be shown in the main chat window.",
    )
    require_terms = st.checkbox("Accept terms before start", value=False)
    terms_text = st.text_input(
        "Terms checkbox label",
        value="I accept the terms and conditions.",
        placeholder="I accept the terms and conditions.",
    )
    greeting_text = st.text_input(
        "Greeting message",
        value="Hi, I can help using guided options.",
    )
    starters_raw = st.text_area(
        "Starter questions (one per line)",
        value="Billing help\nUpdate contact details\nCheck application status",
        help="Users choose one starter to begin.",
    )
    response_language = st.selectbox(
        "Response language",
        options=[
            "English",
            "Russian",
            "Mandarin Chinese",
            "Hindi",
            "Spanish",
            "French",
            "Modern Standard Arabic",
            "Bengali",
            "Portuguese",
            "Urdu",
            "German",
        ],
        index=0,
    )

    if st.button("Reset conversation", use_container_width=True):
        _reset_conversation()
        st.rerun()

    st.divider()
    st.header("Connection")
    api_url = st.text_input("Chat Completion API URL", value="https://api.openai.com/v1/chat/completions")
    api_token = st.text_input("API Token", type="password")
    model = st.text_input("Model", value="gpt-4o-mini")

_init_state()
st.session_state.response_language = response_language

st.title(title_text)
st.markdown(description_text)

if require_terms:
    accepted_now = st.checkbox(terms_text or "I accept the terms and conditions.", value=st.session_state.accepted_terms)
    st.session_state.accepted_terms = accepted_now
else:
    st.session_state.accepted_terms = True

if not st.session_state.accepted_terms:
    st.info("Please accept terms and conditions to start the chat.")
    st.stop()

_ensure_greeting(greeting_text)
starters = [line.strip() for line in starters_raw.splitlines() if line.strip()]

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        content = message["content"]
        if message["role"] == "user" and content.startswith("FORM_SUBMISSION: "):
            payload_text = content.replace("FORM_SUBMISSION: ", "", 1)
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                st.markdown("Form submitted.")
                with st.expander("Form submitted"):
                    st.code(payload_text, language="json")
            else:
                friendly_lines = [f"**{str(key).replace('_', ' ').title()}:** {value}" for key, value in payload.items()]
                st.markdown("\n".join(friendly_lines))
                with st.expander("Form submitted"):
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
        else:
            st.markdown(content)

if len(st.session_state.chat_history) == 1 and starters:
    selected_starter = st.pills("Choose a starter question", starters, selection_mode="single")
    if selected_starter:
        st.session_state.chat_history.append({"role": "user", "content": selected_starter})
        try:
            _trigger_assistant_turn(api_url, api_token, model)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.pending_choices and not st.session_state.conversation_done:
    selected_choice = st.pills("Choose your next step", st.session_state.pending_choices, selection_mode="single")
    if selected_choice:
        st.session_state.chat_history.append({"role": "user", "content": selected_choice})
        try:
            _trigger_assistant_turn(api_url, api_token, model)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.pending_form and not st.session_state.conversation_done:
    form_values = _render_form(st.session_state.pending_form)
    if form_values is not None:
        user_payload = json.dumps(form_values, ensure_ascii=False)
        st.session_state.chat_history.append({"role": "user", "content": f"FORM_SUBMISSION: {user_payload}"})
        try:
            _trigger_assistant_turn(api_url, api_token, model)
            st.rerun()
        except Exception as exc:
            st.error(f"Chat completion request failed: {exc}")

if st.session_state.conversation_done:
    with st.container():
        st.success("Conversation completed.")
        feedback = st.feedback("thumbs", key="conversation_feedback")
        if feedback is not None:
            st.caption("Thanks for your feedback.")
        if st.button("Start new conversation"):
            _reset_conversation()
            st.rerun()
