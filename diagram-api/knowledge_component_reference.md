# Azure Component Reference for Diagram Agent

## Compute
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| VM, virtual machine, server | vm | backend | Receives from LB (HTTPS/443), sends to DB (1433) |
| App Service, web app | app service | backend | Receives from AppGW (HTTPS), sends to DB, Key Vault |
| Function App, serverless function | function app | backend | Triggered by Service Bus, HTTP, Timer; sends to DB, Storage |
| Container Instance, ACI | container instance | backend | Receives from LB/AppGW, sends to DB |
| Availability Set | availability set | backend | Groups VMs for fault domain distribution |

## Networking
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| Load Balancer, LB | load balancer | frontend | Receives internet traffic, distributes to VMs |
| Application Gateway, App Gateway, WAF | application gateway | frontend | L7 load balancing with WAF, routes to App Services/VMs |
| Front Door, CDN | front door | frontend | Global load balancer, routes to regional backends |
| VNet, virtual network | vnet | networking | Contains subnets |
| NSG, network security group | nsg | security | Filters traffic on subnet or NIC level |
| Firewall | firewall | networking | Centralized traffic filtering in hub VNet |
| Public IP | public ip | frontend | Attached to LB, AppGW, or VM |
| Private Endpoint, Private Link | private endpoint | networking | Secures access to PaaS services (SQL, Key Vault, Storage) |

## Database & Storage
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| SQL Server, SQL Database, relational | sql server | database | Receives from backends (Port 1433) |
| Cosmos DB, NoSQL, document database | cosmos db | database | Receives from backends (HTTPS/443) |
| Storage Account, blob, files | storage account | database | Receives from backends (HTTPS/443) |
| Blob Storage | blob storage | database | Receives from backends, Function Apps |

## Security & Identity
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| Key Vault, secrets, certificates | key vault | security | Accessed by App Services, VMs, Functions via Managed Identity |
| Managed Identity | managed identity | security | Assigned to compute resources for passwordless auth |

## Integration
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| Service Bus, message queue | service bus | backend | Receives from producers, consumed by Functions/Apps |

## Monitoring
| Customer Term | Component Type | Tier | Common Connections |
|---|---|---|---|
| Log Analytics | log analytics | monitoring | Receives logs from all resources |
| App Insights, Application Insights | app insights | monitoring | Receives telemetry from App Services, Functions |

## Default Ports and Protocols
- HTTPS: 443 (web traffic, API calls, PaaS service access)
- SQL: 1433 (SQL Server connections)
- SSH: 22 (VM management)
- RDP: 3389 (Windows VM management)
- HTTP: 80 (unencrypted web, usually redirected to 443)
- AMQP: 5671 (Service Bus)

## Tier Color Coding
| Tier | Background Color | Used For |
|---|---|---|
| frontend / web | #E3F2FD (light blue) | Load balancers, gateways, Front Door |
| backend / app | #E8F5E9 (light green) | VMs, App Services, Functions, Containers |
| database / data | #FFF3E0 (light orange) | SQL, Cosmos DB, Storage |
| loadbalancer | #F3E5F5 (light purple) | Load balancers when displayed separately |
| security | #FCE4EC (light pink) | Key Vault, Managed Identity, NSG |
| networking | #F3E5F5 (light purple) | VNets, Subnets, Firewalls, Private Endpoints |
| monitoring | #E0F7FA (light teal) | Log Analytics, App Insights |
