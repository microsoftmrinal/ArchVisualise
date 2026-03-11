# Azure Architecture Diagram Agent - Step-by-Step Build Guide

## Overview
Build a Copilot Studio agent that accepts plain text architecture descriptions from customers
and generates editable Azure architecture diagrams (.drawio). The solution has two layers:
- **Frontend**: Copilot Studio (conversation, orchestration)
- **Backend**: Azure Container App (Python, diagram generation, file storage)

---

## PHASE 1: Build the Backend (Azure Container App)

### Step 1: Create the Project Structure
Create the following folder structure for your backend API:

```
diagram-api/
├── app/
│   ├── main.py               # FastAPI application
│   ├── diagram_builder.py    # Builds Python diagram scripts from JSON
│   ├── icon_mappings.py      # Maps plain terms to diagrams library classes
│   └── requirements.txt      # Python dependencies
├── Dockerfile
└── README.md
```

### Step 2: Create requirements.txt
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
```

### Step 3: Create the Dockerfile
```dockerfile
FROM python:3.13-slim

# Install system-level GraphViz (required for diagrams + pygraphviz)
RUN apt-get update && \
    apt-get install -y graphviz graphviz-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY app/ /app
WORKDIR /app

# Create output directory
RUN mkdir -p /app/diagrams

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Step 4: Create icon_mappings.py
This file maps customer-friendly terms to the diagrams library class names:

```python
# icon_mappings.py
AZURE_ICON_MAP = {
    # Compute
    "vm": ("diagrams.azure.compute", "VM"),
    "virtual machine": ("diagrams.azure.compute", "VM"),
    "availability set": ("diagrams.azure.compute", "AvailabilitySets"),
    "function app": ("diagrams.azure.compute", "FunctionApps"),
    "container instance": ("diagrams.azure.compute", "ContainerInstances"),
    "app service": ("diagrams.azure.compute", "AppServices"),
    # Network
    "vnet": ("diagrams.azure.network", "VirtualNetworks"),
    "virtual network": ("diagrams.azure.network", "VirtualNetworks"),
    "subnet": ("diagrams.azure.network", "Subnets"),
    "load balancer": ("diagrams.azure.network", "LoadBalancers"),
    "application gateway": ("diagrams.azure.network", "ApplicationGateway"),
    "front door": ("diagrams.azure.network", "FrontDoors"),
    "nsg": ("diagrams.azure.network", "NetworkSecurityGroupsClassic"),
    "public ip": ("diagrams.azure.network", "PublicIpAddresses"),
    "private endpoint": ("diagrams.azure.network", "PrivateEndpoint"),
    "firewall": ("diagrams.azure.network", "Firewall"),
    # Database
    "sql server": ("diagrams.azure.database", "SQLServers"),
    "sql database": ("diagrams.azure.database", "SQLDatabases"),
    "cosmos db": ("diagrams.azure.database", "CosmosDb"),
    # Storage
    "storage account": ("diagrams.azure.storage", "StorageAccounts"),
    "blob storage": ("diagrams.azure.storage", "BlobStorage"),
    # Security
    "key vault": ("diagrams.azure.security", "KeyVaults"),
    # Identity
    "managed identity": ("diagrams.azure.identity", "ManagedIdentities"),
    # Integration
    "service bus": ("diagrams.azure.integration", "ServiceBus"),
    # Monitoring
    "log analytics": ("diagrams.azure.analytics", "LogAnalyticsWorkspaces"),
    "app insights": ("diagrams.azure.devops", "ApplicationInsights"),
}

TIER_COLORS = {
    "frontend": "#E3F2FD",
    "web": "#E3F2FD",
    "backend": "#E8F5E9",
    "app": "#E8F5E9",
    "database": "#FFF3E0",
    "data": "#FFF3E0",
    "loadbalancer": "#F3E5F5",
    "security": "#FCE4EC",
    "networking": "#F3E5F5",
    "monitoring": "#E0F7FA",
}
```

### Step 5: Create diagram_builder.py
This dynamically generates and executes a Python diagram script from structured JSON:

