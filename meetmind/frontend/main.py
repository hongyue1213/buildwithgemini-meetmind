"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
try:
    from a2a.client import create_client
except ImportError:
    create_client = None
from a2a.types import Message, Part, Role
try:
    from a2a.types import SendMessageRequest
except ImportError:
    SendMessageRequest = None
try:
    from a2a.types import AgentCard, TaskArtifactUpdateEvent
except ImportError:
    AgentCard = None
    TaskArtifactUpdateEvent = None
try:
    from a2a.types import FilePart, TextPart
except ImportError:
    FilePart = None
    TextPart = None
try:
    from a2a.utils.constants import (
        PROTOCOL_VERSION_1_0,
        VERSION_HEADER,
        TransportProtocol,
    )
except ImportError:
    try:
        from a2a.types import TransportProtocol
    except ImportError:
        TransportProtocol = None
    PROTOCOL_VERSION_1_0 = "1.0"
    VERSION_HEADER = "X-A2A-Version"
try:
    from google.protobuf.json_format import MessageToDict
except ImportError:
    MessageToDict = None
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/639275673587/locations/us-east1/reasoningEngines/2734449134395195392",
)
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card = None


async def _get_card(client: httpx.AsyncClient):
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        if AgentCard is not None:
            card = AgentCard(**resp.json())
            card.url = A2A_BASE
            _card = card
        else:
            _card = resp.json()
    return _card


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI data parts (tagged
    application/json+a2ui) become {"kind": "a2ui", "data": <message>} so the UI
    renders the card; each data part is one A2UI message (beginRendering or
    surfaceUpdate).
    """
    out: list[dict] = []
    for p in parts:
        # 1. Protobuf Part (a2a-sdk 1.x)
        if MessageToDict is not None and (hasattr(p, "DESCRIPTOR") or hasattr(p, "ListFields")):
            p_dict = MessageToDict(p)
            if "text" in p_dict and p_dict["text"]:
                out.append({"kind": "text", "text": p_dict["text"]})
                continue
            if "data" in p_dict:
                d = p_dict["data"]
                if isinstance(d, dict) and "metadata" in d:
                    meta = d.get("metadata", {})
                    mime = meta.get("mimeType") if isinstance(meta, dict) else None
                    if mime == _A2UI_MIME:
                        out.append({"kind": "a2ui", "data": d.get("data", d)})
                        continue
                out.append({"kind": "a2ui", "data": d})
                continue
            if "file" in p_dict and "uri" in p_dict["file"]:
                out.append({"kind": "text", "text": p_dict["file"]["uri"]})
                continue

        # 2. Pydantic Part (a2a-sdk 0.3.x fallback)
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if text:
            out.append({"kind": "text", "text": text})
            continue
        data = getattr(root, "data", None)
        if data is not None:
            meta = getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else getattr(meta, "mime_type", None)
            if mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data})
                continue
        file_obj = getattr(root, "file", None)
        if file_obj:
            uri = getattr(file_obj, "uri", None)
            if uri:
                out.append({"kind": "text", "text": uri})
                continue
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    headers = _auth_headers()
    headers[VERSION_HEADER] = PROTOCOL_VERSION_1_0

    async with httpx.AsyncClient(headers=headers, timeout=120) as client:
        if TransportProtocol is not None and hasattr(TransportProtocol, "JSONRPC"):
            config = ClientConfig(
                httpx_client=client,
                supported_protocol_bindings=[
                    TransportProtocol.JSONRPC,
                    TransportProtocol.HTTP_JSON,
                ],
            )
        elif TransportProtocol is not None and hasattr(TransportProtocol, "jsonrpc"):
            config = ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        else:
            config = ClientConfig(httpx_client=client)

        if create_client is not None:
            a2a_client = await create_client(A2A_BASE, config)
        else:
            card = await _get_card(client)
            factory = ClientFactory(config)
            a2a_client = factory.create(card)

        role = getattr(Role, "ROLE_USER", getattr(Role, "user", 1))
        if TextPart is not None:
            part = Part(root=TextPart(text=message))
        else:
            part = Part(text=message)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=role,
            parts=[part],
            context_id=_contexts.get(user_id) or "",
        )

        send_arg = SendMessageRequest(message=msg) if SendMessageRequest is not None else msg
        async for chunk in a2a_client.send_message(send_arg):
            if hasattr(chunk, "HasField"):
                if chunk.HasField("artifact_update"):
                    if not _contexts.get(user_id) and chunk.artifact_update.context_id:
                        _contexts[user_id] = chunk.artifact_update.context_id
                    parts.extend(_extract_parts(chunk.artifact_update.artifact.parts))
                elif chunk.HasField("message"):
                    if not _contexts.get(user_id) and chunk.message.context_id:
                        _contexts[user_id] = chunk.message.context_id
                    parts.extend(_extract_parts(chunk.message.parts))
                elif chunk.HasField("task"):
                    if not _contexts.get(user_id) and chunk.task.context_id:
                        _contexts[user_id] = chunk.task.context_id
                    for artifact in chunk.task.artifacts:
                        parts.extend(_extract_parts(artifact.parts))
            elif isinstance(chunk, tuple):
                task, update = chunk
                if task is not None and getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
                if update is not None and hasattr(update, "artifact"):
                    parts.extend(_extract_parts(update.artifact.parts))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})



# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
