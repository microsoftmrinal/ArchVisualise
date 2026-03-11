# diagram_builder.py
import os
import subprocess
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
    lines = ["import subprocess"]
    lines.append("from diagrams import Diagram, Cluster, Edge")
    for module_path, class_name in imports:
        lines.append(f"from {module_path} import {class_name}")

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
        lines.append(
            f'    with Cluster("{g["name"]}", graph_attr={{"fontsize":"13","bgcolor":"{color}","style":"rounded","margin":"15"}}):'
        )
        for mid in g.get("members", []):
            comp = next((c for c in components if c["id"] == mid), None)
            if comp:
                _, cls = AZURE_ICON_MAP.get(comp["type"].lower(), (None, None))
                if cls:
                    lines.append(
                        f'        {comp["id"]} = {cls}("{comp.get("label", comp["id"])}")'
                    )

    # Ungrouped nodes
    for comp in components:
        if comp["id"] not in grouped_ids:
            _, cls = AZURE_ICON_MAP.get(comp["type"].lower(), (None, None))
            if cls:
                lines.append(
                    f'    {comp["id"]} = {cls}("{comp.get("label", comp["id"])}")'
                )

    # Connections
    for conn in connections:
        label = f'label="{conn["label"]}"' if conn.get("label") else ""
        lines.append(f'    {conn["from"]} >> Edge({label}) >> {conn["to"]}')

    # Add drawio conversion
    lines.append(
        f'subprocess.run(["graphviz2drawio","{filename}.dot","-o","{filename}.drawio"], check=True)'
    )

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
        },
    }
