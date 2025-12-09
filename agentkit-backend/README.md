# Kavin Scientific AgentKit Backend

This is the AgentKit backend implementation for Kavin Scientific, integrating your agent with ChatKit protocol.

## Architecture

```
Frontend (ChatKit) → AgentKit Backend → Agent (GPT-5) → Tools → RAG Service
```

## Features

- **Agent Integration**: Uses your GPT-5 agent with reasoning capabilities
- **Tool Support**: 
  - `file_search`: Search product catalogs via RAG service
  - `generate_quote_for_products`: Generate Excel quotes with brand mapping
- **ChatKit Protocol**: Full ChatKit server implementation
- **Streaming**: Real-time response streaming
- **Brand Mapping**: Automatic brand detection from catalog filenames

## Setup

### 1. Install Dependencies

```bash
cd agentkit-backend
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file:

```bash
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# RAG Service
RAG_SERVICE_URL=http://localhost:8001

# Template and Output
TEMPLATE_PATH=./mcp/quote.xlsx
OUTPUT_DIR=./mcp

# DigitalOcean Spaces (for quote uploads)
DO_ACCESS_KEY=your_do_access_key
DO_SECRET_KEY=your_do_secret_key
DO_SPACE_NAME=optimus
DO_REGION=ams3
DO_ENDPOINT=ams3.digitaloceanspaces.com

# Server Configuration
PORT=8005
HOST=0.0.0.0
```

### 3. Start the Backend

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

## API Endpoints

### ChatKit Endpoint
- **POST** `/chatkit` - Main ChatKit protocol endpoint

### Health Check
- **GET** `/health` - Service health check

### Root
- **GET** `/` - Service information

## Integration with Frontend

Update your frontend to connect to this backend instead of OpenAI's hosted workflow.

### Option 1: Update Frontend API Route

Modify `frontend/app/api/create-session/route.ts` to use your backend:

```typescript
// Use your backend for session creation
const apiBase = process.env.CHATKIT_API_BASE ?? "http://localhost:8005";
const url = `${apiBase}/chatkit/sessions`;
```

### Option 2: Keep OpenAI Workflow

You can still use OpenAI's workflow, but configure it to call your backend tools via HTTP.

## How It Works

1. **User sends message** → Frontend → ChatKit Backend
2. **Backend processes** → Converts to agent input format
3. **Agent runs** → Uses tools (file_search, generate_quote)
4. **Tools execute** → Call RAG service, generate quotes
5. **Response streams** → Back to frontend via ChatKit protocol

## Agent Behavior

The agent follows your instructions:
- Searches products individually using `file_search`
- Determines brand from catalog filename
- Uses mock data when information is missing
- Generates Excel quotes with all product details
- Uploads quotes to DigitalOcean Spaces

## Brand Mapping

Brands are automatically determined from catalog filenames:

| Catalog File | Brand |
|-------------|-------|
| SRL- PRICE LIST Excel_Version-2024-25.pdf | SRL |
| Hyma Pricelist 2025-2026 incl bio (1) (1).pdf | HYMA |
| SH - SEPT - 04-09-2025 (1).pdf | SH |
| ISOCHEM%20PRICE%20LIST%2008-05-2025%20(2).pdf | ISOCHEM |

## Troubleshooting

### Agent not responding
- Check OpenAI API key is set correctly
- Verify RAG service is running on port 8001
- Check logs for errors

### Tools not working
- Ensure RAG service is accessible
- Verify template file exists at TEMPLATE_PATH
- Check DigitalOcean Spaces credentials

### Streaming issues
- Check CORS settings
- Verify frontend is connecting to correct endpoint
- Check network connectivity

## Development

### Running in Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

### Testing

```bash
# Health check
curl http://localhost:8005/health

# Test ChatKit endpoint (requires proper ChatKit request format)
curl -X POST http://localhost:8005/chatkit \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "test", "message": "Hello"}'
```

## Notes

- The agent uses GPT-5 with reasoning enabled (low effort, auto summary)
- All tool calls are logged for debugging
- Thread history is managed by ChatKit protocol
- Quotes are automatically uploaded to DigitalOcean Spaces
