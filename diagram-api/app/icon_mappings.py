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
