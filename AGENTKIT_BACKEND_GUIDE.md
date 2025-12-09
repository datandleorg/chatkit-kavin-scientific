# AgentKit Backend Implementation Guide

This guide explains how to build an AgentKit backend based on the [OpenAI ChatKit Advanced Samples customer-support example](https://github.com/openai/openai-chatkit-advanced-samples/tree/main/examples/customer-support), and how it differs from the current MCP server approach.

## Quick Summary

**What is AgentKit Backend?**
- A self-hosted backend that uses OpenAI's Agents SDK and ChatKit SDK
- Provides full control over agent behavior, tools, and conversation flow
- Integrates directly with ChatKit frontend without requiring OpenAI's hosted workflows

**Key Components:**
1. **ChatKitServer** - Handles ChatKit protocol communication
2. **Agent** - Manages AI reasoning and tool execution
3. **Tools** - Custom functions the agent can call (quote generation, document search, etc.)
4. **MemoryStore** - Manages conversation thread history

**Why Migrate from MCP?**
- Direct integration with ChatKit (no external workflow needed)
- Better control over agent behavior and context
- Built-in thread management
- Native streaming support
- Easier debugging and monitoring

## Architecture Comparison

### Current Architecture (MCP Server)
```
Frontend (ChatKit) → OpenAI Workflow → MCP Server (FastMCP) → RAG Service
```

### AgentKit Backend Architecture
```
Frontend (ChatKit) → AgentKit Backend (ChatKitServer) → Agent → Tools → RAG Service
```

## Key Differences

| Aspect | MCP Server | AgentKit Backend |
|--------|------------|------------------|
| **Protocol** | Model Context Protocol (MCP) | OpenAI Agents SDK |
| **Server Type** | FastMCP with SSE | ChatKitServer (custom implementation) |
| **Tool Definition** | `@mcp.tool()` decorator | `@function_tool` decorator |
| **Agent Management** | External (via OpenAI Workflow) | Internal (Agent class) |
| **Context** | Request-based | AgentContext with MemoryStore |
| **Thread Management** | External | Built-in with MemoryStore |

## AgentKit Backend Structure

Based on the customer-support example, an AgentKit backend has 4 layers:

1. **API Layer** - FastAPI for HTTP requests
2. **ChatKit Server** - Custom ChatKitServer managing ChatKit protocol
3. **Agent System** - Agent class with function tools (from OpenAI Agents SDK)
4. **Storage Layer** - MemoryStore for thread history

## Implementation Steps

### Step 1: Install Dependencies

```bash
# Core dependencies
pip install openai-agents openai-chatkit fastapi uvicorn httpx python-dotenv

# Additional dependencies for your tools
pip install boto3 openpyxl
```

**Note**: The actual package names may vary. Check the official OpenAI repositories:
- [OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python)
- [OpenAI ChatKit Python SDK](https://github.com/openai/chatkit-python)

### Step 2: Project Structure

```
agentkit-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── chat.py              # FactAssistantServer implementation
│   ├── constants.py         # Agent configuration constants
│   ├── tools/               # Agent tools
│   │   ├── __init__.py
│   │   ├── quote_tools.py   # Quote generation tools
│   │   └── search_tools.py  # RAG search tools
│   └── storage/
│       ├── __init__.py
│       └── memory_store.py  # Thread history storage
└── requirements.txt
```

### Step 3: Create Constants File

```python
# app/constants.py
MODEL = "gpt-4o-mini"  # or "gpt-4o" for better performance

INSTRUCTIONS = """You are a helpful assistant for Kavin Scientific, a chemical products company.
You can help users with:
1. Generating quotes for chemical products
2. Searching through company documents
3. Answering questions about products and services

Always be professional and helpful. When generating quotes, ensure all product details are accurate.
When searching documents, provide relevant excerpts with context."""

AGENT_NAME = "Kavin Scientific Assistant"
```

### Step 4: Create Agent Tools

```python
# app/tools/quote_tools.py
from agents import function_tool
from typing import List, Dict, Any
import httpx
import boto3
import os
from xml_quote_generator import XMLQuoteGenerator

# Configuration
TEMPLATE_PATH = os.getenv("TEMPLATE_PATH", "./quote.xlsx")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./")
DO_ACCESS_KEY = os.getenv("DO_ACCESS_KEY")
DO_SECRET_KEY = os.getenv("DO_SECRET_KEY")
DO_SPACE_NAME = os.getenv("DO_SPACE_NAME", "optimus")
DO_REGION = os.getenv("DO_REGION", "ams3")
DO_ENDPOINT = os.getenv("DO_ENDPOINT", "ams3.digitaloceanspaces.com")

def upload_to_do_spaces(file_path: str, file_name: str) -> str:
    """Upload file to DigitalOcean Spaces and return public URL"""
    session = boto3.session.Session()
    s3_client = session.client(
        's3',
        region_name=DO_REGION,
        endpoint_url=f'https://{DO_ENDPOINT}',
        aws_access_key_id=DO_ACCESS_KEY,
        aws_secret_access_key=DO_SECRET_KEY
    )
    
    s3_client.upload_file(
        file_path,
        DO_SPACE_NAME,
        file_name,
        ExtraArgs={'ACL': 'public-read'}
    )
    
    return f"https://{DO_SPACE_NAME}.{DO_ENDPOINT}/{file_name}"

@function_tool
def generate_quote_for_products(
    products: List[Dict[str, Any]],
    file_name: str
) -> str:
    """
    Generate a quote in Excel format for a list of products.
    
    Args:
        products: List of product dictionaries with fields:
            - name: Product name
            - cas_number: CAS number
            - packing: Packing information
            - price: Product price
            - part: Part number
            - hs_code: HS code
            - tax: Tax rate percentage
        file_name: Desired filename for the generated quote
    
    Returns:
        Success message with file path and public URL
    """
    # Validation
    if not products:
        return "Error: Products list cannot be empty"
    if not file_name:
        return "Error: File name cannot be empty"
    
    required_fields = ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
    for i, product in enumerate(products):
        missing = [f for f in required_fields if f not in product]
        if missing:
            return f"Error: Product {i+1} missing required fields: {missing}"
    
    if not os.path.exists(TEMPLATE_PATH):
        return f"Error: Template file not found: {TEMPLATE_PATH}"
    
    try:
        # Generate quote
        generator = XMLQuoteGenerator(TEMPLATE_PATH)
        output_path = generator.generate_quote(products, file_name)
        
        # Upload to DigitalOcean Spaces
        if not file_name.endswith('.xlsx'):
            file_name += '.xlsx'
        
        public_url = upload_to_do_spaces(output_path, file_name)
        
        # Calculate total
        total_amt = 0.0
        for product in products:
            price = float(product.get('price', 0))
            quantity = float(product.get('quantity', 1))
            discount = float(product.get('discount', 0))
            tax = float(product.get('tax', 0))
            
            discounted_rate = price * (1 - discount / 100)
            amount = discounted_rate * quantity
            tax_amount = amount * (tax / 100)
            total_amt += amount + tax_amount
        
        return (
            f"✅ Quote generated successfully!\n"
            f"📁 File: {output_path}\n"
            f"🌐 Public URL: {public_url}\n"
            f"📦 Products: {len(products)}\n"
            f"💰 Total Amount: ${total_amt:.2f}"
        )
    except Exception as e:
        return f"Error generating quote: {str(e)}"
```

```python
# app/tools/search_tools.py
from agents import function_tool
from typing import Optional
import httpx
import os

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8001")

@function_tool
def file_search(query: str, collection_name: str = "documents", limit: int = 10) -> str:
    """
    Search through uploaded documents using the RAG service.
    
    Args:
        query: The search query to find relevant content
        collection_name: Collection to search in (default: "documents")
        limit: Maximum number of results (default: 10)
    
    Returns:
        Formatted search results as text
    """
    try:
        search_data = {"query": query, "filters": {}}
        params = {
            "collection_name": collection_name,
            "limit": limit,
            "text_only": True,
            "llm_format": False
        }
        
        async def _search():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{RAG_SERVICE_URL}/search",
                    json=search_data,
                    params=params
                )
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('formatted_content') or result.get('text_content', '')
                    return content if content else f"No relevant content found for: '{query}'"
                else:
                    return f"Search failed: {response.text}"
        
        # Note: In actual implementation, you'd use asyncio.run() or handle async properly
        import asyncio
        return asyncio.run(_search())
        
    except Exception as e:
        return f"Error during file search: {str(e)}"

@function_tool
def get_document_info(document_id: str) -> str:
    """
    Get information about a specific document by its ID.
    
    Args:
        document_id: The unique identifier of the document
    
    Returns:
        Document information as formatted text
    """
    try:
        async def _get_info():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{RAG_SERVICE_URL}/documents/{document_id}")
                if response.status_code == 200:
                    doc_info = response.json()
                    return (
                        f"**Document Information**\n\n"
                        f"**ID:** {document_id}\n"
                        f"**Filename:** {doc_info.get('filename', 'Unknown')}\n"
                        f"**Chunks:** {doc_info.get('chunks_count', 0)}\n"
                        f"**Collection:** {doc_info.get('collection_name', 'Unknown')}"
                    )
                elif response.status_code == 404:
                    return f"Document not found: {document_id}"
                else:
                    return f"Error: {response.text}"
        
        import asyncio
        return asyncio.run(_get_info())
    except Exception as e:
        return f"Error getting document information: {str(e)}"

@function_tool
def list_collections() -> str:
    """
    List all available document collections in the RAG service.
    
    Returns:
        List of collections as formatted text
    """
    try:
        async def _list():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{RAG_SERVICE_URL}/collections")
                if response.status_code == 200:
                    collections_data = response.json()
                    collections = collections_data.get('collections', [])
                    if collections:
                        return "**Available Collections:**\n\n" + "\n".join(f"- {col}" for col in collections)
                    else:
                        return "No collections found. Upload some documents first."
                else:
                    return f"Error: {response.text}"
        
        import asyncio
        return asyncio.run(_list())
    except Exception as e:
        return f"Error listing collections: {str(e)}"
```

### Step 5: Create Memory Store

```python
# app/storage/memory_store.py
from typing import Dict, List, Optional
from agents import MemoryStore, ThreadMessage

class SimpleMemoryStore(MemoryStore):
    """Simple in-memory storage for thread history"""
    
    def __init__(self):
        self._threads: Dict[str, List[ThreadMessage]] = {}
    
    async def get_thread_messages(self, thread_id: str) -> List[ThreadMessage]:
        """Retrieve messages for a thread"""
        return self._threads.get(thread_id, [])
    
    async def add_thread_message(self, thread_id: str, message: ThreadMessage) -> None:
        """Add a message to a thread"""
        if thread_id not in self._threads:
            self._threads[thread_id] = []
        self._threads[thread_id].append(message)
    
    async def clear_thread(self, thread_id: str) -> None:
        """Clear all messages for a thread"""
        if thread_id in self._threads:
            del self._threads[thread_id]
```

### Step 6: Create ChatKit Server with Agent Integration

```python
# app/chat.py
from typing import AsyncIterator, Optional
from agents import Agent, AgentContext, function_tool
from openai_chatkit.server import ChatKitServer, stream_agent_response, simple_to_agent_input
from openai_chatkit.types import (
    ThreadMetadata, 
    UserMessageItem, 
    ThreadStreamEvent,
    ThreadMessage  # May be in a different module - check SDK docs
)
from app.constants import MODEL, INSTRUCTIONS, AGENT_NAME
from app.tools.quote_tools import generate_quote_for_products
from app.tools.search_tools import file_search, get_document_info, list_collections
from app.storage.memory_store import SimpleMemoryStore

# Initialize memory store
memory_store = SimpleMemoryStore()

# Create agent with tools
agent = Agent(
    name=AGENT_NAME,
    model=MODEL,
    instructions=INSTRUCTIONS,
    tools=[
        generate_quote_for_products,
        file_search,
        get_document_info,
        list_collections,
    ],
)

# Create custom ChatKit server that integrates with Agent
class KavinScientificServer(ChatKitServer):
    """ChatKit server for Kavin Scientific with Agent integration"""
    
    def __init__(self, agent: Agent, memory_store: SimpleMemoryStore):
        self.agent = agent
        self.memory_store = memory_store
        super().__init__()
    
    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Handle incoming messages and stream responses using the agent"""
        if input_user_message is None:
            return
        
        # Store user message in memory (adjust based on actual SDK structure)
        # The exact structure may vary - check the SDK documentation
        # await self.memory_store.add_thread_message(
        #     thread.id,
        #     {"role": "user", "content": input_user_message.content}
        # )
        
        # Convert ChatKit thread items to Agent SDK input
        agent_input = await simple_to_agent_input(thread.items)
        
        # Run the agent and stream responses
        response_stream = self.agent.run_stream(agent_input)
        
        # Convert agent responses back to ChatKit events
        async for event in stream_agent_response(response_stream, thread.id):
            # Store assistant messages in memory (adjust based on actual SDK structure)
            # if event.type == "message" and event.role == "assistant":
            #     await self.memory_store.add_thread_message(
            #         thread.id,
            #         {"role": "assistant", "content": event.content}
            #     )
            yield event

# Create server instance
server = KavinScientificServer(agent=agent, memory_store=memory_store)
```

### Step 7: Create FastAPI App

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from openai_chatkit.server import StreamingResult, NonStreamingResult
from app.chat import server

app = FastAPI(title="Kavin Scientific AgentKit Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint that processes requests"""
    body = await request.body()
    result = await server.process(body, {})
    
    if isinstance(result, StreamingResult):
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    return Response(
        content=result.json,
        media_type="application/json"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "agentkit-backend"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Kavin Scientific AgentKit Backend",
        "endpoints": {
            "health": "/health",
            "chatkit": "/chatkit",
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
```

### Step 8: Environment Configuration

```bash
# .env
OPENAI_API_KEY=your_openai_api_key_here
TEMPLATE_PATH=./quote.xlsx
OUTPUT_DIR=./
RAG_SERVICE_URL=http://localhost:8001
DO_ACCESS_KEY=your_do_access_key
DO_SECRET_KEY=your_do_secret_key
DO_SPACE_NAME=optimus
DO_REGION=ams3
DO_ENDPOINT=ams3.digitaloceanspaces.com
```

## Integration with Frontend

### Update Frontend Configuration

The frontend needs to connect to your AgentKit backend instead of using OpenAI's hosted workflow. Update `frontend/app/api/create-session/route.ts`:

```typescript
// Option 1: Use your own backend for session creation
const apiBase = process.env.CHATKIT_API_BASE ?? "http://localhost:8005/chatkit";
const url = `${apiBase}/sessions`;

// Option 2: Keep using OpenAI's API but configure workflow to use your backend
// The workflow in OpenAI Agent Builder should be configured to call your backend
```

## Key Benefits of AgentKit Backend

1. **Full Control**: Complete control over agent behavior and tool execution
2. **Custom Context**: Ability to add custom context and state management
3. **Thread Management**: Built-in thread history with MemoryStore
4. **Streaming**: Native support for streaming responses
5. **Tool Integration**: Direct integration of tools without external protocols
6. **Debugging**: Easier to debug and monitor agent behavior

## Migration Path from MCP

1. **Keep RAG Service**: The RAG service can remain unchanged
2. **Replace MCP Server**: Replace `mcp/mcp_server.py` with AgentKit backend
3. **Update Tools**: Convert `@mcp.tool()` to `@function_tool`
4. **Update Frontend**: Configure frontend to use AgentKit backend
5. **Test Integration**: Ensure all tools work correctly

## Testing

```bash
# Start RAG service
cd rag-service
python main.py

# Start AgentKit backend
cd agentkit-backend
python -m app.main

# Test health endpoint
curl http://localhost:8005/health

# Test ChatKit endpoint
curl http://localhost:8005/chatkit
```

## Important Notes

1. **SDK Availability**: The exact package names and APIs may vary. Always refer to the official documentation:
   - Check [OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python) for the latest API
   - Check [OpenAI ChatKit Python SDK](https://github.com/openai/chatkit-python) for ChatKit server implementation
   - The customer-support example in the advanced samples repository is the best reference

2. **FactAssistantServer**: In the customer-support example, `FactAssistantServer` is a custom class that extends `ChatKitServer`. You'll need to implement a similar pattern for your use case.

3. **Async Handling**: Make sure to properly handle async operations, especially when calling the RAG service from tools.

4. **Error Handling**: Add comprehensive error handling for tool failures, network issues, and agent errors.

## References

- [OpenAI ChatKit Advanced Samples](https://github.com/openai/openai-chatkit-advanced-samples)
- [Customer Support Example](https://github.com/openai/openai-chatkit-advanced-samples/tree/main/examples/customer-support)
- [OpenAI Agents SDK Documentation](https://platform.openai.com/docs/guides/agents-sdk)
- [OpenAI Agents Python SDK GitHub](https://github.com/openai/openai-agents-python)
- [OpenAI ChatKit Python SDK](https://github.com/openai/chatkit-python)
