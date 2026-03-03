import json
import uuid
import base64
import tempfile
import shutil
import logging
import io
import aiofiles
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from anthropic import AsyncAnthropic
from PyPDF2 import PdfReader

from config import (
    HOST,
    PORT,
    UPLOAD_DIR,
    MAX_FILE_SIZE_MB,
    ALLOWED_EXTENSIONS,
    ANTHROPIC_API_KEY,
)
from agent import chat_graph, run_agent
from agent.graph import SYSTEM_PROMPT
from utils.xml_quote_generator import XMLQuoteGenerator
import db as db_service

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:
    _enc = None

TEMPLATE_PATH = Path(__file__).parent / "templates" / "quote.xlsx"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
VISION_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = (
    "Extract ALL text content from this image. It likely contains a product list, "
    "purchase order, or chemical inventory. Return the extracted text exactly as it "
    "appears, preserving table structure with | separators if present. "
    "Include product names, catalog numbers, quantities, brands, CAS numbers, "
    "and any other details you see."
)


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


async def _extract_image_text(file_bytes: bytes, media_type: str) -> str:
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
    response = await client.messages.create(
        model=VISION_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    )
    return response.content[0].text


async def _process_uploaded_files(files: list[UploadFile]) -> list[dict]:
    """Extract text from uploaded files. Returns list of {filename, text} dicts."""
    results = []
    for f in files:
        ext = Path(f.filename or "file").suffix.lower()
        file_bytes = await f.read()

        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            results.append({"filename": f.filename, "text": f"[File too large: {f.filename}]"})
            continue

        try:
            if ext in PDF_EXTENSIONS:
                text = _extract_pdf_text(file_bytes)
                results.append({"filename": f.filename, "text": text})
            elif ext in IMAGE_EXTENSIONS:
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".webp": "image/webp", ".gif": "image/gif"}
                media_type = mime_map.get(ext, "image/png")
                text = await _extract_image_text(file_bytes, media_type)
                results.append({"filename": f.filename, "text": text})
            else:
                results.append({"filename": f.filename, "text": f"[Unsupported file type: {ext}]"})
        except Exception as e:
            logger.warning(f"Failed to extract text from {f.filename}: {e}")
            results.append({"filename": f.filename, "text": f"[Extraction failed: {e}]"})

    return results

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


TOKEN_THRESHOLD = 30000
RECENT_WINDOW = 20
MAX_ASSISTANT_CONTENT_LEN = 3000
SUMMARIZATION_MODEL = "claude-haiku-4-5-20251001"


def _count_tokens(text: str) -> int:
    if _enc is not None:
        return len(_enc.encode(text, disallowed_special=()))
    return len(text) // 4


def _count_message_tokens(msgs: list[dict]) -> int:
    total = 0
    for msg in msgs:
        total += _count_tokens(msg.get("content") or "")
        total += 4
    return total


def _compress_assistant_content(content: str) -> str:
    """Restorable compression: truncate long assistant text but note it was truncated."""
    if len(content) <= MAX_ASSISTANT_CONTENT_LEN:
        return content
    return content[:MAX_ASSISTANT_CONTENT_LEN] + "\n\n[... response truncated for context length — full text stored in conversation history]"


async def _summarize_with_llm(msgs_to_summarize: list[dict]) -> str:
    """Use a fast LLM to produce an abstractive summary of older messages."""
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    formatted = []
    for msg in msgs_to_summarize:
        role = msg.get("role", "user")
        content = (msg.get("content") or "")[:600]
        formatted.append(f"[{role}]: {content}")

    conversation_text = "\n".join(formatted[-40:])

    response = await client.messages.create(
        model=SUMMARIZATION_MODEL,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": (
                "Summarize this conversation between a user and a chemical procurement assistant. "
                "Focus on: what chemicals were searched, which vendors had results, key findings "
                "(prices, availability, pack sizes), and any errors encountered. Be concise, "
                "use bullet points.\n\n" + conversation_text
            ),
        }],
    )
    return response.content[0].text


