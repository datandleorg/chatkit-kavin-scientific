# MCP Location in Unified Backend

## Answer: MCP is NOT in unified-backend - it's separate!

**MCP Location:** `mcp/` directory (separate from unified-backend, as per plan)

**Unified Backend Reference:** `unified-backend/app/chatkit/agent.py` references it externally

## Structure

```
project-root/
├── unified-backend/              # Unified backend service
│   └── app/
│       └── chatkit/
│           └── agent.py          # References MCP externally via path
│
└── mcp/                          # MCP server (SEPARATE - not moved!)
    ├── mcp_server_stdio.py       # Stdio server (used by agent)
    ├── mcp_server.py             # HTTP server  
    └── ...other MCP files
```

## How Unified Backend Accesses MCP

**File:** `unified-backend/app/chatkit/agent.py`

The agent creates a subprocess that runs the external MCP server:

```python
# Get path from environment variable (set in docker-compose)
MCP_BASE_DIR = os.getenv("MCP_BASE_DIR")  # /app/mcp in Docker

if MCP_BASE_DIR:
    MCP_SERVER_SCRIPT = Path(MCP_BASE_DIR) / "mcp_server_stdio.py"
else:
    # Local development: goes up to project root, then into mcp/
    BASE_DIR = Path(__file__).parent.parent.parent
    MCP_SERVER_SCRIPT = BASE_DIR / "mcp" / "mcp_server_stdio.py"

# Creates subprocess to run EXTERNAL MCP server
return MCPServerStdio(
    name="Kavin Scientific MCP Server",
    params={
        "command": PYTHON_EXECUTABLE,
        "args": [str(MCP_SERVER_SCRIPT)],  # External path!
        "env": mcp_env,
    },
)
```

## Docker Configuration

**In docker-compose.yml:**
- MCP directory is **mounted** into container: `./mcp:/app/mcp:ro`
- Environment variable set: `MCP_BASE_DIR=/app/mcp`
- Agent finds MCP at this mounted path

## Summary

✅ **MCP stays in `mcp/` directory** (separate, as per plan)  
✅ **Unified backend references it externally** via path  
✅ **MCP is mounted in Docker** at `/app/mcp`  
✅ **Agent creates subprocess** to run external MCP server  

**This matches our plan:** MCP remains separate, not moved into unified-backend.
