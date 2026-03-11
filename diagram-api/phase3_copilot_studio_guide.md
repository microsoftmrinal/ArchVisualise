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

The agent is now created. Next we connect it to the backend API.

---

## Step 12: Add the Custom Connector (Plugin Action)

There are two approaches. **Option A** (recommended) uses a Power Platform custom connector. **Option B** uses an HTTP action inside a Power Automate flow.

### Option A: Custom Connector from OpenAPI Spec

1. Go to **https://make.powerapps.com**
2. In the left sidebar, expand **More** > click **Discover all**
3. Find and pin **Custom connectors** (under Data)
4. Click **Custom connectors** > **+ New custom connector** > **Import an OpenAPI file**
5. Set connector name: `DiagramAPI`
6. Click **Import** and upload the file: `diagram-api/openapi-spec.json`
7. On the **General** tab, verify:
   - Scheme: **HTTPS**
   - Host: `diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io`
   - Base URL: `/`
8. On the **Security** tab:
   - Authentication type: **No authentication** (for now; add OAuth in Phase 4)
9. On the **Definition** tab, you should see 3 actions:
   - `GenerateDiagram` (POST /generate)
   - `DownloadFile` (GET /download/{filename})
   - `HealthCheck` (GET /health)
10. Click **Create connector** (top right)
11. Go to the **Test** tab > click **+ New connection** > **Create**
12. Select the `HealthCheck` operation > click **Test operation**
    - Expected response: `{"status": "ok"}`
13. Select the `GenerateDiagram` operation > paste this test body > **Test operation**:
    ```json
    {
      "name": "connector_test",
      "components": [
        {"id": "vm1", "type": "vm", "label": "Test VM", "tier": "backend"}
      ],
      "connections": [],
      "groups": []
    }
    ```
    - Expected: `{"success": true, ...}`

### Connect the Connector to Copilot Studio

1. Go back to **https://copilotstudio.microsoft.com**
2. Open your **Azure Architecture Diagram Generator** agent
3. In the left sidebar, click **Actions** > **+ Add an action**
4. Search for `DiagramAPI` — you should see the custom connector
5. Add the **GenerateDiagram** action
6. Add the **DownloadFile** action
7. For each action, review the input/output parameter descriptions

### Option B: Power Automate HTTP Action (Alternative)

If custom connectors are restricted in your environment:

1. In Copilot Studio, go to **Actions** > **+ Add an action** > **New flow**
2. This opens Power Automate. Create a flow:
   - Trigger: **Run a flow from Copilot** (with text input `diagramPayload`)
   - Action: **HTTP**
     - Method: `POST`
     - URI: `https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io/generate`
     - Headers: `Content-Type: application/json`
     - Body: `@{triggerBody()['text']}`
   - Action: **Parse JSON** on the HTTP response body
   - Action: **Respond to Copilot** with outputs: `success`, `pngPath`, `drawioPath`
3. Save the flow as `Generate Architecture Diagram`
4. Return to Copilot Studio — the flow appears as a plugin action

---

## Step 13: Create Topics

### Topic 1: Describe Architecture

1. In Copilot Studio, go to **Topics** > **+ Add a topic** > **From blank**
2. **Name**: `Describe Architecture`
3. **Trigger phrases** (add all of these):
   - `create a diagram`
   - `generate architecture`
   - `draw architecture`
   - `create architecture diagram`
   - `I need a diagram`
   - `design my architecture`
   - `build a diagram`

