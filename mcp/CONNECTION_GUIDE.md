# MCP Server Connection Guide

This guide explains how to connect to the MCP server running at `/Users/saravanan/kavin/chatkit-kavin-scientific/mcp/mcp_server.py`.

## Quick Start

### 1. Install Dependencies

First, make sure you have all required dependencies installed:

```bash
cd /Users/saravanan/kavin/chatkit-kavin-scientific/mcp
pip install -r requirements.txt
```

Required packages:
- `mcp>=1.0.0`
- `openpyxl>=3.1.0`
- `boto3>=1.26.0`
- `fastapi`
- `uvicorn`
- `httpx`

### 2. Start the MCP Server

Run the server directly:

```bash
cd /Users/saravanan/kavin/chatkit-kavin-scientific/mcp
python mcp_server.py
```

The server will start on `http://0.0.0.0:8000` (accessible at `http://localhost:8000`).

### 3. Connection Endpoints

Once running, the server exposes:

- **SSE Endpoint**: `http://localhost:8000/messages/`
  - This is the main MCP endpoint for Server-Sent Events communication
  - Use this for MCP client connections

- **FastAPI Docs**: `http://localhost:8000/docs`
  - Interactive API documentation (Swagger UI)

- **FastAPI ReDoc**: `http://localhost:8000/redoc`
  - Alternative API documentation

## Connection Methods

### Method 1: HTTP/SSE Connection (Recommended)

For HTTP-based MCP clients, connect to:

```
http://localhost:8000/messages/
```

**Example MCP Client Configuration:**

```json
{
  "mcpServers": {
    "quote-generator": {
      "url": "http://localhost:8000/messages/",
      "transport": "sse"
    }
  }
}
```

### Method 2: Direct HTTP API Calls

You can also make direct HTTP requests to test the server. The server uses Server-Sent Events (SSE), so you'll need an SSE-compatible client.

**Using curl to test the SSE endpoint:**

```bash
curl -N http://localhost:8000/messages/
```

**Using Python with httpx:**

```python
import httpx
import asyncio

async def test_mcp_server():
    async with httpx.AsyncClient() as client:
        # Test SSE connection
        async with client.stream('GET', 'http://localhost:8000/messages/') as response:
            async for line in response.aiter_lines():
                print(line)

asyncio.run(test_mcp_server())
```

### Method 3: Stdio Mode (If Needed)

If you need stdio mode instead of HTTP, you would need to modify the server to support it. Currently, the server only runs in HTTP mode via FastAPI.

## Available Tools

Once connected, the MCP server provides these tools:

1. **`generate_quote_for_products`**
   - Generates Excel quotes for products
   - Uploads to DigitalOcean Spaces
   - Returns public URL

2. **`file_search`**
   - Searches documents using the RAG service
   - Requires RAG service running on `http://localhost:8001`

3. **`get_document_info`**
   - Retrieves information about a specific document

4. **`list_collections`**
   - Lists all available document collections

## Prerequisites

Before connecting, ensure:

1. **Template File Exists**: 
   - Template should be at: `/Users/saravanan/kavin/chatkit-kavin-scientific/mcp/quote.xlsx`
   - (Currently configured path in the code)

2. **RAG Service Running** (for file search tools):
   - Must be running on `http://localhost:8001`
   - The MCP server expects the RAG service to be available

3. **DigitalOcean Spaces Credentials** (for quote uploads):
   - Credentials are configured in the code
   - Ensure they're valid if you need upload functionality

## Testing the Connection

### Test 1: Check if server is running

```bash
curl http://localhost:8000/docs
```

You should see the FastAPI documentation page.

### Test 2: Test SSE endpoint

```bash
curl -N -H "Accept: text/event-stream" http://localhost:8000/messages/
```

### Test 3: Use the test script

```bash
cd /Users/saravanan/kavin/chatkit-kavin-scientific/mcp
python test_mcp_server.py
```

## Troubleshooting

### Server won't start

- Check if port 8000 is already in use: `lsof -i :8000`
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (should be 3.8+)

### Connection refused

- Verify the server is running: `ps aux | grep mcp_server`
- Check firewall settings
- Ensure you're using the correct URL: `http://localhost:8000/messages/`

### RAG service connection errors

- Ensure RAG service is running on `http://localhost:8001`
- Check `RAG_SERVICE_URL` in `mcp_server.py` (line 55)
- Test RAG service directly: `curl http://localhost:8001/collections`

## Environment Variables (Optional)

You can customize the server by modifying these variables in `mcp_server.py`:

- `TEMPLATE_PATH`: Path to Excel template
- `OUTPUT_DIR`: Directory for generated quotes
- `RAG_SERVICE_URL`: URL of RAG service
- `DO_ACCESS_KEY`, `DO_SECRET_KEY`: DigitalOcean Spaces credentials

## Next Steps

After connecting:

1. Test the quote generation tool
2. Test file search functionality (requires RAG service)
3. Integrate with your MCP client application
4. Monitor logs for any issues

For more information, see the main README.md file.

