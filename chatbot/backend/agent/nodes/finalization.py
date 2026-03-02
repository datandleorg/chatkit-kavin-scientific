import json
import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from agent.state import WorkflowState


async def finalization_node(state: WorkflowState) -> dict:
    """Generate a final procurement comparison report from scraping results."""
    results = state.get("scraping_results", [])
    if not results:
        return {"final_report": "No scraping results to generate a report from."}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = (
        "Based on the following vendor search results for chemicals, "
        "generate a concise procurement comparison report. Include:\n"
        "1. A summary table comparing vendors for each chemical\n"
        "2. Best price recommendations\n"
        "3. Vendor notes (availability, shipping)\n"
        "4. Estimated total cost if prices are available\n\n"
        f"Results:\n{json.dumps(results, indent=2)}"
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"final_report": response.content[0].text}
    except Exception as e:
        return {"final_report": f"Error generating report: {e}"}
