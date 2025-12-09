# MCP Server - stdio Transport

This is the stdio-based MCP server for Kavin Scientific. It communicates via stdin/stdout and is designed to be used with the OpenAI Agents SDK's `MCPServerStdio` client.

## Differences from HTTP/SSE Server

- **Transport**: Uses stdin/stdout instead of HTTP/SSE
- **Usage**: Run as a subprocess, not as a web server
- **Integration**: Used directly by the Agents SDK via `MCPServerStdio`
- **No FastAPI**: No web framework needed, pure MCP protocol

## Setup

### 1. Install Dependencies

```bash
cd mcp
pip install -r requirements.txt
```

### 2. Environment Variables (Optional)

The server uses environment variables for configuration:

```bash
# RAG Service
export RAG_SERVICE_URL="http://localhost:8001"

# Template and Output
export TEMPLATE_PATH="./quote.xlsx"
export OUTPUT_DIR="./"

# DigitalOcean Spaces
export DO_ACCESS_KEY="your_key"
export DO_SECRET_KEY="your_secret"
export DO_SPACE_NAME="optimus"
export DO_REGION="ams3"
export DO_ENDPOINT="ams3.digitaloceanspaces.com"
```

### 3. Test the Server

You can test the server directly:

```bash
# Windows
python mcp_server_stdio.py

# Mac/Linux
python3 mcp_server_stdio.py
```

The server will wait for MCP protocol messages on stdin and respond on stdout.

## Integration with AgentKit Backend

The stdio server is automatically used by the AgentKit backend via `MCPServerStdio`. The backend spawns this script as a subprocess and communicates with it via stdin/stdout.

## Available Tools

1. **`generate_quote_for_products`** - Generate Excel quotes for products
2. **`file_search`** - Search documents via RAG service
3. **`get_document_info`** - Get document metadata
4. **`list_collections`** - List available collections

## Troubleshooting

### Server won't start
- Check Python path is correct
- Verify all dependencies are installed
- Check that template file exists at TEMPLATE_PATH

### Tools not working
- Ensure RAG service is running on port 8001
- Check environment variables are set correctly
- Verify DigitalOcean Spaces credentials if using upload

### Connection issues
- The stdio server is managed by the Agents SDK
- Check agentkit-backend logs for connection errors
- Verify the server script path is correct in agent.py

## Architecture

```
AgentKit Backend
    ↓ (spawns subprocess)
MCPServerStdio
    ↓ (stdin/stdout)
mcp_server_stdio.py
    ↓ (HTTP calls)
RAG Service (port 8001)
```

## Notes

- The server runs as a subprocess managed by the Agents SDK
- No need to manually start/stop the server
- The SDK handles process lifecycle automatically
- All communication is via MCP protocol over stdin/stdout