```python
# diagram_builder.py
import os, subprocess, importlib, tempfile
from icon_mappings import AZURE_ICON_MAP, TIER_COLORS

def build_diagram(name: str, components: list, connections: list, groups: list):
    """
    components: [{"id":"web1","type":"vm","label":"Web VM 1","tier":"frontend"}]
    connections: [{"from":"lb1","to":"web1","label":"HTTPS"}]
    groups:      [{"name":"Web Subnet","tier":"frontend","members":["web1","web2"]}]
    """
    output_dir = "/app/diagrams"
    filename = f"{output_dir}/{name}"

    # Collect required imports
    imports = set()
    for comp in components:
        key = comp["type"].lower()
        if key in AZURE_ICON_MAP:
            imports.add(AZURE_ICON_MAP[key])

    # Build script
    lines = ['import subprocess']
    lines.append('from diagrams import Diagram, Cluster, Edge')
    for module_path, class_name in imports:
        lines.append(f'from {module_path} import {class_name}')

    lines.append(f'''
graph_attr = {{"splines":"ortho","nodesep":"0.8","ranksep":"1.2","fontsize":"14","bgcolor":"white","pad":"0.5"}}
with Diagram("{name}", filename="{filename}", show=False, outformat=["png","dot"], direction="TB", graph_attr=graph_attr):''')

    # Create grouped and ungrouped nodes
    grouped_ids = set()
    for g in groups:
        grouped_ids.update(g.get("members", []))

    # Write groups as Clusters
    for g in groups:
        tier = g.get("tier", "frontend")
        color = TIER_COLORS.get(tier, "#FFFFFF")
        lines.append(f'    with Cluster("{g["name"]}", graph_attr={{"fontsize":"13","bgcolor":"{color}","style":"rounded","margin":"15"}}):')
        for mid in g.get("members", []):
            comp = next((c for c in components if c["id"] == mid), None)
            if comp:
                _, cls = AZURE_ICON_MAP.get(comp["type"].lower(), (None, None))
                if cls:
                    lines.append(f'        {comp["id"]} = {cls}("{comp.get("label", comp["id"])}")')

    # Ungrouped nodes
    for comp in components:
        if comp["id"] not in grouped_ids:
            _, cls = AZURE_ICON_MAP.get(comp["type"].lower(), (None, None))
            if cls:
                lines.append(f'    {comp["id"]} = {cls}("{comp.get("label", comp["id"])}")')

    # Connections
    for conn in connections:
        label = f', label="{conn["label"]}"' if conn.get("label") else ""
        lines.append(f'    {conn["from"]} >> Edge({label}) >> {conn["to"]}')

    # Add drawio conversion
    lines.append(f'subprocess.run(["graphviz2drawio","{filename}.dot","-o","{filename}.drawio"], check=True)')

    # Write and execute
    script = "\n".join(lines)
    script_path = f"{output_dir}/{name}_gen.py"
    with open(script_path, "w") as f:
        f.write(script)

    result = subprocess.run(["python", script_path], capture_output=True, text=True)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "files": {
            "png": f"{filename}.png",
            "dot": f"{filename}.dot",
            "drawio": f"{filename}.drawio",
        }
    }
```

### Step 6: Create main.py (FastAPI Application)
```python
# main.py
import os, base64
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from diagram_builder import build_diagram

app = FastAPI(title="Azure Architecture Diagram API")

class Component(BaseModel):
    id: str
    type: str
    label: str
    tier: str = "frontend"

class Connection(BaseModel):
    from_id: str   # renamed from "from" since it is a Python keyword
    to_id: str     # renamed from "to" for consistency
    label: str = ""

class Group(BaseModel):
    name: str
    tier: str = "frontend"
    members: list[str] = []

class DiagramRequest(BaseModel):
    name: str
    components: list[Component]
    connections: list[Connection]
    groups: list[Group] = []

@app.post("/generate")
def generate(req: DiagramRequest):
    conns = [{"from": c.from_id, "to": c.to_id, "label": c.label} for c in req.connections]
    comps = [c.model_dump() for c in req.components]
    grps = [g.model_dump() for g in req.groups]
    result = build_diagram(req.name, comps, conns, grps)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return result

@app.get("/download/{filename}")
def download(filename: str):
    path = f"/app/diagrams/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)

@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## PHASE 2: Deploy to Azure

### Step 7: Create Azure Container Registry
```bash
az group create --name rg-arch-diagrams --location eastus
az acr create --resource-group rg-arch-diagrams --name acrarchdiagrams --sku Basic
az acr login --name acrarchdiagrams
```

### Step 8: Build and Push Docker Image
```bash
cd diagram-api
docker build -t acrarchdiagrams.azurecr.io/diagram-api:v1 .
docker push acrarchdiagrams.azurecr.io/diagram-api:v1
```

### Step 9: Deploy Azure Container App
```bash
az containerapp env create \
  --name diagram-env \
  --resource-group rg-arch-diagrams \
  --location eastus

az containerapp create \
  --name diagram-api \
  --resource-group rg-arch-diagrams \
  --environment diagram-env \
  --image acrarchdiagrams.azurecr.io/diagram-api:v1 \
  --target-port 8080 \
  --ingress external \
  --registry-server acrarchdiagrams.azurecr.io \
  --min-replicas 0 \
  --max-replicas 3
```

### Step 10: Verify Deployment
```bash
# Get the URL
az containerapp show --name diagram-api --resource-group rg-arch-diagrams --query properties.configuration.ingress.fqdn -o tsv

# Test health endpoint
curl https://<your-app-url>/health

# Test diagram generation
curl -X POST https://<your-app-url>/generate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_arch",
    "components": [
      {"id": "lb1", "type": "load balancer", "label": "Load Balancer", "tier": "loadbalancer"},
      {"id": "vm1", "type": "vm", "label": "Web VM", "tier": "frontend"}
    ],
    "connections": [{"from_id": "lb1", "to_id": "vm1", "label": "HTTP"}],
    "groups": [{"name": "Web Tier", "tier": "frontend", "members": ["vm1"]}]
  }'
