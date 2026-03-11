# Azure Architecture Diagram Agent - Step-by-Step Build Guide

## Overview
A Copilot Studio agent that accepts plain text architecture descriptions from customers
and generates editable Azure architecture diagrams (PNG + .drawio). The solution has two layers:
- **Frontend**: Copilot Studio agent (conversation, orchestration)
- **Backend**: Azure Container App running FastAPI + Azure OpenAI (text parsing, diagram generation)

### Deployed Resources
| Resource | Name | Region |
|---|---|---|
| Resource Group | `rg-arch-diagrams` | East US |
| Container Registry | `acrarchdiagrams` (Basic, admin enabled) | East US |
| Container App Env | `diagram-env` | East US |
| Container App | `diagram-api` (1 CPU, 2 GB, 0-3 replicas) | East US |
| Azure OpenAI | `aoai-arch-diagrams` (S0, gpt-4o) | East US 2 |

**Base URL**: `https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io`

---

## PHASE 1: Build the Backend

### Step 1: Project Structure
```
diagram-api/
├── Dockerfile                       # Multi-stage build, non-root user
├── openapi-spec.json                # Swagger 2.0 spec for Power Platform
├── phase3_copilot_studio_guide.md   # Copilot Studio setup instructions
├── knowledge_architecture_patterns.md  # Knowledge source for agent
├── knowledge_component_reference.md    # Knowledge source for agent
└── app/
    ├── main.py                      # FastAPI app with /chat, /generate, /generate-from-text
    ├── diagram_builder.py           # Builds + executes diagram scripts from JSON
    ├── icon_mappings.py             # 60+ component type aliases, fuzzy matching, tier colors
    └── requirements.txt             # Python dependencies
```

### Step 2: requirements.txt
```
fastapi==0.115.0
uvicorn==0.30.0
diagrams==0.24.4
graphviz==0.20.3
pygraphviz==1.14
graphviz2drawio==1.1.0
puremagic==1.30
svg.path==7.0
azure-storage-blob==12.19.0
python-multipart==0.0.9
httpx==0.27.0
azure-identity==1.19.0
```

### Step 3: Dockerfile (multi-stage, non-root)
```dockerfile
FROM python:3.13-slim AS builder
RUN apt-get update && \
    apt-get install -y --no-install-recommends graphviz graphviz-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.13-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends graphviz && \
    rm -rf /var/lib/apt/lists/* && apt-get clean
RUN useradd -m -u 1000 appuser
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY --chown=appuser:appuser app/ /app
WORKDIR /app
RUN mkdir -p /app/diagrams && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Step 4: icon_mappings.py
Maps 60+ customer-friendly terms to the `diagrams` library classes with fuzzy matching. Key features:
- **Direct aliases**: "vm", "virtual machine", "server" all map to `VM`
- **`normalize_type(raw)`**: Strips prefixes like "Azure ", does substring matching as fallback
- **`auto_tier(type)`**: Auto-assigns color tier (frontend, backend, database, security, networking, monitoring)
- **`TIER_COLORS`**: Maps tiers to hex backgrounds for diagram clusters

See `diagram-api/app/icon_mappings.py` for the complete source.

### Step 5: diagram_builder.py
Dynamically generates and executes a Python diagram script. Key features:
- Normalizes component types via `normalize_type()` before processing
- Falls back to generic `Node()` for unrecognized types instead of silently dropping
- Returns `warnings` array listing any unrecognized types
- Outputs: PNG, DOT, and DRAWIO (via graphviz2drawio conversion)

See `diagram-api/app/diagram_builder.py` for the complete source.

### Step 6: main.py (FastAPI Application)
Four endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | POST | **Primary endpoint for Copilot Studio.** Accepts plain text, returns conversational message with download links. Handles help requests, errors, and empty input gracefully. |
| `/generate-from-text` | POST | Accepts plain text, calls Azure OpenAI to parse, generates diagram, returns structured JSON. |
| `/generate` | POST | Accepts structured JSON (components, connections, groups), generates diagram. For modifications. |
| `/download/{filename}` | GET | Serves generated PNG/DOT/DRAWIO files. |
| `/health` | GET | Health check (`{"status": "ok"}`). |

Key features in main.py:
- **Flexible body parsing**: Accepts JSON objects, JSON strings, and raw text (Power Platform compatibility)
- **Azure OpenAI via Managed Identity**: Uses `DefaultAzureCredential` — no API keys stored
- **Accepts `from`/`to` and `from_id`/`to_id`** in connections (Python keyword workaround)
- **`/chat` returns 4 simple strings**: `message`, `architecture_json`, `png_url`, `drawio_url`

See `diagram-api/app/main.py` for the complete source.

---

## PHASE 2: Deploy to Azure

### Step 7: Create Resource Group and ACR
```bash
# Register required providers (one-time)
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# Create resources
az group create --name rg-arch-diagrams --location eastus
az acr create --resource-group rg-arch-diagrams --name acrarchdiagrams --sku Basic --admin-enabled true
```

### Step 8: Build and Push Docker Image (ACR Build — no local Docker needed)
```bash
# Build remotely in ACR (avoids needing Docker Desktop)
az acr build --registry acrarchdiagrams --image diagram-api:v7 diagram-api/ --no-logs
```

### Step 9: Deploy Azure Container App
```bash
# Create environment
az containerapp env create --name diagram-env --resource-group rg-arch-diagrams --location eastus

