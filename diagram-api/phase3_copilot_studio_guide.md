# Phase 3: Configure Copilot Studio - Detailed Walkthrough

Base API URL: `https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io`

---

## Step 11: Create the Agent

1. Go to **https://copilotstudio.microsoft.com**
2. Click **Create** in the left sidebar, then **New agent**
3. Click **Skip to configure** (top right) to bypass the wizard
4. Fill in these fields:
   - **Name**: `Azure Architecture Diagram Generator`
   - **Description**: `Creates editable Azure architecture diagrams from plain text descriptions. Generates PNG and draw.io files.`
   - **Instructions**: Copy and paste the entire contents of `copilot_agent_instructions.md` into this field
5. Click **Create**

---

## Step 12: Add the Custom Connector

1. Go to **https://make.powerapps.com**
2. In the left sidebar, expand **More** > click **Discover all**
3. Find and pin **Custom connectors** (under Data)
4. Click **Custom connectors** > **+ New custom connector** > **Import an OpenAPI file**
5. Set connector name: `DiagramAPI`
6. Click **Import** and upload: `diagram-api/openapi-spec.json` (Swagger 2.0, v4.0.0)
7. On the **General** tab, verify:
   - Scheme: **HTTPS**
   - Host: `diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io`
   - Base URL: `/`
8. On the **Security** tab:
   - Authentication type: **No authentication**
9. On the **Definition** tab, you should see these actions:
   - **`Chat`** (POST /chat) — primary action for the agent
   - `GenerateDiagramFromText` (POST /generate-from-text)
   - `GenerateDiagram` (POST /generate)
   - `DownloadFile` (GET /download/{filename})
   - `HealthCheck` (GET /health)
10. Click **Create connector** (top right)
11. Go to the **Test** tab > click **+ New connection** > **Create**
12. Test **HealthCheck** — expected: `{"status": "ok"}`
13. Test **Chat** with:
    - message: `I need a web app with a load balancer and 2 VMs`
    - Expected: `message` field with component list and download links

### Connect to Copilot Studio

1. Go to **https://copilotstudio.microsoft.com** > open your agent
2. Left sidebar > **Actions** > **+ Add an action**
3. Search for `DiagramAPI`
4. Add the **Chat** action (this is the only action you need)

---

## Step 13: Create a Single Topic

With the `/chat` endpoint, the backend handles all logic. You only need **one topic**.

### Topic: Architecture Diagram

1. Go to **Topics** > **+ Add a topic** > **From blank**
2. **Name**: `Architecture Diagram`
3. **Trigger phrases**:
   - `create a diagram`
   - `generate architecture`
   - `draw architecture`
   - `I need a diagram`
   - `design my architecture`
   - `build a diagram`
   - `help`
   - `what can you do`

4. **Build the flow:**

   **Node 1 — Question:**
   - Ask: `What architecture would you like me to create? Describe it in plain language, for example: "A web app with a load balancer, 2 VMs, and a SQL database."`
   - Identify: **User's entire response**
   - Save to variable: `userMessage`

   **Node 2 — Action:**
   - Call action: **Chat** (from DiagramAPI connector)
   - Input: set `message` to `userMessage`
   - Save outputs to variables:
     - `chatReply` = message
     - `pngUrl` = png_url
     - `drawioUrl` = drawio_url
     - `archJson` = architecture_json

   **Node 3 — Message:**
   - Display: `{chatReply}`

   **Node 4 — Question (follow-up):**
   - Ask: `Would you like to make any changes, create a new diagram, or are you done?`
   - Options: `Make changes` / `New diagram` / `Done`
   - If `Make changes`: loop back to Node 1
   - If `New diagram`: loop back to Node 1
   - If `Done`: end topic

That's it. The `/chat` endpoint handles:
- Greeting/empty messages (returns usage instructions)
- Help requests (returns supported services and examples)
- Architecture descriptions (parses, generates, returns download links)
- Error situations (returns friendly error messages)

---

## Step 14: Add Knowledge Sources (Optional)

In Copilot Studio, go to **Knowledge** > **+ Add knowledge**. Upload:

1. **`knowledge_architecture_patterns.md`** — 7 common patterns (3-tier, hub-spoke, microservices, etc.)
2. **`knowledge_component_reference.md`** — component types, ports, tier colors

---

## Step 15: End-to-End Testing

1. In Copilot Studio, click **Test** (bottom-left panel)

2. **Test 1 — Diagram creation:**
   Type: `I need a 3-tier web app with a load balancer, 2 web VMs, Redis cache, and a SQL database`
   - Verify: Response includes component list and download links
   - Click the PNG and DRAWIO links to verify they work

3. **Test 2 — Help:**
   Type: `What can you do?`
   - Verify: Response lists supported services and usage examples

4. **Test 3 — Complex architecture:**
   Type: `Hub-spoke network with a firewall in the hub, two spokes each with an app service and SQL database, Key Vault in the hub`
   - Verify: All components identified, download links work

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| SystemError in Copilot Studio | Use the `/chat` endpoint (not `/generate-from-text`). It handles all edge cases. |
| 422 error from custom connector | Update the connector with the latest `openapi-spec.json` (v4.0.0). The `/chat` endpoint accepts any body format. |
| Custom connector not visible | Ensure connector and agent are in the same Power Platform environment |
| Download links return 404 | Container scaled to zero, files lost. Regenerate. Consider Blob Storage (Phase 4). |
| Action timeout | The `/chat` endpoint may take 15-30s (Azure OpenAI + diagram generation). Check Container App logs: `az containerapp logs show --name diagram-api --resource-group rg-arch-diagrams` |
