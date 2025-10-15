# AgentFlow

AgentFlow is a **multi-agent workflow automation** platform. Define a workflow once (e.g., “When a lead comes in → research → qualify → outreach”) and AI agents run each step end-to-end.

## Demo Screenshots

**Landing**
![Landing](docs/images/landing.png)

**Empty Workflow State**
![Empty](docs/images/workflows-empty.png)

**Create Workflow – Success**
![Create Success](docs/images/create-success.png)

**Workflow List**
![List](docs/images/workflows-list.png)


## Quick Start

### Prereqs
- Node 18+ and Python 3.11+
- MongoDB (Docker compose provided)
- API keys in `.env` as needed (e.g., `OPENAI_API_KEY`)

### 1) Infra (Mongo)
```bash
cd infra
docker compose up -d
