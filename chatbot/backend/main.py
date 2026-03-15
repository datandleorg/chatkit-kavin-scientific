import json
import uuid
import base64
import tempfile
import shutil
import logging
import io
import time
import aiofiles
from pathlib import Path
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
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
    CLAUDE_MODEL,
)
from pricing import compute_cost as compute_usage_cost, get_allowed_models, is_allowed_model
from agent import chat_graph, run_agent
from agent.graph import SYSTEM_PROMPT
from utils.xml_quote_generator import XMLQuoteGenerator
import db as db_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chatbot")

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:
    _enc = None

TEMPLATE_PATH = Path(__file__).parent / "templates" / "quote.xlsx"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
VISION_MODEL = "claude-haiku-4-5-20251001"


def _sanitize_filename(name: str) -> str:
    """Return a safe filename (no path traversal, no empty)."""
    if not name or not name.strip():
        return "file"
    base = Path(name).name.strip()
    if not base:
        return "file"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    safe = "".join(c if c in allowed else "_" for c in base)
    return safe[:200] or "file"

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
    result = "\n\n".join(pages)
    logger.info("PDF extracted: %d pages, %d chars", len(reader.pages), len(result))
    return result


def _usage_from_anthropic_response(response) -> dict:
    """Build usage dict from Anthropic Message response (input_tokens, output_tokens, cache)."""
    usage = getattr(response, "usage", None)
    if not usage:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cache_tokens": 0}
    if isinstance(usage, dict):
        inp = usage.get("input_tokens", 0) or 0
        out = usage.get("output_tokens", 0) or 0
        total = usage.get("total_tokens") or (inp + out)
        details = usage.get("input_token_details") or {}
        cache = int(details.get("cache_read_input_tokens", 0) or 0) + int(details.get("cache_creation_input_tokens", 0) or 0)
    else:
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        total = getattr(usage, "total_tokens", None) or (inp + out)
        details = getattr(usage, "input_token_details", None) or {}
        if isinstance(details, dict):
            cache = int(details.get("cache_read_input_tokens", 0) or 0) + int(details.get("cache_creation_input_tokens", 0) or 0)
        else:
            cache = int(getattr(details, "cache_read_input_tokens", 0) or 0) + int(getattr(details, "cache_creation_input_tokens", 0) or 0)
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": total,
        "cache_tokens": cache,
    }


async def _extract_image_text(file_bytes: bytes, media_type: str) -> tuple[str, dict]:
    """Extract text from image via vision API. Returns (text, usage_dict)."""
    logger.info("Image extraction: model=%s, media_type=%s, size=%dKB", VISION_MODEL, media_type, len(file_bytes) // 1024)
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
    text = response.content[0].text
    usage_dict = _usage_from_anthropic_response(response)
    logger.info("Image extraction done: %d chars extracted", len(text))
    return text, usage_dict


async def _process_uploaded_files(files: list[UploadFile]) -> list[dict]:
    """Extract text from uploaded files. Returns list of {filename, text} dicts."""
    logger.info("Processing %d uploaded file(s)", len(files))
    results = []
    for f in files:
        ext = Path(f.filename or "file").suffix.lower()
        file_bytes = await f.read()
        size_kb = len(file_bytes) // 1024

        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.warning("File too large: %s (%dKB)", f.filename, size_kb)
            results.append({"filename": f.filename, "text": f"[File too large: {f.filename}]"})
            continue

        try:
            if ext in PDF_EXTENSIONS:
                logger.info("Extracting PDF: %s (%dKB)", f.filename, size_kb)
                text = _extract_pdf_text(file_bytes)
                results.append({"filename": f.filename, "text": text})
            elif ext in IMAGE_EXTENSIONS:
                logger.info("Extracting image: %s (%dKB)", f.filename, size_kb)
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".webp": "image/webp", ".gif": "image/gif"}
                media_type = mime_map.get(ext, "image/png")
                text = await _extract_image_text(file_bytes, media_type)
                results.append({"filename": f.filename, "text": text})
            else:
                logger.warning("Unsupported file type: %s (%s)", f.filename, ext)
                results.append({"filename": f.filename, "text": f"[Unsupported file type: {ext}]"})
        except Exception as e:
            logger.error("Extraction failed for %s: %s", f.filename, e)
            results.append({"filename": f.filename, "text": f"[Extraction failed: {e}]"})

    return results