4. **Build the flow** (add these nodes in order):

   **Node 1 — Message:**
   ```
   I can help you create an Azure architecture diagram! Describe your architecture in plain language. For example:

   "I need a 3-tier web app with a load balancer, 2 web server VMs behind it, and an Azure SQL database. The VMs should be in a web subnet and the database in a data subnet."

   The more detail you provide, the better the diagram. You can mention:
   - Components (VMs, databases, load balancers, app services, etc.)
   - Connections (what talks to what, and over which protocol)
   - Groupings (subnets, tiers, VNets)
   ```

   **Node 2 — Question:**
   - Ask: `Please describe your architecture:`
   - Identify: **User's entire response**
   - Save to variable: `architectureDescription`

   **Node 3 — Generative answers (AI-powered parsing):**
   - Add a **Create a prompt** action (Generative AI)
   - Prompt name: `Parse Architecture`
   - Prompt text:
   ```
   You are a JSON converter. The user described an Azure architecture below. Convert it to this exact JSON format. Use only these component types: vm, load balancer, application gateway, front door, sql server, cosmos db, storage account, function app, container instance, app service, key vault, vnet, nsg, firewall, service bus, managed identity, private endpoint, log analytics, app insights.

   Assign tiers: frontend (LBs, gateways, front doors), backend (VMs, app services, functions, containers), database (SQL, Cosmos, storage), security (key vault, managed identity, NSG), networking (VNet, subnet, firewall, private endpoint), monitoring (log analytics, app insights).

   Create logical groups (subnets) even if the user didn't mention them.

   User description: {architectureDescription}

   Return ONLY valid JSON in this format, nothing else:
   {"name":"diagram_name","components":[{"id":"short_id","type":"type","label":"Display Name","tier":"tier"}],"connections":[{"from_id":"id","to_id":"id","label":"protocol"}],"groups":[{"name":"Group Name","tier":"tier","members":["id1","id2"]}]}
   ```
   - Input: `architectureDescription` variable
   - Save output to variable: `parsedJSON`

   **Node 4 — Message (Confirmation):**
   ```
   Here is what I understood from your description. Please review the components:

   {parsedJSON}

   Does this look correct? I can add, remove, or change components before generating the diagram.
   ```

   **Node 5 — Question:**
   - Ask: `Shall I generate the diagram, or would you like changes?`
   - Identify: **Multiple choice**
   - Options: `Generate diagram` / `Make changes`
   - Save to: `userConfirmation`

   **Node 6 — Condition:**
   - If `userConfirmation` equals `Generate diagram`:
     - **Call action**: `GenerateDiagram` with input `parsedJSON`
     - Save result to: `generateResult`
     - **Message**:
       ```
       Your diagram has been generated! Here are your download links:

       - PNG: {baseUrl}/download/{name}.png
       - Editable DRAWIO: {baseUrl}/download/{name}.drawio

       The .drawio file is fully editable. Open it in:
       - VS Code with the Draw.io extension (hediet.vscode-drawio)
       - app.diagrams.net (free, browser-based)

       You can rearrange nodes, change colors, add annotations, or export to other formats. Would you like to make any changes to the architecture?
       ```
   - If `userConfirmation` equals `Make changes`:
     - Redirect to **Topic: Modify Diagram**

---

### Topic 2: Modify Diagram

1. **+ Add a topic** > **From blank**
2. **Name**: `Modify Diagram`
3. **Trigger phrases**:
   - `change the diagram`
   - `add a component`
   - `remove a component`
   - `modify the architecture`
   - `update the diagram`
   - `I want to change`

4. **Flow:**

   **Node 1 — Message:**
   ```
   What changes would you like to make? For example:
   - "Add a Redis cache between the VMs and the database"
   - "Remove the second VM"
   - "Move the database to its own subnet"
   - "Add a Key Vault for secrets"
   - "Change the load balancer to an application gateway"
   ```

   **Node 2 — Question:**
   - Ask: `Describe the changes:`
   - Save to: `modificationRequest`

   **Node 3 — Generative answers:**
   - Prompt name: `Apply Modifications`
   - Prompt text:
   ```
   You have an existing Azure architecture diagram JSON:
   {parsedJSON}

   The user wants these changes: {modificationRequest}

   Apply the changes to the JSON. Add new components with proper IDs, tiers, and connections. Remove components and their connections if requested. Move components between groups if requested.

   Return ONLY the updated valid JSON in the same format, nothing else.
   ```
   - Save output to: `parsedJSON` (overwrite the existing variable)

   **Node 4 — Message:**
   ```
   Updated architecture:

   {parsedJSON}

   Does this look correct?
   ```

   **Node 5 — Question (same confirm pattern as Topic 1, Node 5)**

   **Node 6 — Condition (same generate/change pattern as Topic 1, Node 6)**

---

### Topic 3: Help / Explain

