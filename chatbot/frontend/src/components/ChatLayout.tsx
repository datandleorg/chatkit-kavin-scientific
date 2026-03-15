import { useState, useEffect } from 'react';
import ChatHeader from './ChatHeader';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import ConversationSidebar from './ConversationSidebar';
import { useChat, CONVERSATION_ID_PARAM } from '../hooks/useChat';

export default function ChatLayout() {
  const { messages, isStreaming, conversationId, sendMessage, stopStreaming, newChat, loadConversation, reasoning, setReasoning, model, setModel } = useChat();
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get(CONVERSATION_ID_PARAM);
    if (c) loadConversation(c);
  }, [loadConversation]);

  const handleSuggestionSelect = (text: string) => {
    sendMessage(text, undefined, undefined, undefined);
  };

  const handleSend = (text: string, files?: File[], modelParam?: string, reasoningParam?: boolean) => {
    sendMessage(text, files, modelParam, reasoningParam);
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)]">
      <ConversationSidebar
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        activeConversationId={conversationId}
        onSelectConversation={loadConversation}
        onNewChat={newChat}
      />

      <ChatHeader
        onToggleHistory={() => setHistoryOpen((v) => !v)}
        onNewChat={newChat}
      />
      <ChatMessages
        messages={messages}
        isStreaming={isStreaming}
        onSuggestionSelect={handleSuggestionSelect}
        conversationId={conversationId}
      />

      <ChatInput
        onSend={handleSend}
        onStop={stopStreaming}
        disabled={isStreaming}
        reasoning={reasoning}
        onReasoningChange={setReasoning}
        model={model}
        onModelChange={setModel}
      />
    </div>
  );
}