async def _process_uploaded_files_from_bytes(
    files: list[dict],
) -> tuple[list[dict], dict | None]:
    """Extract text from in-memory file contents. Each item: {filename, content} (bytes).
    Returns (list of {filename, text}, extraction_usage or None). extraction_usage is summed over image calls only."""
    logger.info("Processing %d file(s) from bytes", len(files))
    results = []
    extraction_usage: dict = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_tokens": 0,
    }
    for item in files:
        filename = item.get("filename") or "file"
        file_bytes = item.get("content") or b""
        ext = Path(filename).suffix.lower()
        size_kb = len(file_bytes) // 1024

        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.warning("File too large: %s (%dKB)", filename, size_kb)
            results.append({"filename": filename, "text": f"[File too large: {filename}]"})
            continue

        try:
            if ext in PDF_EXTENSIONS:
                logger.info("Extracting PDF: %s (%dKB)", filename, size_kb)
                text = _extract_pdf_text(file_bytes)
                results.append({"filename": filename, "text": text})
            elif ext in IMAGE_EXTENSIONS:
                logger.info("Extracting image: %s (%dKB)", filename, size_kb)
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".webp": "image/webp", ".gif": "image/gif"}
                media_type = mime_map.get(ext, "image/png")
                text, usage = await _extract_image_text(file_bytes, media_type)
                results.append({"filename": filename, "text": text})
                extraction_usage["input_tokens"] += usage.get("input_tokens", 0)
                extraction_usage["output_tokens"] += usage.get("output_tokens", 0)
                extraction_usage["total_tokens"] += usage.get("total_tokens", 0)
                extraction_usage["cache_tokens"] += usage.get("cache_tokens", 0)
            else:
                logger.warning("Unsupported file type: %s (%s)", filename, ext)
                results.append({"filename": filename, "text": f"[Unsupported file type: {ext}]"})
        except Exception as e:
            logger.error("Extraction failed for %s: %s", filename, e)
            results.append({"filename": filename, "text": f"[Extraction failed: {e}]"})

    if extraction_usage["input_tokens"] == 0 and extraction_usage["output_tokens"] == 0:
        return results, None
    return results, extraction_usage


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
    conversation_id: str | None = None
    message_prompt: str | None = None


DEFAULT_CHAT_MODEL = "gpt-5-mini"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/models")
async def list_models():
    """Return allowed chat models (id, label, provider) from single source of truth."""
    return get_allowed_models()


@app.get("/uploads/{file_path:path}")
async def serve_upload(file_path: str):
    """Serve a stored upload. file_path is relative (e.g. conv_id/msg_id/filename); must stay under UPLOAD_DIR."""
    if not file_path or ".." in file_path or file_path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    resolved = (UPLOAD_DIR / file_path).resolve()
    try:
        resolved.relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        raise HTTPException(403, "Forbidden")
    if not resolved.is_file():
        raise HTTPException(404, "File not found")
    media_types = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
    }
    media_type = media_types.get(resolved.suffix.lower(), "application/octet-stream")
    return FileResponse(resolved, media_type=media_type)


@app.get("/conversations")
async def list_conversations():
    return await db_service.list_conversations()


@app.post("/conversations")
async def create_conversation():
    conv = await db_service.create_conversation("New conversation")
    return {"id": conv["_id"], "title": conv["title"], "updated_at": conv["updated_at"].isoformat()}


def _message_cost_usd(msg: dict) -> float:
    """Compute cost in USD for a message from its usage and extraction_usage (same logic as get_usage)."""
    cost = 0.0
    for usage_key in ("usage", "extraction_usage"):
        u = msg.get(usage_key)
        if not u:
            continue
        model_id = u.get("model_id") or "default"
        if model_id == "default":
            model_id = CLAUDE_MODEL
        cost += compute_usage_cost(
            u.get("input_tokens", 0),
            u.get("output_tokens", 0),
            u.get("cache_tokens", 0),
            model_id,
            use_reasoning=u.get("use_reasoning", False),
        )
    return round(cost, 6)


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    conv = await db_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = await db_service.get_messages(conversation_id)
    rate = await _get_usd_to_inr_rate()
    for m in messages:
        if m.get("usage") or m.get("extraction_usage"):
            m["cost_usd"] = _message_cost_usd(m)
        if m.get("cost_usd") is not None and rate is not None:
            m["cost_inr"] = round(m["cost_usd"] * rate, 2)
    return messages


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conv = await db_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db_service.delete_conversation(conversation_id)
    return {"ok": True}


