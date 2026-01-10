# MCP Location Explanation

## Where is MCP?

**MCP is NOT inside unified-backend** - it remains **separate** in the `mcp/` directory, as per our plan.

## Structure

```
project-root/
├── unified-backend/          # Unified backend service
│   └── app/
│       └── chatkit/
│           └── agent.py      # References MCP EXTERNALLY
│
└── mcp/                      # MCP server (SEPARATE - not moved)
    ├── mcp_server_stdio.py   # Stdio server (used by agent)
    ├── mcp_server.py         # HTTP server
    └── ...other MCP files
```

## How Unified Backend References MCP

**Location:** `unified-backend/app/chatkit/agent.py`

The agent.py file **references** MCP externally:

```python
# Get MCP path from environment variable (set in docker-compose)
MCP_BASE_DIR = os.getenv("MCP_BASE_DIR")  # /app/mcp in Docker

if MCP_BASE_DIR:
    MCP_SERVER_SCRIPT = Path(MCP_BASE_DIR) / "mcp_server_stdio.py"
else:
    # Fallback for local development
    BASE_DIR = Path(__file__).parent.parent.parent  # Goes up to project root
    MCP_SERVER_SCRIPT = BASE_DIR / "mcp" / "mcp_server_stdio.py"  # Points to mcp/ dir

# Creates subprocess to run external MCP server
return MCPServerStdio(
    name="Kavin Scientific MCP Server",
    params={
        "command": PYTHON_EXECUTABLE,
        "args": [str(MCP_SERVER_SCRIPT)],  # External path to mcp/mcp_server_stdio.py
        "env": mcp_env,
    },
)
```

## Docker Configuration

**In docker-compose.yml:**
- MCP directory is **mounted** into the container at `/app/mcp` (read-only)
- Environment variable `MCP_BASE_DIR=/app/mcp` is set
- Agent finds MCP at this mounted path

## Summary

- ✅ **MCP Location:** `mcp/` directory (separate, not in unified-backend)
- ✅ **Reference:** `unified-backend/app/chatkit/agent.py` references it via path
- ✅ **Docker:** Mounted at `/app/mcp` via volume mount
- ✅ **This matches the plan:** MCP remains separate as designed

The unified backend does NOT contain MCP code - it only references it externally.