def _build_context(
    db_msgs: list[dict],
    current_message: str,
    session_context: str,
    summary: str | None = None,
) -> list:
    """
    Build the LLM message list applying context engineering principles:
    - Static system prompt prefix (KV-cache friendly)
    - Append-only message history from MongoDB
    - Restorable compression for long assistant messages
    - LLM summary for older messages when token count exceeds threshold
    - Keep errors in context for better recovery
    """
    system_parts = [SYSTEM_PROMPT]
    if session_context:
        system_parts.append(f"\n\n---\nSession context:\n{session_context}")

    if summary:
        db_msgs_to_use = db_msgs[-RECENT_WINDOW:] if len(db_msgs) > RECENT_WINDOW else db_msgs
        system_parts.append(f"\n\n---\nConversation summary (older messages):\n{summary}")
    else:
        db_msgs_to_use = db_msgs

    messages: list = [SystemMessage(content="".join(system_parts))]

    for msg in db_msgs_to_use:
        content = msg.get("content") or ""
        if msg["role"] == "user":
            messages.append(HumanMessage(content=content))
        elif msg["role"] == "assistant" and content:
            messages.append(AIMessage(content=_compress_assistant_content(content)))

    # Replace the last user message with current_message which may include
    # file-extracted content appended after the DB save
    replaced = False
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            messages[i] = HumanMessage(content=current_message)
            replaced = True
            break
    if not replaced:
        messages.append(HumanMessage(content=current_message))

    return messages


@app.post("/chat/stream")
async def chat_stream(
    message: str = Form(...),
    session_id: str = Form(""),
    conversation_id: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    """Stream chat responses through the LangGraph ReAct agent with tool calling."""

    conv_id = conversation_id or ""
    sid = session_id or ""
    if not conv_id:
        title = message[:80].strip() or "New conversation"
        conv = await db_service.create_conversation(title)
        conv_id = conv["_id"]

    await db_service.add_message(conv_id, "user", message)

    context = ""
    if sid and sid in sessions:
        session_data = sessions[sid]
        if session_data.get("chemicals"):
            context = f"Chemicals in session: {', '.join(session_data['chemicals'])}"
        if session_data.get("scraping_results"):
            context += f"\nPrevious scraping results available for {len(session_data['scraping_results'])} items."

    uploaded_files = [f for f in files if f.filename]

    db_msgs = await db_service.get_messages(conv_id)

    total_tokens = _count_message_tokens(db_msgs)
    needs_summarization = total_tokens > TOKEN_THRESHOLD and len(db_msgs) > RECENT_WINDOW
    cached_summary: str | None = None

    if needs_summarization:
        conv_doc = await db_service.get_conversation(conv_id)
        if conv_doc and conv_doc.get("summary"):
            cached_count = conv_doc.get("summary_msg_count", 0)
            if cached_count >= len(db_msgs) - RECENT_WINDOW:
                cached_summary = conv_doc["summary"]

    effective_message = message
    messages = _build_context(db_msgs, effective_message, context, cached_summary)

    all_tokens: list[str] = []
    pending_text: list[str] = []
    saved_blocks: list[dict] = []

    def flush_text():
        if pending_text:
            saved_blocks.append({"type": "text", "text": "".join(pending_text)})
            pending_text.clear()

    async def generate():
        nonlocal messages, effective_message
        try:
            yield f"data: {json.dumps({'conversation_id': conv_id})}\n\n"

            if uploaded_files:
                yield f"data: {json.dumps({'extracting': True})}\n\n"
                extractions = await _process_uploaded_files(uploaded_files)
                extracted_parts = []
                for ext in extractions:
                    yield f"data: {json.dumps({'file_extracted': {'filename': ext['filename'], 'preview': ext['text'][:200]}})}\n\n"
                    extracted_parts.append(f"--- Content from {ext['filename']} ---\n{ext['text']}")

                if extracted_parts:
                    file_context = "\n\n".join(extracted_parts)
                    effective_message = (
                        f"{message}\n\n"
                        f"[Attached file content — use this to identify products and search vendors]\n"
                        f"{file_context}"
                    )
                    messages = _build_context(db_msgs, effective_message, context, cached_summary)

                yield f"data: {json.dumps({'extracting': False})}\n\n"

            if needs_summarization and cached_summary is None:
                yield f"data: {json.dumps({'summarizing': True})}\n\n"
                try:
                    old_msgs = db_msgs[:-RECENT_WINDOW]
                    summary_text = await _summarize_with_llm(old_msgs)
                    await db_service.update_conversation_summary(
                        conv_id, summary_text, len(old_msgs),
                    )
                    messages = _build_context(db_msgs, effective_message, context, summary_text)
                    yield f"data: {json.dumps({'summary': summary_text})}\n\n"
                except Exception as e:
                    logger.warning(f"LLM summarization failed, proceeding without: {e}")
                yield f"data: {json.dumps({'summarizing': False})}\n\n"

            async for event in chat_graph.astream_events(
                {"messages": messages, "session_id": sid, "context": context},
                version="v2",
                config={"recursion_limit": 200},
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
                                if isinstance(block, dict):
                                    if block.get("type") == "thinking":
                                        thinking_text = block.get("thinking", "")
                                        if thinking_text:
                                            yield f"data: {json.dumps({'thinking': thinking_text})}\n\n"
                                    elif block.get("type") == "text":
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