# Deploy (ACR credentials are auto-fetched)
az containerapp create \
  --name diagram-api \
  --resource-group rg-arch-diagrams \
  --environment diagram-env \
  --image acrarchdiagrams.azurecr.io/diagram-api:v7 \
  --target-port 8080 \
  --ingress external \
  --registry-server acrarchdiagrams.azurecr.io \
  --registry-username acrarchdiagrams \
  --registry-password "$(az acr credential show --name acrarchdiagrams --query 'passwords[0].value' -o tsv)" \
  --min-replicas 0 \
  --max-replicas 3 \
  --cpu 1.0 --memory 2.0Gi
```

### Step 9b: Create Azure OpenAI and Configure Managed Identity
```bash
# Create Azure OpenAI resource
az cognitiveservices account create \
  --name aoai-arch-diagrams --resource-group rg-arch-diagrams \
  --kind OpenAI --sku S0 --location eastus2 \
  --custom-domain aoai-arch-diagrams

# Deploy gpt-4o model
az cognitiveservices account deployment create \
  --name aoai-arch-diagrams --resource-group rg-arch-diagrams \
  --deployment-name gpt-4o --model-name gpt-4o --model-version "2024-11-20" \
  --model-format OpenAI --sku-capacity 10 --sku-name "GlobalStandard"

# Assign system-managed identity to Container App
az containerapp identity assign --name diagram-api --resource-group rg-arch-diagrams --system-assigned

# Grant OpenAI User role to the Container App's identity
PRINCIPAL_ID=$(az containerapp identity show --name diagram-api --resource-group rg-arch-diagrams --query principalId -o tsv)
AOAI_ID=$(az cognitiveservices account show --name aoai-arch-diagrams --resource-group rg-arch-diagrams --query id -o tsv)
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services OpenAI User" --scope $AOAI_ID

# Set environment variables on Container App
az containerapp update --name diagram-api --resource-group rg-arch-diagrams \
  --set-env-vars \
    "AZURE_OPENAI_ENDPOINT=https://aoai-arch-diagrams.openai.azure.com/" \
    "AZURE_OPENAI_DEPLOYMENT=gpt-4o"
```

### Step 10: Verify Deployment
```bash
# Health check
curl https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io/health

