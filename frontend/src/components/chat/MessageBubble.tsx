"use client";

import type { ChatMessage } from "@/types/business";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-amber-500 text-white"
            : "bg-white border border-zinc-200 text-zinc-800 shadow-sm"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
