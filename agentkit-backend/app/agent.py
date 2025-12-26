"""
Agent definition for Kavin Scientific ChatKit Backend
This uses MCP stdio server for tools instead of function tools
"""
from agents import Agent, ModelSettings
from agents.mcp import MCPServerStdio
from openai.types.shared.reasoning import Reasoning
from pathlib import Path
import os
import sys

# Get the path to the MCP stdio server script
# In Docker, MCP is mounted at /app/mcp, so we use environment variable or fallback to relative path
MCP_BASE_DIR = os.getenv("MCP_BASE_DIR")
if MCP_BASE_DIR:
    MCP_SERVER_SCRIPT = Path(MCP_BASE_DIR) / "mcp_server_stdio.py"
else:
    # Fallback: assume mcp is at ../mcp relative to agentkit-backend
    BASE_DIR = Path(__file__).parent.parent.parent
    MCP_SERVER_SCRIPT = BASE_DIR / "mcp" / "mcp_server_stdio.py"

# Python executable path
PYTHON_EXECUTABLE = sys.executable if hasattr(sys, 'executable') else "python3"

# Create MCP stdio server instance
# This will be used as a context manager in the chatkit_server
def create_mcp_server():
    """Create and return MCP stdio server instance"""
    # Get environment variables to pass to MCP subprocess
    mcp_env = os.environ.copy()
    
    # Ensure RAG_SERVICE_URL is set (use Docker service name in containers)
    # This is critical - the MCP server subprocess needs this to connect to RAG service
    rag_service_url = os.getenv("RAG_SERVICE_URL", "http://rag-service:8000")
    mcp_env["RAG_SERVICE_URL"] = rag_service_url
    
    # Pass other MCP-related environment variables
    for env_var in ["TEMPLATE_PATH", "OUTPUT_DIR", "DO_ACCESS_KEY", "DO_SECRET_KEY", 
                    "DO_SPACE_NAME", "DO_REGION", "DO_ENDPOINT", "OPENAI_API_KEY"]:
        if env_var in os.environ:
            mcp_env[env_var] = os.environ[env_var]
    
    # Log the RAG service URL being used (for debugging)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Creating MCP server with RAG_SERVICE_URL={rag_service_url}")
    
    return MCPServerStdio(
        name="Kavin Scientific MCP Server",
        params={
            "command": PYTHON_EXECUTABLE,
            "args": [str(MCP_SERVER_SCRIPT)],
            "env": mcp_env,  # Pass environment variables to subprocess
        },
        cache_tools_list=True,
    )

# Agent instructions
AGENT_INSTRUCTIONS = """You are a helpful assistant that generates chemical product quotations.

🧩 Core Behavior:

When the user asks to generate a quote, you must:

Search all requested products individually using file_search across the available product catalogs.

Then generate an Excel quote containing all the matched or mock data.

If the user uploads a list of products, do the same:

Search each product individually.

Use the results to build the Excel quote.

📄 Missing Data Handling:

If any column values (e.g., price, catalog number, or purity) are not available, use mock values (reasonable placeholders).

Inform the user clearly that mock values were used for those specific items.

⚗️ Catalog & Brand Mapping:

If a requested chemical/product is not found in any catalog, still include it as an entry in the final quote (with mock values).

Determine the brand name based on which catalog (citation) the product information came from:

Catalog File | Brand Name
SRL- PRICE LIST Excel_Version-2024-25.pdf | SRL
Hyma Pricelist 2025-2026 incl bio (1) (1).pdf | HYMA
SH - SEPT - 04-09-2025 (1).pdf | SH
ISOCHEM%20PRICE%20LIST%2008-05-2025%20(2).pdf | ISOCHEM
Phoenix Borosilicate and Consumables PL 25-26.pdf | Phoenix Science
SCIENCE HOUSE PRICE LIST 13-11-2025 | Science House

The brand represents where the product was fetched from.

Always match the brand name according to the catalog citation above.

🧾 Output:

Produce an Excel quote file containing:

Product name
Catalog number (or mock if missing)
Brand (determined by source file)
Pack size
Price
Remarks (if mock data was used)

Ensure the quote is neatly formatted, with headers and proper alignment.
"""

# Note: The agent will be created in chatkit_server.py with the MCP server
# This allows proper async context management