# Test the /chat endpoint (primary endpoint for Copilot Studio)
curl -X POST https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a web app with a load balancer, 2 VMs, and a SQL database"}'
```

Expected response: a JSON object with `message` (conversational reply with download links), `png_url`, `drawio_url`, and `architecture_json`.

---

## PHASE 3: Configure Copilot Studio

See `diagram-api/phase3_copilot_studio_guide.md` for the detailed walkthrough. Summary:

### Step 11: Create the Agent
- Go to copilotstudio.microsoft.com > Create > New agent
- Name: `Azure Architecture Diagram Generator`
- Paste `copilot_agent_instructions.md` into the Instructions field

### Step 12: Add Custom Connector
- Go to make.powerapps.com > Custom connectors > Import OpenAPI file
- Upload `diagram-api/openapi-spec.json` (Swagger 2.0, v4.0.0)
- Primary action: **Chat** (POST /chat) — 2 inputs, 4 outputs, all strings
- Test: HealthCheck, then Chat with a description

### Step 13: Create a Single Topic
With the `/chat` endpoint, you only need **one topic**:

**Topic: Architecture Diagram**
- Trigger: "create diagram", "generate architecture", "help", etc.
- Node 1 (Question): Capture user input
- Node 2 (Action): Call `Chat`, pass user input as `message`
- Node 3 (Message): Display the `message` output

The `/chat` endpoint handles help, greetings, diagram generation, and error messages — all server-side.

### Step 14: Add Knowledge Sources (Optional)
Upload `knowledge_architecture_patterns.md` and `knowledge_component_reference.md`.

### Step 15: End-to-End Test
Test in Copilot Studio test panel with:
1. "I need a 3-tier app with a load balancer, 2 VMs, and a SQL database"
2. "What can you do?"
3. "Create a hub-spoke network with a firewall and two spoke VNets"

---

## PHASE 4: Optional Enhancements

### Step 16: Azure Blob Storage for File Persistence
The Container App scales to zero — files are lost on scale-down. For persistent downloads:
```bash
az storage account create --name starchdiagrams --resource-group rg-arch-diagrams --sku Standard_LRS
az storage container create --name diagrams --account-name starchdiagrams --public-access blob
```
Update main.py to upload to Blob Storage and return blob URLs.

### Step 17: Add Authentication
- Enable Azure AD auth on the Container App
- Configure OAuth2 on the custom connector

### Step 18: IaC Parsing (Terraform/Bicep/ARM)
Add `POST /parse-iac` to accept infrastructure-as-code and extract resources into the diagram JSON format.

---

## Quick Reference: API Endpoints

### POST /chat (recommended for Copilot Studio)
```json
// Request
{"message": "I need a web app with a load balancer, 2 VMs, and a SQL database"}

// Response
{
  "message": "Your architecture diagram has been generated!\n\n**Components:**\n...\n\n**Download:**\n- [PNG](https://...)\n- [Draw.io](https://...)",
  "architecture_json": "{...}",
  "png_url": "https://diagram-api.../download/web_app.png",
  "drawio_url": "https://diagram-api.../download/web_app.drawio"
}
```

### POST /generate (for modifications)
```json
{
  "name": "my_architecture",
  "components": [
    {"id": "lb1", "type": "load balancer", "label": "Public LB", "tier": "frontend"},
    {"id": "vm1", "type": "vm", "label": "Web VM 1", "tier": "backend"},
    {"id": "sql1", "type": "sql server", "label": "SQL Server", "tier": "database"}
  ],
  "connections": [
    {"from_id": "lb1", "to_id": "vm1", "label": "HTTPS"},
    {"from_id": "vm1", "to_id": "sql1", "label": "Port 1433"}
  ],
  "groups": [
    {"name": "Web Subnet", "tier": "frontend", "members": ["vm1"]},
    {"name": "Data Subnet", "tier": "database", "members": ["sql1"]}
  ]
}
```

### Supported Component Types (60+ aliases)
vm, virtual machine, server, load balancer, lb, application gateway, app gateway, waf,
front door, cdn, sql server, sql database, sql, azure sql, cosmos db, cosmosdb, nosql,
redis, redis cache, cache, storage account, storage, blob storage, function app, function,
serverless, container instance, aci, container, app service, web app, key vault, keyvault,
vnet, virtual network, subnet, nsg, network security group, firewall, azure firewall,
public ip, pip, private endpoint, private link, service bus, message queue,
managed identity, log analytics, app insights, application insights

### Rebuild & Redeploy
```bash
az acr build --registry acrarchdiagrams --image diagram-api:v7 diagram-api/ --no-logs
az containerapp update --name diagram-api --resource-group rg-arch-diagrams --image acrarchdiagrams.azurecr.io/diagram-api:v7
```