1. **+ Add a topic** > **From blank**
2. **Name**: `Help and Info`
3. **Trigger phrases**:
   - `help`
   - `what can you do`
   - `how does this work`
   - `what is drawio`
   - `how to edit the diagram`
   - `supported services`
   - `what Azure services do you support`

4. **Flow:**

   **Node 1 — Message:**
   ```
   I help you create editable Azure architecture diagrams from plain text descriptions. Here's how it works:

   **Creating a diagram:**
   Say something like "Create a diagram with a load balancer, 2 web VMs, and a SQL database" and I'll generate it for you.

   **What you get:**
   - A PNG image for quick viewing and sharing
   - A .drawio file that is fully editable

   **Editing your diagram:**
   Open the .drawio file in:
   - VS Code (install the Draw.io extension by hediet)
   - app.diagrams.net (free browser editor)
   You can drag nodes, add text, change colors, and export to PDF/SVG/PNG.

   **Modifying the architecture:**
   Say "add a Redis cache" or "remove the second VM" and I'll regenerate with your changes.

   **Supported Azure services:**
   VMs, Load Balancers, Application Gateway, Front Door, SQL Server, Cosmos DB, Storage Accounts, Function Apps, Container Instances, App Services, Key Vault, VNets, NSGs, Firewalls, Service Bus, Managed Identity, Private Endpoints, Log Analytics, App Insights.

   **Alternative inputs:**
   You can also paste Terraform, Bicep, or ARM template code and I'll parse it into a diagram.

   What would you like to create?
   ```

---

## Step 14: Add Knowledge Sources (Optional)

In Copilot Studio, go to **Knowledge** > **+ Add knowledge**.

### Recommended knowledge documents to upload:

**1. Azure Architecture Patterns** (upload as a file or paste as text):
Upload the file `knowledge_architecture_patterns.md` (created alongside this guide).

**2. Component Reference** (upload as a file):
Upload the file `knowledge_component_reference.md` (created alongside this guide).

These give the agent context about common architecture patterns so it can suggest improvements and catch missing components.

---

## Step 15: End-to-End Testing

1. In Copilot Studio, click **Test** (bottom-left test panel)

2. **Test 1 — Basic diagram creation:**
   Type: `Create an architecture with a front door, application gateway, 2 web app VMs behind a load balancer, and a SQL database`
   - Verify: Agent asks for clarification or confirms the component list
   - Verify: Agent calls the GenerateDiagram action
   - Verify: You receive PNG and DRAWIO download links
   - Click the DRAWIO download link and open in app.diagrams.net to verify it's editable

3. **Test 2 — Modification:**
   Type: `Add a Key Vault and a Redis cache between the VMs and the database`
   - Verify: Agent updates the component list
   - Verify: New diagram is generated with the additions

4. **Test 3 — Help:**
   Type: `What Azure services do you support?`
   - Verify: Agent responds with the supported services list

5. **Test 4 — Ambiguity handling:**
   Type: `I need 2 servers and a database`
   - Verify: Agent asks clarifying questions (what kind of database? VMs or app services?)

6. **Test 5 — Complex architecture:**
   Type: `I need a hub-spoke network with a central firewall in the hub VNet, two spoke VNets each with an app service and a SQL database, connected via VNet peering, with a Key Vault in the hub for shared secrets`
   - Verify: Agent parses all components correctly
   - Verify: Generated diagram shows proper groupings

7. **Verify download endpoints directly** (from your browser or terminal):
   ```
   https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io/download/{name}.png
   https://diagram-api.yellowdune-01c84401.eastus.azurecontainerapps.io/download/{name}.drawio
   ```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Custom connector not visible in Copilot Studio | Ensure the connector and the agent are in the same Power Platform environment |
| "Action failed" when calling GenerateDiagram | Check the Container App logs: `az containerapp logs show --name diagram-api --resource-group rg-arch-diagrams` |
| Agent doesn't trigger the right topic | Add more trigger phrases or adjust the topic priority |
| Download links return 404 | The container scaled to zero and the files were lost. Diagram must be regenerated. Consider adding Blob Storage (Phase 4, Step 16) for persistent files |
| JSON parsing fails | Check that the generative prompt is returning clean JSON without markdown code fences |
