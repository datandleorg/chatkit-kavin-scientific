import { NextResponse } from "next/server";
import { agent } from "@/agent/agent";

export const runtime = "edge";

const DEFAULT_CHATKIT_BASE = "https://api.openai.com";
const SESSION_COOKIE_NAME = "chatkit_session_id";

interface AgentRuntimeRequest {
  type: string;
  actionType?: string;
  payload?: Record<string, unknown>;
}

function getCookieValue(cookieHeader: string | null, name: string): string | null {
  if (!cookieHeader) {
    return null;
  }
  const cookies = cookieHeader.split(";");
  for (const cookie of cookies) {
    const [rawName, ...rest] = cookie.split("=");
    if (!rawName || rest.length === 0) { continue; }
    if (rawName.trim() === name) { return rest.join("=").trim(); }
  }
  return null;
}

export async function POST(req: Request): Promise<Response> {
  try {
    const body: AgentRuntimeRequest = await req.json();

    if (process.env.NODE_ENV !== "production") {
      console.info("[agent-runtime] Received request:", {
        type: body.type,
        actionType: body.actionType,
        payload: body.payload,
      });
    }

    // Handle widget actions
    if (body.type === "widget_action") {
      const actionType = body.actionType;
      const payload = body.payload || {};

      // Get session ID from cookie to stream events back to ChatKit
      const sessionId = getCookieValue(req.headers.get("cookie"), SESSION_COOKIE_NAME);

      // Handle specific action types
      if (actionType === "generate_quote_for_products" || actionType === "generate_quote_form_submit") {
        // Call the agent to process the request
        const result = await agent.respond({
          type: "generate_quote",
          payload: payload,
        });
        
        // Stream events back to ChatKit session
        if (sessionId) {
          const apiBase = process.env.CHATKIT_API_BASE ?? DEFAULT_CHATKIT_BASE;
          const openaiApiKey = process.env.OPENAI_API_KEY;
        
          if (!openaiApiKey) {
            console.error("[agent-runtime] Missing OPENAI_API_KEY");
            return NextResponse.json(
              { error: "Server configuration error" },
              { status: 500 }
            );
          }

          for await (const event of result.stream) {
            // Send event to ChatKit session
            await fetch(`${apiBase}/v1/chatkit/sessions/${sessionId}/events`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${openaiApiKey}`,
                "OpenAI-Beta": "chatkit_beta=v1",
              },
              body: JSON.stringify(event),
            });
          }
        }

        // Return success response
        return NextResponse.json({ 
          success: true,
          message: `Processing quote request for ${Object.keys(payload).length} items...`,
        });
      }

      // Handle other action types
      return NextResponse.json({
        success: true,
        message: `Action "${actionType}" received and processed.`,
      });
    }

    return NextResponse.json(
      { error: "Invalid request type" },
      { status: 400 }
    );
  } catch (error) {
    console.error("[agent-runtime] Error:", error);
    return NextResponse.json(
      { 
        error: "Internal server error",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