```

---

## PHASE 3: Configure Copilot Studio

### Step 11: Create the Agent
1. Go to https://copilotstudio.microsoft.com
2. Create a new Agent
3. Name: "Azure Architecture Diagram Generator"
4. Paste the agent instructions from `copilot_agent_instructions.md` into the Instructions field

### Step 12: Add the Custom Connector
1. Go to Power Platform > Custom Connectors
2. Create new connector from blank
3. Set host to your Container App URL (from Step 10)
4. Define the POST /generate action:
   - Request body: DiagramRequest schema (name, components, connections, groups)
   - Response body: success, files object with URLs
5. Define the GET /download/{filename} action
6. Test the connector

### Step 13: Create Topics

**Topic 1: Describe Architecture**
- Trigger: "create diagram", "generate architecture", "draw architecture"
- Flow:
  1. Ask: "Describe your Azure architecture. For example: I need a 3-tier app with
     a load balancer, 2 web VMs, and a SQL database."
  2. Store response in variable `architectureDescription`
  3. Use Generative AI to parse description into structured JSON (components, connections, groups)
  4. Confirm with user: "I identified these components: [list]. Shall I generate the diagram?"
  5. On confirm: Call Plugin Action (POST /generate)
  6. Return: "Your diagram is ready. Download links: [PNG] [DRAWIO].
     The .drawio file is fully editable at app.diagrams.net or VS Code draw.io extension."

**Topic 2: Modify Diagram**
- Trigger: "change diagram", "add component", "remove", "modify"
- Flow:
  1. Ask: "What changes would you like? (e.g., add a Redis cache, remove the second VM)"
  2. Update the stored component list
  3. Re-call POST /generate with updated data
  4. Return updated download links

**Topic 3: Help / Explain**
- Trigger: "how to edit", "what is drawio", "help"
- Flow: Explain how to open and edit .drawio files, supported Azure services

### Step 14: Add Knowledge Sources (Optional)
Upload reference documents to Copilot Studio Knowledge:
- Azure service descriptions and when to use each
- Common architecture patterns (hub-spoke, 3-tier, microservices, event-driven)
- Icon name reference list

### Step 15: Test End-to-End
1. Open the agent in Copilot Studio test panel
2. Type: "Create an architecture with a front door, application gateway, 2 web app VMs
   behind a load balancer, and a SQL database"
3. Verify the agent asks clarifying questions if needed
4. Verify it calls the backend API
5. Verify you receive working PNG and DRAWIO download links
6. Open the .drawio file and confirm it is editable

---

## PHASE 4: Optional Enhancements

### Step 16: Add Azure Blob Storage for File Persistence
Instead of serving files directly from the container, upload them to Blob Storage
for permanent URLs and sharing:

```bash
az storage account create --name starchdiagrams --resource-group rg-arch-diagrams --sku Standard_LRS
az storage container create --name diagrams --account-name starchdiagrams --public-access blob
```

Update main.py to upload files to blob storage and return blob URLs.

### Step 17: Add Authentication
Secure the API endpoint:
- Enable Azure AD authentication on the Container App
- Configure the Copilot Studio custom connector to use OAuth2

### Step 18: Add IaC Parsing (Terraform/Bicep/ARM)
Add a POST /parse-iac endpoint that accepts IaC file content,
extracts resources and relationships, and returns the same JSON structure
that /generate accepts. This enables customers to upload their existing
infrastructure code as an alternative to plain text descriptions.

---

## Quick Reference: API Contract

**POST /generate**
```json
{
  "name": "my_architecture",
  "components": [
    {"id": "lb1", "type": "load balancer", "label": "Public LB", "tier": "loadbalancer"},
    {"id": "vm1", "type": "vm", "label": "Web VM 1", "tier": "frontend"},
    {"id": "vm2", "type": "vm", "label": "Web VM 2", "tier": "frontend"},
    {"id": "sql1", "type": "sql server", "label": "SQL Server", "tier": "database"}
  ],
  "connections": [
    {"from_id": "lb1", "to_id": "vm1", "label": "HTTPS"},
    {"from_id": "lb1", "to_id": "vm2", "label": "HTTPS"},
    {"from_id": "vm1", "to_id": "sql1", "label": "Port 1433"},
    {"from_id": "vm2", "to_id": "sql1", "label": "Port 1433"}
  ],
  "groups": [
    {"name": "Web Subnet", "tier": "frontend", "members": ["vm1", "vm2"]},
    {"name": "Data Subnet", "tier": "database", "members": ["sql1"]}
  ]
}
```

**Supported component types:**
vm, virtual machine, availability set, function app, container instance, app service,
vnet, virtual network, subnet, load balancer, application gateway, front door, nsg,
public ip, private endpoint, firewall, sql server, sql database, cosmos db,
storage account, blob storage, key vault, managed identity, service bus,
log analytics, app insights
