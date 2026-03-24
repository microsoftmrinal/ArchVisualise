<#
.SYNOPSIS
    Deploys the Azure Architecture Diagram Agent end-to-end.

.DESCRIPTION
    Creates all Azure resources, configures Managed Identity RBAC (no API keys),
    builds the container image, and deploys the Container App.

    Security guardrails:
    - Managed Identity for all service-to-service auth (no stored secrets)
    - ACR admin disabled; Container App pulls via managed identity
    - Storage account: shared-key access disabled, HTTPS-only, TLS 1.2
    - Blob container: private access only, SAS via user-delegation keys
    - Container App: HTTPS-only ingress, non-root container, system-assigned identity
    - Azure OpenAI: accessed via RBAC, no API key in env vars
    - Diagnostic logging to Log Analytics workspace

.PARAMETER ResourceGroup
    Name of the Azure resource group (default: rg-arch-diagrams)

.PARAMETER Location
    Azure region for most resources (default: eastus)

.PARAMETER AoaiLocation
    Azure region for Azure OpenAI — gpt-4o availability varies (default: eastus2)

.PARAMETER AcrName
    Azure Container Registry name — must be globally unique (default: acrarchdiagrams)

.PARAMETER StorageAccountName
    Storage account name — must be globally unique (default: starchdiagrams)

.PARAMETER AoaiName
    Azure OpenAI resource name (default: aoai-arch-diagrams)

.PARAMETER ImageTag
    Docker image tag (default: v1)

.PARAMETER SkipProviderRegistration
    Skip Azure provider registration if already done

.EXAMPLE
    .\deploy.ps1
    .\deploy.ps1 -ResourceGroup "my-rg" -Location "westus2" -ImageTag "v2"
    .\deploy.ps1 -SkipProviderRegistration
#>

[CmdletBinding()]
param(
    [string]$ResourceGroup = "rg-arch-diagrams",
    [string]$Location = "eastus",
    [string]$AoaiLocation = "eastus2",
    [string]$AcrName = "acrarchdiagrams",
    [string]$StorageAccountName = "starchdiagrams",
    [string]$AoaiName = "aoai-arch-diagrams",
    [string]$ContainerAppName = "diagram-api",
    [string]$ContainerEnvName = "diagram-env",
    [string]$ImageTag = "v1",
    [switch]$SkipProviderRegistration
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Helper ────────────────────────────────────────────────────────────────────
function Write-Step { param([string]$Message) Write-Host "`n▶ $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "  ✔ $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "  ⚠ $Message" -ForegroundColor Yellow }

# ── Pre-flight checks ────────────────────────────────────────────────────────
Write-Step "Pre-flight checks"

# Verify Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is not installed. Install from https://aka.ms/installazurecli"
}

# Verify logged in
$account = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Not logged in to Azure CLI. Run 'az login' first."
}
$subscriptionName = ($account | ConvertFrom-Json).name
$subscriptionId   = ($account | ConvertFrom-Json).id
Write-Ok "Logged in — subscription: $subscriptionName ($subscriptionId)"

# Verify the diagram-api folder exists
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$apiDir = Join-Path $scriptRoot "diagram-api"
if (-not (Test-Path (Join-Path $apiDir "Dockerfile"))) {
    throw "Cannot find diagram-api/Dockerfile. Run this script from the repository root."
}
Write-Ok "Project files found at $apiDir"

$imageFull = "$AcrName.azurecr.io/diagram-api:$ImageTag"

# ── 1. Register providers ────────────────────────────────────────────────────
if (-not $SkipProviderRegistration) {
    Write-Step "Registering Azure resource providers (one-time)"
    $providers = @(
        "Microsoft.ContainerRegistry",
        "Microsoft.App",
        "Microsoft.OperationalInsights",
        "Microsoft.CognitiveServices",
        "Microsoft.Storage"
    )
    foreach ($p in $providers) {
        az provider register --namespace $p --wait 2>$null
        Write-Ok $p
    }
}

