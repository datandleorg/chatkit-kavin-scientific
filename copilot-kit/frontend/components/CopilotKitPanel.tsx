"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

export default function CopilotKitPanel() {
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      publicApiKey={undefined}
    >
      <CopilotSidebar
        instructions="You are a helpful AI assistant. You can answer questions and help with various tasks."
        defaultOpen={true}
        labels={{
          title: "Copilot Kit Assistant",
          initial: "Hi! I'm your AI assistant. How can I help you today?",
        }}
      >
        <div className="w-full max-w-4xl mx-auto p-8">
          <h1 className="text-4xl font-bold mb-4">Copilot Kit</h1>
          <p className="text-lg text-gray-600 dark:text-gray-400 mb-8">
            AI Assistant powered by Copilot Kit, LangGraph, and FastAPI
          </p>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <p className="text-gray-700 dark:text-gray-300">
              Open the sidebar to start chatting with the AI assistant.
              The assistant is powered by LangGraph and supports streaming responses.
            </p>
          </div>
        </div>
      </CopilotSidebar>
    </CopilotKit>
  );
}

