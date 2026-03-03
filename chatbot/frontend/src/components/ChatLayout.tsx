import { useState } from 'react';
import ChatHeader from './ChatHeader';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import ConversationSidebar from './ConversationSidebar';
import { useChat } from '../hooks/useChat';

export default function ChatLayout() {
  const { messages, isStreaming, conversationId, sendMessage, stopStreaming, newChat, loadConversation } = useChat();
  const [historyOpen, setHistoryOpen] = useState(false);

  const handleSuggestionSelect = (text: string) => {
    sendMessage(text);
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
      />
      <ChatInput
        onSend={sendMessage}
        onStop={stopStreaming}
        disabled={isStreaming}
      />
    </div>
  );
}
