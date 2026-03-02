import base64
import anthropic
from pathlib import Path

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from agent.state import WorkflowState


async def extraction_node(state: WorkflowState) -> dict:
    """Extract chemical names from uploaded PDF/image files using Claude vision."""
    file_paths = state.get("file_paths", [])
    if not file_paths:
        return {"chemical_list": [], "error": "No files provided"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    content_blocks: list[dict] = []

    for fp in file_paths:
        path = Path(fp)
        if not path.exists():
            continue

        raw = path.read_bytes()
        b64 = base64.standard_b64encode(raw).decode("utf-8")
        ext = path.suffix.lower()

        if ext == ".pdf":
            content_blocks.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })
        elif ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            media_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_map[ext], "data": b64},
            })

    if not content_blocks:
        return {"chemical_list": [], "error": "No readable files found"}

    content_blocks.append({
        "type": "text",
        "text": (
            "Extract all chemical names from these documents. "
            "Return ONLY a JSON array of chemical name strings, no other text. "
            'Example: ["Formic Acid", "Sodium Chloride", "Methanol"]'
        ),
    })

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": content_blocks}],
        )

        import json
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        chemicals = json.loads(text)

        if isinstance(chemicals, list):
            return {"chemical_list": [str(c) for c in chemicals]}
        return {"chemical_list": [], "error": "Unexpected response format"}
    except Exception as e:
        return {"chemical_list": [], "error": str(e)}