def _rows_to_products(rows: list) -> list[dict]:
    products = []
    for row in rows:
        if isinstance(row, dict):
            products.append({
                "name": row.get("name", ""),
                "catalog_number": row.get("catalogNo") or row.get("catalog_no", ""),
                "hs_code": row.get("hsn", ""),
                "brand": row.get("brand", ""),
                "packing": row.get("unit", ""),
                "price": float(row.get("rate", 0)),
                "discount": float(row.get("discount", 0)),
                "quantity": float(row.get("qty", 1)),
                "tax": float(row.get("gstPercent") or row.get("gst_percent", 0)),
            })
        else:
            products.append({
                "name": getattr(row, "name", ""),
                "catalog_number": getattr(row, "catalogNo", ""),
                "hs_code": getattr(row, "hsn", ""),
                "brand": getattr(row, "brand", ""),
                "packing": getattr(row, "unit", ""),
                "price": float(getattr(row, "rate", 0)),
                "discount": float(getattr(row, "discount", 0)),
                "quantity": float(getattr(row, "qty", 1)),
                "tax": float(getattr(row, "gstPercent", 0)),
            })
    return products


_usd_to_inr_cache: tuple[float, float] | None = None  # (rate, timestamp)
_USD_INR_CACHE_TTL = 3600  # 1 hour


async def _get_usd_to_inr_rate() -> float | None:
    """Fetch current USD to INR rate from Frankfurter API. Cached for 1 hour."""
    global _usd_to_inr_cache
    now = time.time()
    if _usd_to_inr_cache is not None and (now - _usd_to_inr_cache[1]) < _USD_INR_CACHE_TTL:
        return _usd_to_inr_cache[0]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("https://api.frankfurter.app/latest?from=USD&to=INR")
            r.raise_for_status()
            out = r.json()
            rate = float(out.get("rates", {}).get("INR", 0))
            if rate > 0:
                _usd_to_inr_cache = (rate, now)
                return rate
    except Exception as e:
        logger.warning("USD to INR rate fetch failed: %s", e)
    return _usd_to_inr_cache[0] if _usd_to_inr_cache else None


@app.get("/usage")
async def get_usage():
    """Return token usage aggregates for dashboard (totals, by day, by_tool_calls, cost). Cost is computed per (model_id, use_reasoning) from usage_by_model."""
    data = await db_service.get_usage_aggregates()
    usage_by_model = data.get("usage_by_model") or []
    cost_usd = 0.0
    for bucket in usage_by_model:
        model_id = bucket.get("model_id") or "default"
        if model_id == "default":
            model_id = CLAUDE_MODEL
        cost_usd += compute_usage_cost(
            bucket.get("input_tokens", 0),
            bucket.get("output_tokens", 0),
            bucket.get("cache_tokens", 0),
            model_id,
            use_reasoning=bucket.get("use_reasoning", False),
        )
    data["cost"] = cost_usd
    rate = await _get_usd_to_inr_rate()
    if rate is not None:
        data["cost_inr"] = round(cost_usd * rate, 2)
        data["usd_to_inr_rate"] = rate
    else:
        data["cost_inr"] = None
        data["usd_to_inr_rate"] = None
    return data


