import json
import uuid
import tempfile
import shutil
import aiofiles
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import (
    HOST,
    PORT,
    UPLOAD_DIR,
    MAX_FILE_SIZE_MB,
    ALLOWED_EXTENSIONS,
)
from agent import chat_graph, run_agent
from agent.graph import SYSTEM_PROMPT
from utils.xml_quote_generator import XMLQuoteGenerator
import db as db_service

TEMPLATE_PATH = Path(__file__).parent / "templates" / "quote.xlsx"

app = FastAPI(title="Chemical Procurement API")


@app.on_event("startup")
async def startup_db():
    await db_service.ensure_indexes()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict] = {}


class ChatStreamRequest(BaseModel):
    message: str
    session_id: str | None = None
    conversation_id: str | None = None
    history: list[dict] = []


class ConfirmChemicalsRequest(BaseModel):
    session_id: str
    chemical_list: list[str]


class ChemicalResult(BaseModel):
    chemical: str
    vendor: str
    price: str
    pack_size: str
    cas_number: str
    availability: str
    url: str


class ConfirmResultsRequest(BaseModel):
    session_id: str
    scraping_results: list[ChemicalResult]


class ExportQuoteRow(BaseModel):
    name: str = ""
    catalogNo: str = ""
    hsn: str = ""
    brand: str = ""
    unit: str = ""
    rate: float = 0
    discount: float = 0
    qty: float = 1
    gstPercent: float = 0


class ExportQuoteRequest(BaseModel):
    rows: list[ExportQuoteRow]
    file_name: str = "quote"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/conversations")
async def list_conversations():
    return await db_service.list_conversations()


@app.post("/conversations")
async def create_conversation():
    conv = await db_service.create_conversation("New conversation")
    return {"id": conv["_id"], "title": conv["title"], "updated_at": conv["updated_at"].isoformat()}


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    conv = await db_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return await db_service.get_messages(conversation_id)


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conv = await db_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db_service.delete_conversation(conversation_id)
    return {"ok": True}


