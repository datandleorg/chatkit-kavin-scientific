# ChatKit Kavin Scientific - Setup Guide

This guide explains how to run both the **MCP (Model Context Protocol) Server** and **RAG Service** together.

## Architecture Overview

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   MCP Server    │────────▶│   RAG Service   │────────▶│    MongoDB      │
│   Port: 8005    │         │   Port: 8001    │         │   Port: 27017   │
│                 │         │                 │         │                 │
│ - Quote Gen     │         │ - Document      │         │ - Vector Store  │
│ - File Search   │         │   Ingestion     │         │ - Text Search   │
└─────────────────┘         │ - Hybrid Search │         └─────────────────┘
                            └─────────────────┘
```

## Prerequisites

1. **Python 3.8+** installed
2. **Docker Desktop** installed and running
   - For Windows: Requires WSL2 or Hyper-V enabled
   - Verify Docker is running: `docker ps`
3. **Git** (if cloning the repository)

## Quick Start

### Step 1: Install Dependencies

#### Install RAG Service Dependencies
```bash
cd rag-service
python -m pip install -r requirements.txt
```

#### Install MCP Server Dependencies
```bash
cd mcp
python -m pip install -r requirements.txt
python -m pip install fastapi uvicorn httpx
```

### Step 2: Start MongoDB

MongoDB is required for the RAG service. Start it using Docker Compose:

```bash
cd mcp
docker compose -f docker-compose.mongodb.yml up -d
```

**Verify MongoDB is running:**
```bash
docker ps
# Should show: mcp_mongodb container running on port 27017

# Or check port:
netstat -ano | findstr "27017"
```

**MongoDB Configuration:**
- **Host:** `localhost`
- **Port:** `27017`
- **Username:** `admin`
- **Password:** `password123`
- **Database:** `rag_db`
- **Connection String:** `mongodb://admin:password123@localhost:27017/rag_db?authSource=admin`

### Step 3: Start RAG Service

The RAG service must be started **before** the MCP server (since MCP depends on it).

```bash
cd rag-service
python main.py
```

The service will start on **port 8001** by default.

**Verify RAG Service is running:**
```bash
# Check if port is listening
netstat -ano | findstr "8001"

# Test health endpoint
curl http://localhost:8001/health
# Or visit in browser: http://localhost:8001/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "mongodb": {...},
  "services": {
    "document_processor": "ready",
    "vector_store": "ready",
    "hybrid_search": "ready"
  }
}
```

### Step 4: Start MCP Server

Once the RAG service is running, start the MCP server:

```bash
cd mcp
python mcp_server.py
```

The server will start on **port 8005** by default.

**Verify MCP Server is running:**
```bash
# Check if port is listening
netstat -ano | findstr "8005"

# Test endpoint (may return 404, which is normal)
curl http://localhost:8005/
```

## Service Endpoints

### RAG Service (Port 8001)

- **Health Check:** `http://localhost:8001/health`
- **API Docs:** `http://localhost:8001/docs`
- **Root:** `http://localhost:8001/`
- **Search:** `POST http://localhost:8001/search`
- **Ingest:** `POST http://localhost:8001/ingest`

### MCP Server (Port 8005)

- **Root:** `http://localhost:8005/`
- **SSE Endpoint:** `http://localhost:8005/messages/`
- **Tools Available:**
  - `generate_quote_for_products` - Generate Excel quotes
  - `file_search` - Search documents via RAG service
  - `get_document_info` - Get document metadata
  - `list_collections` - List available collections

## Running Services in Background

### Windows PowerShell

**Start RAG Service:**
```powershell
cd rag-service
Start-Process python -ArgumentList "main.py" -WindowStyle Hidden
```

**Start MCP Server:**
```powershell
cd mcp
Start-Process python -ArgumentList "mcp_server.py" -WindowStyle Hidden
```

### Linux/Mac

**Start RAG Service:**
```bash
cd rag-service
nohup python main.py > rag-service.log 2>&1 &
```

**Start MCP Server:**
```bash
cd mcp
nohup python mcp_server.py > mcp-server.log 2>&1 &
```

## Stopping Services

### Stop Python Services

**Windows:**
```powershell
# Find and kill processes on ports
$port8001 = netstat -ano | findstr ":8001" | findstr "LISTENING"
$port8005 = netstat -ano | findstr ":8005" | findstr "LISTENING"
if ($port8001) { $pid = ($port8001 -split '\s+')[-1]; Stop-Process -Id $pid -Force }
if ($port8005) { $pid = ($port8005 -split '\s+')[-1]; Stop-Process -Id $pid -Force }

# Or kill all Python processes
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force
```

