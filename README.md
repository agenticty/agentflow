# AgentFlow 🤖

**Multi-Agent Revenue Operations Platform**

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://agentflow-tau.vercel.app/app)

> Autonomous AI agent system that qualifies prospects and generates personalized outreach, reducing manual sales operations.

![AgentFlow Banner](https://github.com/user-attachments/assets/5abeea04-f529-4e23-9c12-54205b21fceb)

---

## What is AgentFlow?

AgentFlow is a production-ready agentic AI platform designed to automate B2B revenue operations. The system uses three autonomous agents that work together to research prospects, qualify them against your Ideal Customer Profile (ICP), and generate personalized outreach emails.

**The Problem:** Sales teams waste 60-80% of their time on manual prospect research and qualification before ever reaching out to potential customers.

**The Solution:** AgentFlow's multi-agent system handles this entire workflow autonomously, allowing sales teams to focus on high-value activities like discovery calls and closing deals.

---

## Key Features

### 🔍 **Research Agent**
- Automatically gathers comprehensive company intelligence
- Analyzes company websites, news, and public data sources
- Identifies key decision-makers and pain points

### ✅ **Qualify Agent**
- Evaluates prospects against your custom ICP criteria
- Assigns qualification scores with detailed reasoning
- Filters out poor-fit prospects before outreach

### ✉️ **Outreach Agent**
- Generates personalized email copy tailored to each prospect
- Incorporates research findings and qualification insights
- Optimized for booking discovery calls, not generic pitching

### 🔧 **Advanced Customization**
- Reorder agent execution to match your workflow
- Define custom ICP criteria
- Adjust agent prompts and parameters
- Monitor agent reasoning in real-time

---

## Tech Stack

**AI & Orchestration:**
- [LangChain](https://www.langchain.com/) - Agent framework and orchestration
- [CrewAI](https://www.crewai.io/) - Multi-agent collaboration
- [OpenAI API](https://openai.com/) - Large language model (GPT-4)

**Backend:**
- Python 3.11+
- FastAPI
- PostgreSQL
- Docker

**Frontend:**
- Next.js 14
- React 18
- Tailwind CSS
- TypeScript

**Infrastructure:**
- Vercel (frontend hosting)
- Railway (backend hosting)
- Docker containerization

---

## 📦 Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- OpenAI API key


## 🎮 Usage

### Basic Workflow

1. **Define Your ICP**
   - Set criteria for your ideal customer (industry, company size, tech stack, etc.)

2. **Add Prospects**
   - Input company names or domains to research

3. **Run Agent Workflow**
   - Agents autonomously research → qualify → generate outreach

4. **Review Results**
   - See qualification scores, reasoning, and generated emails
   - Approve or edit outreach before sending


---

## 🏗️ Architecture
```
┌─────────────────┐
│   Next.js App   │  ← User Interface
└────────┬────────┘
         │
    [REST API]
         │
┌────────▼────────┐
│  FastAPI Server │  ← Business Logic
└────────┬────────┘
         │
    ┌────▼────┐
    │ CrewAI  │  ← Agent Orchestration
    │ Engine  │
    └────┬────┘
         │
    ┌────▼─────────────┐
    │  Agent Execution │
    ├──────────────────┤
    │ • Research Agent │
    │ • Qualify Agent  │
    │ • Outreach Agent │
    └────┬─────────────┘
         │
    [OpenAI API Calls]
```

---

## 💡 Use Cases

- **Sales Teams:** Automate top-of-funnel qualification
- **Marketing Agencies:** Scale outbound for multiple clients
- **Startups:** Identify and engage ICP-fit prospects with limited resources
- **Consultants:** Research potential clients before outreach

---

## Security & Privacy

- API keys stored as environment variables (never committed)
- All prospect data encrypted at rest
- GDPR-compliant data handling
- Rate limiting on API endpoints
- Input validation and sanitization

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## Author

**Ty McLean**
- GitHub: [@agenticty](https://github.com/agenticty)
- LinkedIn: [Ty McLean](https://linkedin.com/in/ty-mclean)

---

**If you find AgentFlow useful, please consider starring this repository!**
```
