# AgentFlow Architecture

AgentFlow is a simple, pragmatic stack designed to demo **multi-agent workflow automation** without heavy infra.

## High-Level Diagram

+---------------------+ HTTPS (REST) +----------------------+
| Next.js Frontend | <----------------> | FastAPI Backend |
| Tailwind v4 (UI) | | Orchestrator |
+----------+----------+ +----------+-----------+
| |
| |
| +-------v--------+
| | MongoDB |
| | workflows,runs |
| +----------------+

## Frontend → Backend Communication

- The UI uses `fetch` from the browser to call FastAPI routes:
  - `GET /api/workflows` — list saved workflows
  - `POST /api/workflows` — create a workflow
  - (Day 13) `POST /api/workflow-runs/:id` — start a run
  - (Day 13) `GET /api/workflow-runs/:id/logs` — stream logs (SSE)  
- In dev, the base URL is `NEXT_PUBLIC_API_BASE=http://localhost:8000`.

### Why this approach?
- Keep the frontend stateless; the backend is the single source of truth.
- Simpler deployments (Vercel for UI, Railway/Render for API).

## How Workflows Are Stored

- **Collection**: `workflows`
- **Document shape (simplified)**:
  ```json
  {
    "_id": "ObjectId",
    "name": "Inbound Lead → Research → Outreach",
    "trigger": { "type": "webhook", "path": "/lead" },
    "steps": [
      { "id": "uuid", "agent": "research",  "input_map": {} },
      { "id": "uuid", "agent": "qualify",   "input_map": {} },
      { "id": "uuid", "agent": "outreach",  "input_map": {} }
    ],
    "createdAt": "ISO8601"
  }