# main.py
import json
import os
import re
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, model_validator
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, ContentSettings, generate_blob_sas
from diagram_builder import build_diagram

app = FastAPI(title="Azure Architecture Diagram API")

# Azure OpenAI config (set via env vars on Container App)
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")  # Optional: falls back to Managed Identity
AOAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# Azure Blob Storage config
STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT", "starchdiagrams")
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "diagrams")

# Managed Identity credential (shared for OpenAI + Blob Storage)
_credential = None


def _get_credential():
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _get_blob_service_client():
    """Get BlobServiceClient using Managed Identity."""
    account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=_get_credential())


def _upload_to_blob(local_path: str, blob_name: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file to Azure Blob Storage and return a SAS URL valid for 24 hours."""
    try:
        blob_client = _get_blob_service_client().get_blob_client(
            container=STORAGE_CONTAINER, blob=blob_name
        )
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True, content_settings=ContentSettings(
                content_type=content_type
            ))

        # Generate a user delegation SAS token (works with Managed Identity, no account key needed)
        delegation_key = _get_blob_service_client().get_user_delegation_key(
            key_start_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            key_expiry_time=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        sas_token = generate_blob_sas(
            account_name=STORAGE_ACCOUNT_NAME,
            container_name=STORAGE_CONTAINER,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        return f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{STORAGE_CONTAINER}/{blob_name}?{sas_token}"
    except Exception as e:
        print(f"[WARN] Blob upload failed for {blob_name}: {e}")
        return ""


def _upload_diagram_files(name: str) -> dict:
    """Upload PNG, DOT, and DRAWIO files to blob storage. Returns dict of blob URLs."""
    output_dir = "/app/diagrams"
    urls = {}
    file_map = {
        "png": (f"{output_dir}/{name}.png", f"{name}.png", "image/png"),
        "drawio": (f"{output_dir}/{name}.drawio", f"{name}.drawio", "application/xml"),
        "dot": (f"{output_dir}/{name}.dot", f"{name}.dot", "text/plain"),
    }
    for key, (local_path, blob_name, content_type) in file_map.items():
        if os.path.exists(local_path):
            url = _upload_to_blob(local_path, blob_name, content_type)
            if url:
                urls[key] = url
    return urls


class Component(BaseModel):
    id: str
    type: str
    label: str
    tier: str = ""


class Connection(BaseModel):
    from_id: str = ""
    to_id: str = ""
    label: str = ""

    @model_validator(mode="before")
    @classmethod
    def accept_from_to_aliases(cls, data):
        """Accept both 'from'/'to' and 'from_id'/'to_id' field names."""
        if isinstance(data, dict):
            if "from" in data and not data.get("from_id"):
                data["from_id"] = data.pop("from")
            if "to" in data and not data.get("to_id"):
                data["to_id"] = data.pop("to")
        return data


class Group(BaseModel):
    name: str
    tier: str = "frontend"
    members: list[str] = []


class DiagramRequest(BaseModel):
    name: str
    components: list[Component]
    connections: list[Connection] = []
    groups: list[Group] = []


class TextRequest(BaseModel):
    description: str
    name: str = "architecture"


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _build_download_urls(base: str, name: str) -> dict:
    return {
        "png": f"{base}/download/{name}.png",
        "drawio": f"{base}/download/{name}.drawio",
        "dot": f"{base}/download/{name}.dot",
    }


@app.post("/generate")
def generate(req: DiagramRequest, request: Request):
    conns = [{"from": c.from_id, "to": c.to_id, "label": c.label} for c in req.connections]
    comps = [c.model_dump() for c in req.components]
    grps = [g.model_dump() for g in req.groups]
    result = build_diagram(req.name, comps, conns, grps)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["stderr"])

    # Upload to blob storage for persistent URLs
    blob_urls = _upload_diagram_files(req.name)
    base = _base_url(request)
    return {
        "success": True,
        "png_url": blob_urls.get("png", f"{base}/download/{req.name}.png"),
        "drawio_url": blob_urls.get("drawio", f"{base}/download/{req.name}.drawio"),
        "dot_url": blob_urls.get("dot", f"{base}/download/{req.name}.dot"),
        "warnings": result.get("warnings", []),
    }


SYSTEM_PROMPT = """You convert plain-text Azure architecture descriptions into JSON.
Return ONLY valid JSON, no markdown fences, no explanation.

Use this exact format:
{"name":"short_name_no_spaces","components":[{"id":"short_id","type":"type","label":"Display Name","tier":"tier"}],"connections":[{"from_id":"source_id","to_id":"target_id","label":"protocol"}],"groups":[{"name":"Group Name","tier":"tier","members":["id1","id2"]}]}

Component types must be one of: vm, load balancer, application gateway, front door, sql server, sql database, cosmos db, redis, storage account, blob storage, function app, container instance, app service, key vault, vnet, nsg, firewall, service bus, managed identity, private endpoint, log analytics, app insights.

Tiers: frontend, backend, database, security, networking, monitoring.

Rules:
- Give every component a unique short id (e.g., lb1, vm1, sql1)
- Add connections with protocols (HTTPS, Port 1433, SSH, etc.)
- Group related components into subnets/tiers even if the user didn't mention them
- Use from_id and to_id for connections (not from/to)
"""


def _get_auth_headers() -> dict:
    """Return authorization headers: API key if set, otherwise Managed Identity bearer token."""
    if AOAI_KEY:
        return {"api-key": AOAI_KEY, "Content-Type": "application/json"}
    else:
        token = _get_credential().get_token("https://cognitiveservices.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}


async def _text_to_json(description: str) -> dict:
    """Call Azure OpenAI to convert plain text to diagram JSON."""
    if not AOAI_ENDPOINT:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT environment variable on the Container App."
        )

    url = f"{AOAI_ENDPOINT.rstrip('/')}/openai/deployments/{AOAI_DEPLOYMENT}/chat/completions?api-version=2024-10-21"
    headers = _get_auth_headers()

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            headers=headers,
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description},
                ],
                "temperature": 0.1,
                "max_tokens": 4000,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Azure OpenAI error: {resp.status_code} {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?```\s*$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"LLM returned invalid JSON: {e}\n\nRaw output:\n{content}")


@app.post("/generate-from-text")
async def generate_from_text(request: Request):
    """Accept a plain text architecture description, parse it with Azure OpenAI,
    and generate the diagram. Handles multiple body formats from Power Platform."""

    # Parse body flexibly — Power Platform may send string, JSON, or wrapped formats
    raw = await request.body()
    body_str = raw.decode("utf-8").strip()

    description = ""
    name = "architecture"

    try:
        data = json.loads(body_str)
        if isinstance(data, str):
            # Body was a JSON-encoded string: "a load balancer and a vm"
            description = data
        elif isinstance(data, dict):
            # Normal JSON object: {"description": "...", "name": "..."}
            description = data.get("description", "")
            name = data.get("name", "architecture") or "architecture"
        else:
            description = str(data)
    except json.JSONDecodeError:
        # Body was plain text, not JSON at all
        description = body_str

    if not description:
        raise HTTPException(status_code=400, detail="No architecture description provided. Send a JSON body with a 'description' field, e.g. {\"description\": \"a web app with a load balancer and two VMs\"}")

    parsed = await _text_to_json(description)

    # Override name if caller provided one
    if name != "architecture":
        parsed["name"] = name

    # Normalize to DiagramRequest to validate
    try:
        diagram_req = DiagramRequest(**parsed)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM output didn't match schema: {e}\n\nParsed JSON:\n{json.dumps(parsed, indent=2)}")

    conns = [{"from": c.from_id, "to": c.to_id, "label": c.label} for c in diagram_req.connections]
    comps = [c.model_dump() for c in diagram_req.components]
    grps = [g.model_dump() for g in diagram_req.groups]
    result = build_diagram(diagram_req.name, comps, conns, grps)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["stderr"])

    # Upload to blob storage for persistent URLs
    blob_urls = _upload_diagram_files(diagram_req.name)
    base = _base_url(request)
    return {
        "success": True,
        "png_url": blob_urls.get("png", f"{base}/download/{diagram_req.name}.png"),
        "drawio_url": blob_urls.get("drawio", f"{base}/download/{diagram_req.name}.drawio"),
        "dot_url": blob_urls.get("dot", f"{base}/download/{diagram_req.name}.dot"),
        "warnings": result.get("warnings", []),
        "parsed_architecture": parsed,
    }


@app.get("/download/{filename}")
def download(filename: str):
    path = f"/app/diagrams/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /chat — single endpoint for Copilot Studio
# Accepts plain text, returns a conversational message with download links.
# Copilot Studio just relays the "message" field to the user.
# ---------------------------------------------------------------------------

BASE_DOMAIN = os.getenv("BASE_URL", "https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io")


def _format_component_list(parsed: dict) -> str:
    """Format the parsed architecture as a readable bullet list."""
    lines = []
    for c in parsed.get("components", []):
        lines.append(f"  - {c['label']} ({c['type']})")
    for g in parsed.get("groups", []):
        members = ", ".join(g.get("members", []))
        lines.append(f"  - Group: {g['name']} [{members}]")
    for conn in parsed.get("connections", []):
        label = f" over {conn['label']}" if conn.get("label") else ""
        lines.append(f"  - {conn['from_id']} -> {conn['to_id']}{label}")
    return "\n".join(lines)


@app.post("/chat")
async def chat(request: Request):
    """Single endpoint for Copilot Studio. Takes plain text, returns a
    conversation-ready message with download links."""

    # Parse body flexibly
    raw = await request.body()
    body_str = raw.decode("utf-8").strip()

    message = ""
    name = "architecture"

    try:
        data = json.loads(body_str)
        if isinstance(data, str):
            message = data
        elif isinstance(data, dict):
            message = data.get("message", data.get("description", ""))
            name = data.get("name", "architecture") or "architecture"
        else:
            message = str(data)
    except json.JSONDecodeError:
        message = body_str

    if not message:
        return {
            "message": "Hello! I can create Azure architecture diagrams for you. Describe your architecture in plain language, for example:\n\n\"I need a 3-tier web app with a load balancer, 2 web server VMs, and a SQL database.\"\n\nWhat would you like to build?",
            "architecture_json": "",
            "png_url": "",
            "drawio_url": "",
        }

    # Check if this is a help/info request
    help_keywords = ["help", "what can you do", "how does this work", "supported", "what services"]
    if any(kw in message.lower() for kw in help_keywords):
        return {
            "message": (
                "I create editable Azure architecture diagrams from plain text descriptions.\n\n"
                "**How to use:**\n"
                "Describe your architecture in plain language. For example:\n"
                "- \"A load balancer with 2 VMs and a SQL database\"\n"
                "- \"Hub-spoke network with a firewall, two spoke VNets, each with an app service\"\n"
                "- \"Microservices with Front Door, 3 container instances, Cosmos DB, and a Service Bus\"\n\n"
                "**What you get:**\n"
                "- A PNG image for quick viewing\n"
                "- An editable .drawio file (open in app.diagrams.net or VS Code)\n\n"
                "**Supported services:** VMs, Load Balancers, Application Gateway, Front Door, SQL Server, "
                "Cosmos DB, Redis Cache, Storage Accounts, Function Apps, Container Instances, App Services, "
                "Key Vault, VNets, NSGs, Firewalls, Service Bus, Private Endpoints, and more.\n\n"
                "**After generating**, you can say:\n"
                "- \"Add a Redis cache between the VMs and the database\"\n"
                "- \"Remove the second VM\"\n"
                "- \"Add a Key Vault for secrets\"\n\n"
                "What would you like to build?"
            ),
            "architecture_json": "",
            "png_url": "",
            "drawio_url": "",
        }

    # Parse the description into structured JSON via Azure OpenAI
    try:
        parsed = await _text_to_json(message)
    except HTTPException as e:
        return {
            "message": f"I had trouble understanding that description. Could you rephrase it? For example: \"A web app with a load balancer, 2 VMs, and a SQL database.\"\n\n(Error: {e.detail})",
            "architecture_json": "",
            "png_url": "",
            "drawio_url": "",
        }

    # Override name if provided
    if name != "architecture":
        parsed["name"] = name
    diagram_name = parsed.get("name", "architecture")

    # Validate
    try:
        diagram_req = DiagramRequest(**parsed)
    except Exception:
        return {
            "message": "I parsed your description but couldn't structure it properly. Could you try rephrasing with specific Azure services? For example: \"2 VMs behind a load balancer with a SQL database.\"",
            "architecture_json": json.dumps(parsed, indent=2),
            "png_url": "",
            "drawio_url": "",
        }

    # Generate the diagram
    conns = [{"from": c.from_id, "to": c.to_id, "label": c.label} for c in diagram_req.connections]
    comps = [c.model_dump() for c in diagram_req.components]
    grps = [g.model_dump() for g in diagram_req.groups]
    result = build_diagram(diagram_name, comps, conns, grps)

    if not result["success"]:
        return {
            "message": "I understood your architecture but hit an error generating the diagram. Please try again or simplify the description.",
            "architecture_json": json.dumps(parsed, indent=2),
            "png_url": "",
            "drawio_url": "",
        }

    # Upload to blob storage for persistent URLs
    blob_urls = _upload_diagram_files(diagram_name)
    png_url = blob_urls.get("png", f"{BASE_DOMAIN}/download/{diagram_name}.png")
    drawio_url = blob_urls.get("drawio", f"{BASE_DOMAIN}/download/{diagram_name}.drawio")

    # Build conversational response
    component_list = _format_component_list(parsed)
    warning_text = ""
    if result.get("warnings"):
        warning_text = "\n\n**Warnings:** " + "; ".join(result["warnings"])

    reply = (
        f"Your architecture diagram has been generated!\n\n"
        f"**Components I identified:**\n{component_list}\n\n"
        f"**Download your diagram:**\n"
        f"- [PNG Image]({png_url})\n"
        f"- [Editable Draw.io File]({drawio_url})\n\n"
        f"The .drawio file is fully editable — open it in app.diagrams.net or VS Code (Draw.io extension)."
        f"{warning_text}\n\n"
        f"**Would you like to make changes?** You can say:\n"
        f"- \"Add a Redis cache\"\n"
        f"- \"Remove the second VM\"\n"
        f"- \"Add a Key Vault for secrets\"\n"
        f"- \"Regenerate with a different layout\""
    )

    return {
        "message": reply,
        "architecture_json": json.dumps(parsed),
        "png_url": png_url,
        "drawio_url": drawio_url,
    }