# ── 2. Resource Group ────────────────────────────────────────────────────────
Write-Step "Creating resource group: $ResourceGroup"
az group create --name $ResourceGroup --location $Location -o none
Write-Ok "Resource group ready"

# ── 3. Log Analytics workspace (for Container App diagnostics) ───────────────
Write-Step "Creating Log Analytics workspace"
$lawName = "law-arch-diagrams"
az monitor log-analytics workspace create `
    --resource-group $ResourceGroup `
    --workspace-name $lawName `
    --location $Location `
    --retention-in-days 30 `
    -o none 2>$null
$lawId = az monitor log-analytics workspace show `
    --resource-group $ResourceGroup `
    --workspace-name $lawName `
    --query customerId -o tsv
$lawKey = az monitor log-analytics workspace get-shared-keys `
    --resource-group $ResourceGroup `
    --workspace-name $lawName `
    --query primarySharedKey -o tsv
Write-Ok "Log Analytics workspace: $lawName"

# ── 4. Container Registry (admin DISABLED — use managed identity to pull) ────
Write-Step "Creating Azure Container Registry: $AcrName"
az acr create `
    --resource-group $ResourceGroup `
    --name $AcrName `
    --sku Basic `
    --admin-enabled false `
    -o none 2>$null
Write-Ok "ACR created (admin disabled — will use managed identity for pull)"

# ── 5. Build container image in ACR ──────────────────────────────────────────
Write-Step "Building container image: $imageFull"
az acr build --registry $AcrName --image "diagram-api:$ImageTag" $apiDir --no-logs
if ($LASTEXITCODE -ne 0) { throw "ACR build failed" }
Write-Ok "Image built successfully"

# ── 6. Container App Environment ─────────────────────────────────────────────
Write-Step "Creating Container App environment: $ContainerEnvName"
az containerapp env create `
    --name $ContainerEnvName `
    --resource-group $ResourceGroup `
    --location $Location `
    --logs-workspace-id $lawId `
    --logs-workspace-key $lawKey `
    -o none 2>$null
Write-Ok "Container App environment ready (logs → $lawName)"

# ── 7. Container App (with system-assigned identity) ─────────────────────────
Write-Step "Deploying Container App: $ContainerAppName"

# Grant ACR pull to the Container App via managed identity
# First create with a temporary public image, then assign identity and switch
az containerapp create `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --environment $ContainerEnvName `
    --image "mcr.microsoft.com/k8se/quickstart:latest" `
    --target-port 8080 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 3 `
    --cpu 1.0 --memory 2.0Gi `
    --system-assigned `
    -o none 2>$null

# Get the Container App's managed identity principal ID
$principalId = az containerapp identity show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query principalId -o tsv
Write-Ok "System-assigned identity: $principalId"

# Grant AcrPull role to the Container App's identity
$acrId = az acr show --name $AcrName --resource-group $ResourceGroup --query id -o tsv
az role assignment create `
    --assignee $principalId `
    --role "AcrPull" `
    --scope $acrId `
    -o none 2>$null
Write-Ok "Granted AcrPull on $AcrName (no admin credentials needed)"

# Now update to use the real image via managed identity
az containerapp registry set `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --server "$AcrName.azurecr.io" `
    --identity system `
    -o none 2>$null

az containerapp update `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --image $imageFull `
    -o none 2>$null
Write-Ok "Container App running image: $imageFull"

# ── 8. Azure OpenAI ──────────────────────────────────────────────────────────
Write-Step "Creating Azure OpenAI: $AoaiName"
az cognitiveservices account create `
    --name $AoaiName `
    --resource-group $ResourceGroup `
    --kind OpenAI `
    --sku S0 `
    --location $AoaiLocation `
    --custom-domain $AoaiName `
    -o none 2>$null