**Linux/Mac:**
```bash
# Kill by port
lsof -ti:8001 | xargs kill -9
lsof -ti:8005 | xargs kill -9
```

### Stop MongoDB

```bash
cd mcp
docker compose -f docker-compose.mongodb.yml down
```

## Configuration

### RAG Service Configuration

Edit `rag-service/config.env`:
```env
MONGODB_CONNECTION_STRING=mongodb://admin:password123@localhost:27017/rag_db?authSource=admin
DATABASE_NAME=rag_db
PORT=8001
```

### MCP Server Configuration

Edit `mcp/mcp_server.py` to update:
- `TEMPLATE_PATH` - Path to Excel quote template
- `OUTPUT_DIR` - Directory for generated quotes
- `RAG_SERVICE_URL` - RAG service URL (default: `http://localhost:8001`)

**Note:** Update the template path for your system:
```python
# Windows example:
TEMPLATE_PATH = "C:\\Users\\ADMIN\\codebase\\chatkit-kavin-scientific\\mcp\\quote.xlsx"
OUTPUT_DIR = "C:\\Users\\ADMIN\\codebase\\chatkit-kavin-scientific\\mcp"

# Linux/Mac example:
TEMPLATE_PATH = "/path/to/chatkit-kavin-scientific/mcp/quote.xlsx"
OUTPUT_DIR = "/path/to/chatkit-kavin-scientific/mcp"
```

## Troubleshooting

### MongoDB Not Starting

**Issue:** Docker container fails to start
```bash
# Check Docker logs
docker logs mcp_mongodb

# Check if port 27017 is already in use
netstat -ano | findstr "27017"

# Restart MongoDB container
docker compose -f docker-compose.mongodb.yml restart
```

**Issue:** Virtualization not supported (Windows)
- Enable virtualization in BIOS
- Install WSL2: `wsl --install`
- Or use Hyper-V backend in Docker Desktop settings

### RAG Service Not Starting

**Issue:** Port 8001 already in use
```bash
# Find process using port 8001
netstat -ano | findstr ":8001"

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

**Issue:** Cannot connect to MongoDB
- Verify MongoDB is running: `docker ps`
- Check connection string in `rag-service/config.env`
- Test MongoDB connection: `docker exec -it mcp_mongodb mongosh -u admin -p password123`

**Issue:** Missing dependencies
```bash
cd rag-service
python -m pip install -r requirements.txt
```

### MCP Server Not Starting

**Issue:** Port 8005 already in use
```bash
# Find and kill process on port 8005
netstat -ano | findstr ":8005"
taskkill /PID <PID> /F
```

**Issue:** Cannot connect to RAG service
- Verify RAG service is running: `curl http://localhost:8001/health`
- Check `RAG_SERVICE_URL` in `mcp/mcp_server.py`
- Ensure RAG service starts before MCP server

**Issue:** Template file not found
- Ensure `quote.xlsx` exists in the MCP directory
- Update `TEMPLATE_PATH` in `mcp/mcp_server.py` with correct path

### Docker Issues

**Issue:** Docker command not found
- Ensure Docker Desktop is installed and running
- Restart terminal/PowerShell after installing Docker
- Add Docker to PATH if needed

**Issue:** Docker Compose not found
- Use `docker compose` (newer versions) instead of `docker-compose`
- Or install Docker Compose separately

## Verification Checklist

- [ ] Docker Desktop is running
- [ ] MongoDB container is running (`docker ps`)
- [ ] MongoDB is listening on port 27017
- [ ] RAG service is running on port 8001
- [ ] RAG service health check returns 200 OK
- [ ] MCP server is running on port 8005
- [ ] All services can communicate with each other

## Development

### View Logs

**RAG Service:**
- Check console output where service was started
- Or redirect to log file: `python main.py > rag-service.log 2>&1`

**MCP Server:**
- Check console output where service was started
- Or redirect to log file: `python mcp_server.py > mcp-server.log 2>&1`

**MongoDB:**
```bash
docker logs mcp_mongodb
docker logs -f mcp_mongodb  # Follow logs
```

### Restart Services

1. Stop all services (see "Stopping Services" section)
2. Start MongoDB: `docker compose -f docker-compose.mongodb.yml up -d`
3. Start RAG service: `cd rag-service && python main.py`
4. Start MCP server: `cd mcp && python mcp_server.py`

## Additional Resources

- **RAG Service README:** `rag-service/README.md`
- **MCP Server README:** `mcp/README.md`
- **MongoDB Docker Compose:** `mcp/docker-compose.mongodb.yml`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review service-specific README files
3. Check Docker and service logs
4. Verify all prerequisites are met

