# Copilot Kit Setup

This project contains a Copilot Kit frontend and a LangGraph FastAPI backend with streaming support.

## Project Structure

```
copilot-kit/
├── frontend/          # Next.js frontend with Copilot Kit
├── backend/           # FastAPI backend with LangGraph
└── README.md          # This file
```

## Prerequisites

- Node.js 18+ and npm
- Python 3.8+
- OpenAI API key

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd copilot-kit/backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

5. Run the backend server:
```bash
python main.py
```

The backend will run on `http://localhost:8002`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd copilot-kit/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env.local` file (optional, defaults to localhost:8002):
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8002
```

4. Run the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## Features

- **Streaming Support**: Real-time streaming responses from the backend
- **LangGraph Integration**: Backend powered by LangGraph for AI conversations
- **Copilot Kit UI**: Modern chat interface with Copilot Kit components
- **FastAPI Backend**: High-performance async backend with FastAPI
- **CORS Enabled**: Cross-origin requests enabled for development

## API Endpoints

### Backend Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health check
- `POST /chat` - Non-streaming chat endpoint
- `POST /chat/stream` - Streaming chat endpoint
- `POST /copilotkit/chat` - Copilot Kit compatible non-streaming endpoint
- `POST /copilotkit/chat/stream` - Copilot Kit compatible streaming endpoint
- `POST /copilotkit/runtime` - Runtime endpoint for Copilot Kit

### Frontend API Route

- `POST /api/copilotkit` - Proxies requests to the backend with streaming support

## Usage

1. Start the backend server first (port 8002)
2. Start the frontend development server (port 3000)
3. Open `http://localhost:3000` in your browser
4. The Copilot Kit sidebar will be open by default - start chatting!

## Development

### Backend Development

The backend uses:
- FastAPI for the web framework
- LangGraph for AI conversation orchestration
- LangChain for LLM integration
- OpenAI for the language model
- SSE (Server-Sent Events) for streaming

### Frontend Development

The frontend uses:
- Next.js 15 with App Router
- React 19
- Copilot Kit for the AI chat interface
- Tailwind CSS for styling

## Troubleshooting

1. **Connection Issues**: Make sure the backend is running on port 8002 before starting the frontend
2. **API Key Issues**: Ensure your OpenAI API key is set in the backend `.env` file
3. **CORS Issues**: The backend has CORS enabled for all origins - adjust if needed for production
4. **Streaming Issues**: Check browser console and backend logs for any errors

## License

Same as parent project

