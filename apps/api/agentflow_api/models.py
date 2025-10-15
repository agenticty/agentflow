from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime

class InputField(BaseModel):
    name: str               # "company"
    label: str              # "Company name"
    type: str = "text"      # "text" | "email" | "url"
    placeholder: Optional[str] = None
    required: bool = True

class WorkflowStep(BaseModel):
    id: str
    agent: str  # e.g., "research", "qualify", "outreach"
    instructions: Optional[str] = "" # <-- NEW (free text; can include {{input.company}} etc.)
    input_map: Dict[str, Any] = {}  # how to map previous outputs to this step's inputs

class Workflow(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""          # <-- NEW: human description
    trigger: Dict[str, Any]
    steps: List[WorkflowStep]
    input_schema: List[InputField] = Field(default_factory=list)  # <-- NEW: 

class CreateWorkflowRequest(BaseModel):
    name: str
    trigger: Dict[str, Any]
    steps: List[WorkflowStep]

class CreateRunRequest(BaseModel):
    workflow_id: str
    inputs: Dict[str, Any] = {}

class WorkflowRun(BaseModel):
    id: Optional[str] = None
    workflow_id: str
    status: str = "running"  # running | success | error
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None