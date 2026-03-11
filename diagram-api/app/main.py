# main.py
import os
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
    from_id: str  # renamed from "from" since it is a Python keyword
    to_id: str  # renamed from "to" for consistency
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