@app.post("/export-quote")
async def export_quote(req: ExportQuoteRequest, background_tasks: BackgroundTasks):
    """Generate an XLSX quote using the template with images preserved."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(500, "Quote template not found on server")

    output_dir = tempfile.mkdtemp()
    try:
        products = []
        for row in req.rows:
            products.append({
                "name": row.name,
                "catalog_number": row.catalogNo,
                "hs_code": row.hsn,
                "brand": row.brand,
                "packing": row.unit,
                "price": row.rate,
                "discount": row.discount,
                "quantity": row.qty,
                "tax": row.gstPercent,
            })

        generator = XMLQuoteGenerator(str(TEMPLATE_PATH), output_dir)
        output_path = generator.generate_quote(products, req.file_name)

        background_tasks.add_task(shutil.rmtree, output_dir, True)

        return FileResponse(
            path=output_path,
            filename=Path(output_path).name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(500, f"Failed to generate quote: {e}")


@app.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest):
    """Stream chat responses through the LangGraph ReAct agent with tool calling."""

    conv_id = req.conversation_id
    if not conv_id:
        title = req.message[:80].strip() or "New conversation"
        conv = await db_service.create_conversation(title)
        conv_id = conv["_id"]

    await db_service.add_message(conv_id, "user", req.message)

    context = ""
    if req.session_id and req.session_id in sessions:
        session_data = sessions[req.session_id]
        if session_data.get("chemicals"):
            context = f"Chemicals in session: {', '.join(session_data['chemicals'])}"
        if session_data.get("scraping_results"):
            context += f"\nPrevious scraping results available for {len(session_data['scraping_results'])} items."

    db_msgs = await db_service.get_messages(conv_id)
    messages: list = [SystemMessage(content=SYSTEM_PROMPT + (f"\n\n{context}" if context else ""))]
    for msg in db_msgs:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant" and msg["content"]:
            messages.append(AIMessage(content=msg["content"]))

    if not any(isinstance(m, HumanMessage) for m in messages) or (
        messages and not isinstance(messages[-1], HumanMessage)
    ):
        messages.append(HumanMessage(content=req.message))

    all_tokens: list[str] = []
    pending_text: list[str] = []
    saved_blocks: list[dict] = []

    def flush_text():
        if pending_text:
            saved_blocks.append({"type": "text", "text": "".join(pending_text)})
            pending_text.clear()

    async def generate():
        try:
            yield f"data: {json.dumps({'conversation_id': conv_id})}\n\n"

            async for event in chat_graph.astream_events(
                {"messages": messages, "session_id": req.session_id or "", "context": context},
                version="v2",
            ):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        if isinstance(chunk.content, str):
                            all_tokens.append(chunk.content)
                            pending_text.append(chunk.content)
                            yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                        elif isinstance(chunk.content, list):
                            for block in chunk.content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    all_tokens.append(block["text"])
                                    pending_text.append(block["text"])
                                    yield f"data: {json.dumps({'token': block['text']})}\n\n"

                elif kind == "on_tool_start":
                    flush_text()
                    tool_name = event.get("name", "tool")
                    run_id = event.get("run_id", "")
                    tool_input = event.get("data", {}).get("input", {})
                    search_param = (
                        tool_input.get("chemical_name")
                        or tool_input.get("search_term")
                        or tool_input.get("item_code")
                        or tool_input.get("product_id")
                        or tool_input.get("product_url", "")
                    )
                    saved_blocks.append({
                        "type": "tool",
                        "toolCall": {"id": run_id, "name": tool_name, "input": search_param, "status": "calling"},
                    })
                    yield f"data: {json.dumps({'tool_start': {'name': tool_name, 'run_id': run_id, 'input': search_param}})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    run_id = event.get("run_id", "")
                    tool_output = event.get("data", {}).get("output")
                    output_str = str(tool_output) if tool_output else ""

                    if tool_name == "prepare_quote_table":
                        try:
                            content = output_str
                            if hasattr(tool_output, "content"):
                                content = tool_output.content
                            rows = json.loads(content)
                            saved_blocks[:] = [b for b in saved_blocks if not (b.get("type") == "tool" and b.get("toolCall", {}).get("name") == "prepare_quote_table")]
                            saved_blocks.append({"type": "table", "rows": rows})
                            yield f"data: {json.dumps({'table_data': {'rows': rows, 'run_id': run_id}})}\n\n"
                        except (json.JSONDecodeError, TypeError):
                            for b in saved_blocks:
                                if b.get("type") == "tool" and b.get("toolCall", {}).get("id") == run_id:
                                    b["toolCall"]["status"] = "done"
                                    b["toolCall"]["result"] = output_str[:500]
                                    break
                            yield f"data: {json.dumps({'tool_end': {'name': tool_name, 'run_id': run_id, 'output': output_str}})}\n\n"
                    else:
                        for b in saved_blocks:
                            if b.get("type") == "tool" and b.get("toolCall", {}).get("id") == run_id:
                                b["toolCall"]["status"] = "done"
                                b["toolCall"]["result"] = output_str[:500]
                                break
                        yield f"data: {json.dumps({'tool_end': {'name': tool_name, 'run_id': run_id, 'output': output_str}})}\n\n"

            flush_text()
            assistant_content = "".join(all_tokens)
            await db_service.add_message(conv_id, "assistant", assistant_content, saved_blocks or None)

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    file_paths: list[str] = []

    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {ext}")

        content = await f.read()
        if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"File too large: {f.filename}")

        dest = UPLOAD_DIR / f"{session_id}_{f.filename}"
        async with aiofiles.open(dest, "wb") as out:
            await out.write(content)
        file_paths.append(str(dest))

    result = await run_agent(
        step="extraction",
        session_id=session_id,
        file_paths=file_paths,
    )

    sessions[session_id] = {
        "file_paths": file_paths,
        "chemicals": result.get("chemical_list", []),
    }

    return {"session_id": session_id, "chemical_list": result.get("chemical_list", [])}


@app.post("/confirm-chemicals")
async def confirm_chemicals(req: ConfirmChemicalsRequest):
    if req.session_id not in sessions:
        raise HTTPException(404, "Session not found")

    sessions[req.session_id]["chemicals"] = req.chemical_list

    result = await run_agent(
        step="scraping",
        session_id=req.session_id,
        chemical_list=req.chemical_list,
    )

    sessions[req.session_id]["scraping_results"] = result.get("scraping_results", [])

    return {"scraping_results": result.get("scraping_results", [])}


@app.post("/confirm-results")
async def confirm_results(req: ConfirmResultsRequest):
    if req.session_id not in sessions:
        raise HTTPException(404, "Session not found")

    results_dicts = [r.model_dump() for r in req.scraping_results]
    sessions[req.session_id]["scraping_results"] = results_dicts

    result = await run_agent(
        step="finalization",
        session_id=req.session_id,
        scraping_results=results_dicts,
    )

    return {"final_report": result.get("final_report", "")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
