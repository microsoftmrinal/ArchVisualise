# icon_mappings.py
AZURE_ICON_MAP = {
    # Compute
    "vm": ("diagrams.azure.compute", "VM"),
    "virtual machine": ("diagrams.azure.compute", "VM"),
    "server": ("diagrams.azure.compute", "VM"),
    "availability set": ("diagrams.azure.compute", "AvailabilitySets"),
    "function app": ("diagrams.azure.compute", "FunctionApps"),
    "function": ("diagrams.azure.compute", "FunctionApps"),
    "azure function": ("diagrams.azure.compute", "FunctionApps"),
    "serverless": ("diagrams.azure.compute", "FunctionApps"),
    "container instance": ("diagrams.azure.compute", "ContainerInstances"),
    "aci": ("diagrams.azure.compute", "ContainerInstances"),
    "container": ("diagrams.azure.compute", "ContainerInstances"),
    "app service": ("diagrams.azure.compute", "AppServices"),
    "web app": ("diagrams.azure.compute", "AppServices"),
    "webapp": ("diagrams.azure.compute", "AppServices"),
    # Network
    "vnet": ("diagrams.azure.network", "VirtualNetworks"),
    "virtual network": ("diagrams.azure.network", "VirtualNetworks"),
    "subnet": ("diagrams.azure.network", "Subnets"),
    "load balancer": ("diagrams.azure.network", "LoadBalancers"),
    "lb": ("diagrams.azure.network", "LoadBalancers"),
    "application gateway": ("diagrams.azure.network", "ApplicationGateway"),
    "app gateway": ("diagrams.azure.network", "ApplicationGateway"),
    "appgw": ("diagrams.azure.network", "ApplicationGateway"),
    "waf": ("diagrams.azure.network", "ApplicationGateway"),
    "front door": ("diagrams.azure.network", "FrontDoors"),
    "frontdoor": ("diagrams.azure.network", "FrontDoors"),
    "cdn": ("diagrams.azure.network", "FrontDoors"),
    "nsg": ("diagrams.azure.network", "NetworkSecurityGroupsClassic"),
    "network security group": ("diagrams.azure.network", "NetworkSecurityGroupsClassic"),
    "public ip": ("diagrams.azure.network", "PublicIpAddresses"),
    "public ip address": ("diagrams.azure.network", "PublicIpAddresses"),
    "pip": ("diagrams.azure.network", "PublicIpAddresses"),
    "private endpoint": ("diagrams.azure.network", "PrivateEndpoint"),
    "private link": ("diagrams.azure.network", "PrivateEndpoint"),
    "firewall": ("diagrams.azure.network", "Firewall"),
    "azure firewall": ("diagrams.azure.network", "Firewall"),
    # Database
    "sql server": ("diagrams.azure.database", "SQLServers"),
    "sql database": ("diagrams.azure.database", "SQLDatabases"),
    "sql": ("diagrams.azure.database", "SQLServers"),
    "azure sql": ("diagrams.azure.database", "SQLServers"),
    "relational database": ("diagrams.azure.database", "SQLServers"),
    "cosmos db": ("diagrams.azure.database", "CosmosDb"),
    "cosmosdb": ("diagrams.azure.database", "CosmosDb"),
    "cosmos": ("diagrams.azure.database", "CosmosDb"),
    "nosql": ("diagrams.azure.database", "CosmosDb"),
    "document database": ("diagrams.azure.database", "CosmosDb"),
    "redis": ("diagrams.azure.database", "CacheForRedis"),
    "redis cache": ("diagrams.azure.database", "CacheForRedis"),
    "cache": ("diagrams.azure.database", "CacheForRedis"),
    # Storage
    "storage account": ("diagrams.azure.storage", "StorageAccounts"),
    "storage": ("diagrams.azure.storage", "StorageAccounts"),
    "blob storage": ("diagrams.azure.storage", "BlobStorage"),
    "blob": ("diagrams.azure.storage", "BlobStorage"),
    "files": ("diagrams.azure.storage", "StorageAccounts"),
    # Security
    "key vault": ("diagrams.azure.security", "KeyVaults"),
    "keyvault": ("diagrams.azure.security", "KeyVaults"),
    "secrets": ("diagrams.azure.security", "KeyVaults"),
    # Identity
    "managed identity": ("diagrams.azure.identity", "ManagedIdentities"),
    # Integration
    "service bus": ("diagrams.azure.integration", "ServiceBus"),
    "servicebus": ("diagrams.azure.integration", "ServiceBus"),
    "message queue": ("diagrams.azure.integration", "ServiceBus"),
    "queue": ("diagrams.azure.integration", "ServiceBus"),
    # Monitoring
    "log analytics": ("diagrams.azure.analytics", "LogAnalyticsWorkspaces"),
    "app insights": ("diagrams.azure.devops", "ApplicationInsights"),
    "application insights": ("diagrams.azure.devops", "ApplicationInsights"),
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

# Auto-assign tier based on component type when tier is not specified
TYPE_TO_TIER = {
    "vm": "backend", "virtual machine": "backend", "server": "backend",
    "app service": "backend", "web app": "backend", "webapp": "backend",
    "function app": "backend", "function": "backend", "azure function": "backend", "serverless": "backend",
    "container instance": "backend", "aci": "backend", "container": "backend",
    "load balancer": "frontend", "lb": "frontend",
    "application gateway": "frontend", "app gateway": "frontend", "appgw": "frontend", "waf": "frontend",
    "front door": "frontend", "frontdoor": "frontend", "cdn": "frontend",
    "public ip": "frontend", "public ip address": "frontend", "pip": "frontend",
    "sql server": "database", "sql database": "database", "sql": "database", "azure sql": "database",
    "cosmos db": "database", "cosmosdb": "database", "cosmos": "database", "nosql": "database",
    "redis": "database", "redis cache": "database", "cache": "database",
    "storage account": "database", "storage": "database", "blob storage": "database", "blob": "database",
    "key vault": "security", "keyvault": "security", "secrets": "security",
    "managed identity": "security",
    "nsg": "security", "network security group": "security",
    "vnet": "networking", "virtual network": "networking", "subnet": "networking",
    "firewall": "networking", "azure firewall": "networking",
    "private endpoint": "networking", "private link": "networking",
    "service bus": "backend", "servicebus": "backend", "message queue": "backend", "queue": "backend",
    "log analytics": "monitoring", "app insights": "monitoring", "application insights": "monitoring",
}


def normalize_type(raw_type: str) -> str | None:
    """Try to match a raw component type string to a known key in AZURE_ICON_MAP.
    Returns the matched key, or None if no match found."""
    t = raw_type.strip().lower()

    # Direct match
    if t in AZURE_ICON_MAP:
        return t

    # Strip common prefixes
    for prefix in ("azure ", "microsoft ", "ms "):
        if t.startswith(prefix):
            stripped = t[len(prefix):]
            if stripped in AZURE_ICON_MAP:
                return stripped

    # Substring match — check if any known key is contained in the input
    for key in AZURE_ICON_MAP:
        if key in t:
            return key

    # Check if the input is contained in any known key
    for key in AZURE_ICON_MAP:
        if t in key:
            return key

    return None


def auto_tier(comp_type: str) -> str:
    """Return the default tier for a given component type."""
    return TYPE_TO_TIER.get(comp_type.strip().lower(), "backend")
