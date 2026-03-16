import { useEffect, useRef } from 'react';
import type { Message } from '../types';
import MessageBubble from './MessageBubble';
import SuggestionChips from './SuggestionChips';

interface ChatMessagesProps {
  messages: Message[];
  isStreaming: boolean;
  onSuggestionSelect: (text: string) => void;
  conversationId?: string | null;
}

export default function ChatMessages({ messages, isStreaming, onSuggestionSelect, conversationId }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-end justify-center pb-4 px-4 sm:px-6 lg:px-8">
        <SuggestionChips onSelect={onSuggestionSelect} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto py-6 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-full mx-auto flex flex-col gap-4">
        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
            conversationId={conversationId}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