@app.post("/export-quote")
async def export_quote(req: ExportQuoteRequest, background_tasks: BackgroundTasks):
    """Generate an XLSX quote using the template with images preserved. Saves quote with conversation_id."""
    if not TEMPLATE_PATH.exists():
        raise HTTPException(500, "Quote template not found on server")

    output_dir = tempfile.mkdtemp()
    try:
        products = _rows_to_products([r.model_dump() for r in req.rows])
        generator = XMLQuoteGenerator(str(TEMPLATE_PATH), output_dir)
        output_path = generator.generate_quote(products, req.file_name)

        await db_service.save_quote(
            req.conversation_id,
            req.file_name,
            [r.model_dump() for r in req.rows],
            message_prompt=req.message_prompt,
        )

        background_tasks.add_task(shutil.rmtree, output_dir, True)

        return FileResponse(
            path=output_path,
            filename=Path(output_path).name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(500, f"Failed to generate quote: {e}")


@app.get("/quotes")
async def list_quotes(limit: int = 50):
    """List recent saved quotes for download."""
    return await db_service.list_saved_quotes(limit=limit)


@app.get("/quotes/{quote_id}/download")
async def download_quote(quote_id: str, background_tasks: BackgroundTasks):
    """Regenerate and return the XLSX for a saved quote."""
    quote = await db_service.get_saved_quote(quote_id)
    if not quote:
        raise HTTPException(404, "Quote not found")
    if not TEMPLATE_PATH.exists():
        raise HTTPException(500, "Quote template not found on server")

    output_dir = tempfile.mkdtemp()
    products = _rows_to_products(quote.get("rows") or [])
    generator = XMLQuoteGenerator(str(TEMPLATE_PATH), output_dir)
    file_name = quote.get("file_name", "quote.xlsx")
    output_path = generator.generate_quote(products, file_name)
    background_tasks.add_task(shutil.rmtree, output_dir, True)
    return FileResponse(
        path=output_path,
        filename=Path(output_path).name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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


def _usage_from_message(msg) -> dict[str, int] | None:
    """Extract usage dict from an AIMessage/AIMessageChunk (usage_metadata + cache from input_token_details)."""
    meta = getattr(msg, "usage_metadata", None) if msg else None
    if not meta:
        return None
    inp = meta.get("input_tokens", 0) or 0
    out = meta.get("output_tokens", 0) or 0
    total = meta.get("total_tokens", 0) or (inp + out)
    details = meta.get("input_token_details") or {}
    cache = (details.get("cache_read") or 0) + (details.get("cache_creation") or 0)
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": total,
        "cache_tokens": cache,
    }


def _compress_assistant_content(content: str) -> str:
    """Restorable compression: truncate long assistant text but note it was truncated."""
    if len(content) <= MAX_ASSISTANT_CONTENT_LEN:
        return content
    return content[:MAX_ASSISTANT_CONTENT_LEN] + "\n\n[... response truncated for context length — full text stored in conversation history]"


async def _summarize_with_llm(msgs_to_summarize: list[dict]) -> str:
    """Use a fast LLM to produce an abstractive summary of older messages."""
    logger.info("Summarization: %d messages → model=%s", len(msgs_to_summarize), SUMMARIZATION_MODEL)
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    formatted = []
    for msg in msgs_to_summarize:
        role = msg.get("role", "user")
        content = (msg.get("content") or "")[:600]
        formatted.append(f"[{role}]: {content}")

    conversation_text = "\n".join(formatted[-40:])
    input_tokens = _count_tokens(conversation_text)
    logger.info("Summarization input: %d chars, ~%d tokens", len(conversation_text), input_tokens)

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
    summary = response.content[0].text
    logger.info("Summarization output: %d chars", len(summary))
    return summary


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
    model: str = Form(""),
    reasoning: str = Form("false"),
    reasoning_query: str | None = Query(None, alias="reasoning"),
    files: list[UploadFile] = File(default=[]),
):
    """Stream chat responses through the LangGraph ReAct agent with tool calling."""

    conv_id = conversation_id or ""
    sid = session_id or ""
    raw_model = model.strip() or None
    if raw_model and not is_allowed_model(raw_model):
        logger.warning("Chat stream: invalid model %r, falling back to %s", raw_model, DEFAULT_CHAT_MODEL)
        model_id = DEFAULT_CHAT_MODEL
    else:
        model_id = raw_model or DEFAULT_CHAT_MODEL
    reasoning_val = (reasoning_query or reasoning).strip().lower()
    use_reasoning = reasoning_val in ("true", "1", "yes")
    file_names = [f.filename for f in files if f.filename]
    logger.info("── CHAT STREAM START ── conv=%s, msg=%r, files=%s, use_reasoning=%s",
                conv_id[:8] if conv_id else "new", message[:80], file_names or "none", use_reasoning)

    if not conv_id:
        title = message[:80].strip() or "New conversation"
        conv = await db_service.create_conversation(title)
        conv_id = conv["_id"]
        logger.info("Created new conversation: %s", conv_id[:8])

    user_msg = await db_service.add_message(conv_id, "user", message)
    user_msg_id = user_msg["_id"]

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

    logger.info("Context: %d messages, %d tokens (threshold=%d, window=%d) → summarize=%s",
                len(db_msgs), total_tokens, TOKEN_THRESHOLD, RECENT_WINDOW, needs_summarization)

    if needs_summarization:
        conv_doc = await db_service.get_conversation(conv_id)
        if conv_doc and conv_doc.get("summary"):
            cached_count = conv_doc.get("summary_msg_count", 0)
            if cached_count >= len(db_msgs) - RECENT_WINDOW:
                cached_summary = conv_doc["summary"]
                logger.info("Using cached summary (covers %d msgs)", cached_count)
            else:
                logger.info("Cached summary stale (covers %d, need %d), will re-summarize",
                            cached_count, len(db_msgs) - RECENT_WINDOW)

    effective_message = message
    messages = _build_context(db_msgs, effective_message, context, cached_summary)
    logger.info("Built LLM context: %d messages to model", len(messages))

    all_tokens: list[str] = []
    pending_text: list[str] = []
    saved_blocks: list[dict] = []
    run_usage: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_tokens": 0,
    }

    def flush_text():
        if pending_text:
            saved_blocks.append({"type": "text", "text": "".join(pending_text)})
            pending_text.clear()

    tool_call_count = 0
    extraction_usage_for_turn: dict | None = None

    async def generate():
        nonlocal messages, effective_message, tool_call_count, extraction_usage_for_turn
        try:
            yield f"data: {json.dumps({'conversation_id': conv_id})}\n\n"

            if uploaded_files:
                logger.info("Starting file save and extraction for %d file(s)", len(uploaded_files))
                yield f"data: {json.dumps({'extracting': True})}\n\n"

                save_dir = UPLOAD_DIR / conv_id / user_msg_id
                save_dir.mkdir(parents=True, exist_ok=True)
                file_blocks: list[dict] = []
                attachments_list: list[str] = []
                files_with_content: list[dict] = []

                for f in uploaded_files:
                    content = await f.read()
                    filename = f.filename or "file"
                    safe_name = _sanitize_filename(filename)
                    stem = Path(safe_name).stem
                    suffix = Path(safe_name).suffix
                    dest = save_dir / safe_name
                    idx = 0
                    while dest.exists():
                        idx += 1
                        safe_name = f"{stem}_{idx}{suffix}"
                        dest = save_dir / safe_name
                    async with aiofiles.open(dest, "wb") as out:
                        await out.write(content)
                    rel_path = f"{conv_id}/{user_msg_id}/{dest.name}"
                    file_blocks.append({"type": "file", "filename": filename, "path": rel_path})
                    attachments_list.append(filename)
                    files_with_content.append({"filename": filename, "content": content})

                if file_blocks:
                    await db_service.update_message(user_msg_id, blocks=file_blocks, attachments=attachments_list)

                extractions, extraction_usage_raw = await _process_uploaded_files_from_bytes(files_with_content)
                if extraction_usage_raw:
                    extraction_usage_for_turn = {
                        **extraction_usage_raw,
                        "model_id": VISION_MODEL,
                        "use_reasoning": False,
                    }
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
                    logger.info("File context injected: %d chars from %d file(s)", len(file_context), len(extracted_parts))

                yield f"data: {json.dumps({'extracting': False})}\n\n"

            if needs_summarization and cached_summary is None:
                logger.info("Starting LLM summarization of %d older messages", len(db_msgs) - RECENT_WINDOW)
                yield f"data: {json.dumps({'summarizing': True})}\n\n"
                try:
                    old_msgs = db_msgs[:-RECENT_WINDOW]
                    summary_text = await _summarize_with_llm(old_msgs)
                    await db_service.update_conversation_summary(
                        conv_id, summary_text, len(old_msgs),
                    )
                    messages = _build_context(db_msgs, effective_message, context, summary_text)
                    logger.info("Summarization complete: %d chars, cached for %d msgs", len(summary_text), len(old_msgs))
                    yield f"data: {json.dumps({'summary': summary_text})}\n\n"
                except Exception as e:
                    logger.error("LLM summarization failed: %s", e)
                yield f"data: {json.dumps({'summarizing': False})}\n\n"

            logger.info("Starting agent loop (recursion_limit=200)")

            stream_state = {"messages": messages, "session_id": sid, "context": context, "use_reasoning": use_reasoning}
            if model_id:
                stream_state["model_id"] = model_id
            async for event in chat_graph.astream_events(
                stream_state,
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

                elif kind == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    u = _usage_from_message(output)
                    if u:
                        run_usage["input_tokens"] += u.get("input_tokens", 0)
                        run_usage["output_tokens"] += u.get("output_tokens", 0)
                        run_usage["total_tokens"] += u.get("total_tokens", 0)
                        run_usage["cache_tokens"] += u.get("cache_tokens", 0)

                elif kind == "on_tool_start":
                    flush_text()
                    tool_call_count += 1
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
                    logger.info("  TOOL #%d START  %-35s  args=%s", tool_call_count, tool_name, search_param or tool_input)
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
                    has_error = any(kw in output_str.lower() for kw in ("error", "failed", "timeout"))
                    status_label = "FAIL" if has_error else "OK"
                    logger.info("  TOOL    END    %-35s  status=%s  output_len=%d", tool_name, status_label, len(output_str))

                    if tool_name == "prepare_quote_table":
                        try:
                            content = output_str
                            if hasattr(tool_output, "content"):
                                content = tool_output.content
                            rows = json.loads(content)
                            saved_blocks[:] = [b for b in saved_blocks if not (b.get("type") == "tool" and b.get("toolCall", {}).get("name") == "prepare_quote_table")]
                            saved_blocks.append({"type": "table", "rows": rows})
                            logger.info("  Quote table generated: %d rows", len(rows))
                            try:
                                prompt_stored = effective_message[:2000] if len(effective_message) > 2000 else effective_message
                                await db_service.save_quote(
                                    conv_id,
                                    "quote.xlsx",
                                    rows,
                                    message_prompt=prompt_stored,
                                )
                                logger.info("  Quote auto-saved to DB (conv=%s)", conv_id[:8])
                            except Exception as save_err:
                                logger.warning("  Quote auto-save failed: %s", save_err)
                            yield f"data: {json.dumps({'table_data': {'rows': rows, 'run_id': run_id}})}\n\n"
                        except (json.JSONDecodeError, TypeError):
                            logger.warning("  Quote table JSON parse failed")
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
            usage_to_store = run_usage if any(run_usage.values()) else None
            if usage_to_store is not None:
                usage_to_store["use_reasoning"] = use_reasoning
                usage_to_store["model_id"] = model_id
            await db_service.add_message(
                conv_id, "assistant", assistant_content, saved_blocks or None,
                usage=usage_to_store, extraction_usage=extraction_usage_for_turn,
            )

            response_tokens = _count_tokens(assistant_content)
            logger.info(
                "── CHAT STREAM DONE ── conv=%s, tool_calls=%d, response_tokens=%d, blocks=%d, usage=%s",
                conv_id[:8], tool_call_count, response_tokens, len(saved_blocks), run_usage,
            )

            turn_cost_usd = 0.0
            if usage_to_store:
                mid = usage_to_store.get("model_id") or CLAUDE_MODEL
                turn_cost_usd += compute_usage_cost(
                    usage_to_store.get("input_tokens", 0),
                    usage_to_store.get("output_tokens", 0),
                    usage_to_store.get("cache_tokens", 0),
                    mid,
                    use_reasoning=usage_to_store.get("use_reasoning", False),
                )
            if extraction_usage_for_turn:
                mid = extraction_usage_for_turn.get("model_id") or CLAUDE_MODEL
                turn_cost_usd += compute_usage_cost(
                    extraction_usage_for_turn.get("input_tokens", 0),
                    extraction_usage_for_turn.get("output_tokens", 0),
                    extraction_usage_for_turn.get("cache_tokens", 0),
                    mid,
                    use_reasoning=False,
                )
            payload = {"usage": run_usage, "extraction_usage": extraction_usage_for_turn, "cost_usd": round(turn_cost_usd, 6)}
            rate = await _get_usd_to_inr_rate()
            if rate is not None:
                payload["cost_inr"] = round(turn_cost_usd * rate, 2)
            yield f"data: {json.dumps(payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("── CHAT STREAM ERROR ── conv=%s: %s", conv_id[:8], e, exc_info=True)
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
