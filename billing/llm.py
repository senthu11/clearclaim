"""Server-side credentials and bounded Nebius calls through LangChain."""

import json
import os
from pathlib import Path

import httpx
import truststore

# Use OS trust roots for all provider integrations, including requests-based tools.
# Certificate verification stays enabled.
truststore.inject_into_ssl()

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
for env_path in (ROOT / ".env", ROOT / ".local-config/.env"):
    load_dotenv(env_path, override=False)

# Graph state can contain local personal details. Never export it through tracing.
def disable_external_tracing():
    for tracing_flag in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
        os.environ[tracing_flag] = "false"


disable_external_tracing()


class UserError(Exception):
    """A safe, actionable message suitable for displaying in the interface."""


def http_client():
    # Use Windows' trusted certificate store, including corporate root certificates.
    import ssl
    return httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=90)


def provider_settings():
    return {
        "api_key": os.getenv("NEBIUS_API_KEY", ""),
        "base_url": os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
    }


def available_models():
    settings = provider_settings()
    if not settings["api_key"]:
        raise UserError("Add NEBIUS_API_KEY to .local-config/.env or .env, then restart the app.")
    try:
        with OpenAI(**settings, http_client=http_client(), max_retries=1) as client:
            return sorted(model.id for model in client.models.list())
    except Exception:
        raise UserError("Could not list Nebius models. Check the key, endpoint, account access, and network.") from None


class NebiusModel:
    def __init__(self, model):
        settings = provider_settings()
        if not settings["api_key"]:
            raise UserError("NEBIUS_API_KEY is missing. Add it to .local-config/.env or .env.")
        if not model.strip():
            raise UserError("Choose a Nebius chat model in the sidebar first.")
        self.chat = ChatOpenAI(
            **settings, model=model.strip(), temperature=0, max_tokens=6500,
            timeout=90, max_retries=1, http_client=http_client(),
        )

    def _invoke(self, system, payload, json_mode=False):
        from billing.privacy import model_payload
        try:
            safe_payload = model_payload(payload)
        except (ValueError, TypeError, AttributeError):
            raise UserError("Blocked external request: only built-in synthetic examples may reach the LLM.") from None
        messages = [SystemMessage(content=system),
                    HumanMessage(content=json.dumps(safe_payload, default=str, ensure_ascii=False))]
        try:
            client = self.chat.bind(response_format={"type": "json_object"}) if json_mode else self.chat
            response = client.invoke(messages)
            if not isinstance(response.content, str) or not response.content.strip():
                raise UserError("The model returned no usable text. Select another chat model and retry.")
            return response.content.strip()
        except UserError:
            raise
        except Exception:
            raise UserError("Nebius request failed. Check the selected chat model, account credits, "
                            "API key, endpoint, and network; then retry.") from None

    def text(self, system, payload):
        return self._invoke(system, payload)

    def json(self, system, payload, schema):
        instruction = system + "\nReturn only a JSON object matching this JSON Schema:\n" + json.dumps(schema)
        raw = self._invoke(instruction, payload, json_mode=True)
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            raise UserError("The model returned invalid JSON. Retry extraction or select another chat model.") from None
