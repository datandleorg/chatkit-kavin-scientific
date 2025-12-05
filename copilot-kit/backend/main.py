from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import AsyncIterator, Dict, Any, Optional, List
import os
import json
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Copilot Kit Backend",
    description="LangGraph FastAPI backend with streaming support for Copilot Kit",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    streaming=True,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Define the state
class GraphState:
    messages: List[BaseMessage]
    
    def __init__(self, messages: List[BaseMessage] = None):
        self.messages = messages or []

def chatbot_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node that calls the LLM with the current messages"""
    messages = state.get("messages", [])
    
    # Convert messages to LangChain format if needed
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            if msg.get("role") == "user":
                formatted_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                formatted_messages.append(AIMessage(content=msg.get("content", "")))
        elif isinstance(msg, BaseMessage):
            formatted_messages.append(msg)
    
    # Get response from LLM
    response = llm.invoke(formatted_messages)
    
    return {
        "messages": add_messages(formatted_messages, [response])
    }

async def chatbot_node_stream(state: Dict[str, Any]) -> AsyncIterator[str]:
    """Streaming version of the chatbot node"""
    messages = state.get("messages", [])
    
    # Convert messages to LangChain format
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            if msg.get("role") == "user":
                formatted_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                formatted_messages.append(AIMessage(content=msg.get("content", "")))
        elif isinstance(msg, BaseMessage):
            formatted_messages.append(msg)
    
    # Stream response from LLM
    async for chunk in llm.astream(formatted_messages):
        if chunk.content:
            yield chunk.content

# Build the graph
workflow = StateGraph(dict)

# Add the chatbot node
workflow.add_node("chatbot", chatbot_node)

# Set entry point
workflow.set_entry_point("chatbot")

# Add edge to END
workflow.add_edge("chatbot", END)

# Compile the graph
memory = MemorySaver()
app_state = workflow.compile(checkpointer=memory)

# Request/Response models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    thread_id: str

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Copilot Kit Backend is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "copilot-kit-backend"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint"""
    try:
        config = {}
        if request.thread_id:
            config["configurable"] = {"thread_id": request.thread_id}
        
        # Convert messages to state format
        state = {"messages": request.messages}
        
        # Invoke the graph
        result = await app_state.ainvoke(state, config=config if config else None)
        
        # Get the last assistant message
        last_message = result["messages"][-1]
        if hasattr(last_message, "content"):
            content = last_message.content
        else:
            content = str(last_message)
        
        return ChatResponse(
            message=content,
            thread_id=request.thread_id or "default"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint"""
    async def event_generator() -> AsyncIterator[str]:
        try:
            config = {}
            thread_id = request.thread_id or "default"
            if request.thread_id:
                config["configurable"] = {"thread_id": thread_id}
            
            # Get the last user message
            user_messages = [msg for msg in request.messages if msg.get("role") == "user"]
            if not user_messages:
                yield 'data: {"type":"error","error":{"message":"No user message found"}}\n\n'
                return
            
            last_user_message = user_messages[-1]
            
            # Get conversation history
            history = request.messages[:-1] if len(request.messages) > 1 else []
            
            # Convert history to LangChain format
            formatted_messages = []
            for msg in history:
                if msg.get("role") == "user":
                    formatted_messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    formatted_messages.append(AIMessage(content=msg.get("content", "")))
            
            # Add current user message
            formatted_messages.append(HumanMessage(content=last_user_message.get("content", "")))
            
            # Stream the response
            async for chunk in llm.astream(formatted_messages):
                if chunk.content:
                    # Format for Copilot Kit compatibility
                    content = {
                        "type": "text",
                        "text": chunk.content
                    }
                    event = {
                        "type": "delta",
                        "delta": {
                            "role": "assistant",
                            "content": [content]
                        }
                    }
                    yield f"data: {json.dumps(event)}\n\n"
            
            # Send done event
            yield 'data: {"type":"done"}\n\n'
        
        except Exception as e:
            error_event = {
                "type": "error",
                "error": {"message": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return EventSourceResponse(event_generator())

# Copilot Kit specific endpoints
@app.post("/copilotkit/chat")
async def copilotkit_chat(request: ChatRequest):
    """Copilot Kit compatible chat endpoint"""
    return await chat(request)

@app.post("/copilotkit/chat/stream")
async def copilotkit_chat_stream(http_request: Request):
    """Copilot Kit compatible streaming endpoint"""
    # Parse the raw request body first
    try:
        request_data = await http_request.json()
    except Exception as e:
        async def error_stream() -> AsyncIterator[str]:
            yield f'data: {{"type":"error","error":{{"message":"Invalid JSON: {str(e)}"}}}}\n\n'
        return EventSourceResponse(error_stream())
    
    async def generate_stream() -> AsyncIterator[str]:
        try:
            # Handle GraphQL requests from Copilot Kit
            # Check if it's a GraphQL request
            if "query" in request_data or "operationName" in request_data:
                # Extract variables from GraphQL request
                variables = request_data.get("variables", {})
                data = variables.get("data", {})
                
                # Extract messages from Copilot Kit format
                copilot_messages = data.get("messages", [])
                thread_id = data.get("threadId") or "default"
                
                # Transform Copilot Kit messages to standard format
                messages = []
                system_message = None
                for copilot_msg in copilot_messages:
                    # Handle different message types
                    if "textMessage" in copilot_msg:
                        text_msg = copilot_msg["textMessage"]
                        role = text_msg.get("role", "user")
                        content = text_msg.get("content", "")
                        if role == "system":
                            # Store system message separately
                            system_message = content
                        else:
                            messages.append({
                                "role": role,
                                "content": content
                            })
                    elif "content" in copilot_msg:
                        # Already in standard format
                        role = copilot_msg.get("role", "user")
                        content = copilot_msg.get("content", "")
                        if role == "system":
                            system_message = content
                        else:
                            messages.append({
                                "role": role,
                                "content": content
                            })
                    elif "role" in copilot_msg:
                        # Extract content from various possible locations
                        role = copilot_msg.get("role", "user")
                        content = copilot_msg.get("content") or copilot_msg.get("text", "")
                        if role == "system":
                            system_message = content if isinstance(content, str) else str(content)
                        else:
                            messages.append({
                                "role": role,
                                "content": content if isinstance(content, str) else str(content)
                            })
            else:
                # Handle standard JSON format
                messages = request_data.get("messages", [])
                thread_id = request_data.get("thread_id") or request_data.get("threadId") or "default"
                system_message = None  # No system message in standard format
            
            # Ensure messages is a list
            if not isinstance(messages, list):
                yield 'data: {"type":"error","error":{"message":"Messages must be a list"}}\n\n'
                return
            
            if not messages:
                yield 'data: {"type":"error","error":{"message":"No messages provided"}}\n\n'
                return
            
            config = {}
            if thread_id and thread_id != "default":
                config["configurable"] = {"thread_id": thread_id}
            
            # Get the last user message (skip system messages)
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            if not user_messages:
                # If no user messages, check if there are any messages at all
                if not messages:
                    yield 'data: {"type":"error","error":{"message":"No user message found"}}\n\n'
                    return
                # If all messages were system messages, use the last message regardless
                if messages:
                    last_user_message = messages[-1]
                else:
                    yield 'data: {"type":"error","error":{"message":"No user message found"}}\n\n'
                    return
            else:
                last_user_message = user_messages[-1]
            
            # Get conversation history (all messages before the last one)
            history = messages[:-1] if len(messages) > 1 else []
            
            # Helper function to extract content from message
            def extract_content(msg: Dict[str, Any]) -> str:
                content = msg.get("content", "")
                # Handle different content formats: string, array of content parts
                if isinstance(content, list):
                    # Extract text from content array
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif "text" in part:
                                text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    return "".join(text_parts)
                elif isinstance(content, str):
                    return content
                else:
                    return str(content) if content else ""
            
            # Convert history to LangChain format
            formatted_messages = []
            
            # Add system message if available
            if system_message:
                formatted_messages.append(SystemMessage(content=system_message))
            
            for msg in history:
                content = extract_content(msg)
                if msg.get("role") == "user":
                    formatted_messages.append(HumanMessage(content=content))
                elif msg.get("role") == "assistant":
                    formatted_messages.append(AIMessage(content=content))
            
            # Add current user message
            user_content = extract_content(last_user_message)
            formatted_messages.append(HumanMessage(content=user_content))
            
            # Stream the response
            # Generate message ID for this response
            import time
            message_id = f"msg-{thread_id}-{int(time.time() * 1000)}"
            created_at = int(time.time() * 1000)
            
            # Track accumulated content for streaming
            accumulated_content = ""
            
            async for chunk in llm.astream(formatted_messages):
                if chunk.content:
                    chunk_text = chunk.content
                    accumulated_content += chunk_text
                    
                    # Stream content as accumulated text
                    # Send full message with accumulated content each time
                    graphql_response = {
                        "data": {
                            "generateCopilotResponse": {
                                "messages": [{
                                    "__typename": "TextMessageOutput",
                                    "id": message_id,
                                    "createdAt": created_at,
                                    "role": "assistant",
                                    "content": accumulated_content,  # Full accumulated content
                                    "parentMessageId": None
                                }]
                            }
                        }
                    }
                    yield f"data: {json.dumps(graphql_response)}\n\n"
            
            # Send final completion event
            if accumulated_content:
                completion_event = {
                    "data": {
                        "generateCopilotResponse": {
                            "status": {
                                "__typename": "SuccessResponseStatus",
                                "code": "SUCCESS"
                            }
                        }
                    }
                }
                yield f"data: {json.dumps(completion_event)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            logger.error(f"Error in copilotkit_chat_stream: {str(e)}")
            logger.error(traceback.format_exc())
            error_event = {
                "type": "error",
                "error": {"message": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return EventSourceResponse(generate_stream())

# Copilot Kit runtime endpoint - alternative endpoint format
@app.post("/copilotkit/runtime")
async def copilotkit_runtime(request: Dict[str, Any]):
    """Copilot Kit runtime endpoint - handles chat messages"""
    try:
        # Extract messages from request
        messages = request.get("messages", [])
        thread_id = request.get("thread_id")
        
        chat_request = ChatRequest(
            messages=messages,
            thread_id=thread_id
        )
        
        # Use the streaming endpoint
        return await copilotkit_chat_stream(chat_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

