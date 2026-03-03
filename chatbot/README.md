# Chemical Procurement Chatbot

AI-powered chatbot for searching and comparing chemicals across multiple Indian vendors — Hyma Synthesis, Spectrochem, Glosil Scientific, and TCI Chemicals.

Built with **React + Vite** (frontend), **FastAPI + LangGraph** (backend), and **MongoDB** (persistence).

## Features

- **Multi-vendor search** — Searches 4 vendors in parallel, fetches detailed pricing and stock info
- **Image & PDF upload** — Upload product lists as images or PDFs; text is extracted automatically (Claude vision for images, PyPDF2 for PDFs) and used to search vendors
- **Quote table** — Editable in-chat procurement table with export to XLSX (preserves branded template with images)
- **Streaming responses** — Real-time token streaming, thinking blocks, tool call status
- **Extended thinking** — Claude Sonnet 4.5 with extended thinking enabled; collapsible thinking blocks in the UI
- **Conversation history** — MongoDB-backed persistence with sidebar for switching between conversations
- **Context engineering** — Token-counted LLM summarization of older messages, KV-cache-friendly prompt structure, error recovery, anti-few-shotting
- **Light / Dark mode**

## Architecture

```
┌─────────────┐       /api/*        ┌──────────────┐       ┌─────────┐
│   Frontend   │ ──── nginx proxy ── │   Backend    │ ────► │ MongoDB │
│  React/Vite  │       (port 3000)   │ FastAPI/LG   │       │  Mongo7 │
│    nginx     │                     │  (port 8000) │       │ (27017) │
└─────────────┘                      └──────┬───────┘       └─────────┘
                                            │
                                   Anthropic API (Claude)
                                   + Vendor websites (scraping)
```

## Quick Start (Docker Compose)

### Prerequisites

- Docker & Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Configure environment

```bash
cd chatbot
cp .env.example .env
```

Edit `.env` and set your API key:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Optional overrides (defaults shown)
MONGO_USER=admin
MONGO_PASSWORD=password123
MONGODB_DB=kavin_scientific
FRONTEND_PORT=3000
BACKEND_PORT=8000
MONGO_PORT=27017
```

### 2. Build and run

```bash
docker compose up --build -d
```

This starts three containers:

| Service    | Port  | Description                          |
|------------|-------|--------------------------------------|
| `frontend` | 3000  | React app served by nginx            |
| `backend`  | 8000  | FastAPI with LangGraph agent         |
| `mongodb`  | 27017 | MongoDB 7 with persistent volume     |

### 3. Open the app

Navigate to **http://localhost:3000**

### Useful commands

```bash
# View logs
docker compose logs -f

# View only backend logs
docker compose logs -f backend

# Stop all services
docker compose down

# Stop and remove volumes (clears DB)
docker compose down -v

# Rebuild a single service
docker compose up --build -d backend
```

## Local Development (without Docker)

### Backend

Requires **Python 3.12+** and **uv**.

```bash
cd chatbot/backend

# Create .env
cat > .env <<EOF
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
HOST=0.0.0.0
PORT=8000
MONGODB_CONNECTION_STRING=mongodb://admin:password123@localhost:27017/kavin_scientific?authSource=admin
EOF

# Install deps and run
uv sync
uv run python main.py
```

Backend runs on **http://localhost:8000**.

### Frontend

Requires **Node.js 20+**.

```bash
cd chatbot/frontend

npm install
npm run dev
```

Frontend runs on **http://localhost:5173** and proxies `/api` to the backend automatically (configured in `vite.config.ts`).

### MongoDB

Run MongoDB locally or via Docker:

```bash
docker run -d --name mongo \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password123 \
  mongo:7
```

## Project Structure

```
chatbot/
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── main.py                  # FastAPI app, streaming endpoint, file extraction
│   ├── config.py                # Environment config
│   ├── db.py                    # MongoDB service (conversations, messages)
│   ├── pyproject.toml           # Python dependencies
│   ├── Dockerfile
│   ├── agent/
│   │   ├── graph.py             # LangGraph agent, system prompt
│   │   ├── state.py             # State definitions
│   │   └── tools/
│   │       ├── hyma.py          # Hyma Synthesis search & details
│   │       ├── spectrochem.py   # Spectrochem search & details
│   │       ├── glosil.py        # Glosil Scientific search & details
│   │       ├── tci.py           # TCI Chemicals search & details
│   │       └── quote_table.py   # Structured quote table tool
│   ├── templates/
│   │   └── quote.xlsx           # Branded quote template
│   └── utils/
│       └── xml_quote_generator.py  # XLSX generation preserving images
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf               # Reverse proxy + SPA config
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── components/
        │   ├── ChatLayout.tsx   # Main layout
        │   ├── ChatInput.tsx    # Input with file attach + stop button
        │   ├── ChatMessages.tsx # Message list
        │   ├── MessageBubble.tsx # Renders text, tools, thinking, tables
        │   ├── QuoteTable.tsx   # Editable procurement table + XLSX export
        │   └── ConversationSidebar.tsx  # History sidebar
        ├── hooks/
        │   └── useChat.ts       # Chat state management
        ├── lib/
        │   └── api.ts           # API client + SSE stream handler
        └── types/
            └── index.ts         # Shared TypeScript types
```

## Environment Variables

| Variable                     | Required | Default                    | Description                     |
|------------------------------|----------|----------------------------|---------------------------------|
| `ANTHROPIC_API_KEY`          | Yes      | —                          | Anthropic API key               |
| `MONGO_USER`                 | No       | `admin`                    | MongoDB root username           |
| `MONGO_PASSWORD`             | No       | `password123`              | MongoDB root password           |
| `MONGODB_DB`                 | No       | `kavin_scientific`         | Database name                   |
| `FRONTEND_PORT`              | No       | `3000`                     | Frontend exposed port           |
| `BACKEND_PORT`               | No       | `8000`                     | Backend exposed port            |
| `MONGO_PORT`                 | No       | `27017`                    | MongoDB exposed port            |

## Tech Stack

| Layer     | Technology                                                     |
|-----------|----------------------------------------------------------------|
| LLM       | Claude Sonnet 4.5 (chat), Claude Haiku 4.5 (vision, summary)  |
| Agent     | LangGraph ReAct agent with 9 tools                            |
| Backend   | FastAPI, SSE streaming, PyPDF2, BeautifulSoup4, tiktoken       |
| Frontend  | React 19, Vite 7, Tailwind CSS 4, react-markdown              |
| Database  | MongoDB 7 via Motor (async driver)                             |
| Deploy    | Docker Compose, nginx reverse proxy                            |
