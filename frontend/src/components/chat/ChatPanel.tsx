"use client";

import { useEffect, useRef, useState } from "react";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { postChat } from "@/lib/api-client";
import type { BusinessContext, ChatMessage } from "@/types/business";
import type { ChatResponse } from "@/types/market";

interface ChatPanelProps {
  context: BusinessContext;
  onResponse: (response: ChatResponse) => void;
}

export function ChatPanel({ context, onResponse }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "안녕하세요! 소상공인 금융 지원 에이전트입니다.\n상권 분석, 정책자금, 금융상품 추천을 도와드릴게요. 궁금한 점을 물어보세요.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const response = await postChat(text, context);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
      onResponse(response);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해 주세요.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-zinc-200 bg-zinc-50">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="text-sm text-zinc-400 animate-pulse">분석 중...</div>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} className="border-t border-zinc-200 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="예: 강남에서 카페 창업하려는데 정책자금 추천해줘"
            className="flex-1 rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
          >
            전송
          </button>
        </div>
      </form>
    </div>
  );
}