az cognitiveservices account deployment create `
    --name $AoaiName `
    --resource-group $ResourceGroup `
    --deployment-name gpt-4o `
    --model-name gpt-4o `
    --model-version "2024-11-20" `
    --model-format OpenAI `
    --sku-capacity 10 `
    --sku-name "GlobalStandard" `
    -o none 2>$null
Write-Ok "Azure OpenAI with gpt-4o deployed"

# Grant Cognitive Services OpenAI User role
$aoaiId = az cognitiveservices account show --name $AoaiName --resource-group $ResourceGroup --query id -o tsv
az role assignment create `
    --assignee $principalId `
    --role "Cognitive Services OpenAI User" `
    --scope $aoaiId `
    -o none 2>$null
Write-Ok "Granted Cognitive Services OpenAI User (Managed Identity — no API key)"

# ── 9. Storage Account (hardened) ────────────────────────────────────────────
Write-Step "Creating Storage Account: $StorageAccountName"
az storage account create `
    --name $StorageAccountName `
    --resource-group $ResourceGroup `
    --sku Standard_LRS `
    --location $Location `
    --https-only true `
    --min-tls-version TLS1_2 `
    --allow-blob-public-access false `
    --allow-shared-key-access false `
    -o none 2>$null

az storage container create `
    --name diagrams `
    --account-name $StorageAccountName `
    --auth-mode login `
    -o none 2>$null

# Grant Storage Blob Data Contributor to the Container App
$storageId = az storage account show --name $StorageAccountName --resource-group $ResourceGroup --query id -o tsv
az role assignment create `
    --assignee $principalId `
    --role "Storage Blob Data Contributor" `
    --scope $storageId `
    -o none 2>$null
Write-Ok "Storage hardened: HTTPS-only, TLS 1.2, shared-key disabled, no public blob access"

# ── 10. Set environment variables on Container App ───────────────────────────
Write-Step "Configuring Container App environment variables"
$aoaiEndpoint = "https://$AoaiName.openai.azure.com/"
az containerapp update `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --set-env-vars `
        "AZURE_OPENAI_ENDPOINT=$aoaiEndpoint" `
        "AZURE_OPENAI_DEPLOYMENT=gpt-4o" `
        "AZURE_STORAGE_ACCOUNT=$StorageAccountName" `
        "AZURE_STORAGE_CONTAINER=diagrams" `
    -o none 2>$null
Write-Ok "Environment variables set (no secrets — all via Managed Identity)"

# ── 11. Verify ───────────────────────────────────────────────────────────────
Write-Step "Verifying deployment"

# Wait for the new revision to become ready
Start-Sleep -Seconds 15

$fqdn = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query "properties.configuration.ingress.fqdn" -o tsv
$baseUrl = "https://$fqdn"

try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 30
    if ($health.status -eq "ok") {
        Write-Ok "Health check passed"
    } else {
        Write-Warn "Unexpected health response: $($health | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Warn "Health check failed (app may still be starting): $_"
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "`n" -NoNewline
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Resource Group:    $ResourceGroup"
Write-Host "  Container App:     $baseUrl"
Write-Host "  Container Image:   $imageFull"
Write-Host "  Azure OpenAI:      $aoaiEndpoint"
Write-Host "  Storage Account:   $StorageAccountName"
Write-Host "  Log Analytics:     $lawName"
Write-Host ""
Write-Host "  Security:" -ForegroundColor Yellow
Write-Host "    ✔ Managed Identity for OpenAI, Storage, and ACR pull"
Write-Host "    ✔ No API keys or secrets in environment variables"
Write-Host "    ✔ ACR admin credentials disabled"
Write-Host "    ✔ Storage: HTTPS-only, TLS 1.2, shared-key disabled"
Write-Host "    ✔ Blob container: private (SAS via user delegation keys)"
Write-Host "    ✔ Container runs as non-root user (appuser)"
Write-Host "    ✔ HTTPS-only ingress with proxy headers"
Write-Host "    ✔ Diagnostics logging to Log Analytics"
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    1. Import openapi-spec.json as a Custom Connector in Power Platform"
Write-Host "    2. Create the Copilot Studio agent (see phase3_copilot_studio_guide.md)"
Write-Host "    3. Test: Invoke-RestMethod -Method Post -Uri '$baseUrl/chat' ``"
Write-Host "         -ContentType 'application/json' ``"
Write-Host "         -Body '{""message"":""A web app with a load balancer and 2 VMs""}'"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
