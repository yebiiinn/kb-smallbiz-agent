"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { postChat } from "@/lib/api-client";
import type { BusinessContext, ChatMessage } from "@/types/business";
import type { ChatResponse } from "@/types/market";

interface ChatPanelProps {
  context: BusinessContext;
  onResponse: (response: ChatResponse) => void;
  onLoadingStart?: () => void;
}

const INITIAL_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "안녕하세요! **KB 소상공인 금융 지원 에이전트**입니다. 🏦\n\n상권 분석, 경기지표, 정책자금, KB 금융상품 추천까지 도와드릴게요.\n\n어떤 것이 궁금하신가요?",
};

function TypingIndicator() {
  return (
    <div className="flex justify-start gap-2.5">
      <div
        className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-black text-black shadow-md"
        style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
      >
        KB
      </div>
      <div
        className="rounded-2xl rounded-bl-sm px-4 py-3"
        style={{
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 rounded-full"
              style={{
                background: "#FFB81C",
                animation: "typingDot 1.2s ease-in-out infinite",
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
        </div>
      </div>
      <style>{`
        @keyframes typingDot {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

const PLACEHOLDER_EXAMPLES = [
  "강남에서 카페 창업하려는데 정책자금 추천해줘",
  "운영 중인 한식당에 맞는 KB 대출 상품 알려줘",
  "현재 상권 분위기랑 경기 상황이 어때?",
  "소상공인 지원 사업 중 지금 신청 가능한 거 뭐야?",
];

function newSessionId() {
  return typeof crypto !== "undefined"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

export function ChatPanel({ context, onResponse, onLoadingStart }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [lastFailedText, setLastFailedText] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * PLACEHOLDER_EXAMPLES.length));
  const sessionIdRef = useRef<string>(newSessionId());

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const resetChat = useCallback(() => {
    setMessages([INITIAL_MESSAGE]);
    setFollowUps([]);
    setInput("");
    setLastFailedText(null);
    sessionIdRef.current = newSessionId();
    inputRef.current?.focus();
  }, []);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    setInput("");
    setFollowUps([]);
    setLastFailedText(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    onLoadingStart?.();

    try {
      const response = await postChat(text, context, sessionIdRef.current);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
      onResponse(response);
      if (response.follow_up_questions?.length) {
        setFollowUps(response.follow_up_questions.slice(0, 3));
      }
    } catch {
      setLastFailedText(text);
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await sendMessage(input);
  }

  function handleFollowUp(q: string) {
    inputRef.current?.focus();
    sendMessage(q);
  }

  return (
    <div
      className="flex h-full flex-col rounded-2xl"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2.5 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
      >
        <div
          className="flex h-7 w-7 items-center justify-center rounded-lg text-[10px] font-black text-black"
          style={{
            background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
            boxShadow: "0 2px 8px rgba(255,184,28,0.4)",
          }}
        >
          KB
        </div>
        <span className="text-sm font-semibold text-white">AI 에이전트</span>
        <span className="ml-auto flex items-center gap-1.5 text-xs" style={{ color: "#4ADE80" }}>
          <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
          Online
        </span>
        <button
          type="button"
          onClick={resetChat}
          title="새 대화 시작"
          className="ml-2 rounded-lg px-2.5 py-1 text-xs transition-all hover:scale-105"
          style={{
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "rgba(255,255,255,0.45)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.8)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.25)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.45)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.1)";
          }}
        >
          새 대화
        </button>
      </div>

      {/* Messages */}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && <TypingIndicator />}

        {/* 에러 재시도 버튼 */}
        {lastFailedText && !loading && (
          <div className="flex justify-center">
            <button
              type="button"
              onClick={() => sendMessage(lastFailedText)}
              className="flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium transition-all hover:scale-105"
              style={{
                background: "rgba(255,184,28,0.1)",
                border: "1px solid rgba(255,184,28,0.3)",
                color: "#FFB81C",
              }}
            >
              ↺ 다시 시도
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Follow-up chips */}
      {followUps.length > 0 && !loading && (
        <div
          className="flex flex-wrap gap-2 px-4 py-3"
          style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
        >
          {followUps.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => handleFollowUp(q)}
              className="rounded-full border px-3 py-1.5 text-xs transition-all hover:scale-[1.02]"
              style={{
                background: "rgba(255,184,28,0.08)",
                borderColor: "rgba(255,184,28,0.2)",
                color: "rgba(255,255,255,0.65)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,184,28,0.15)";
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,184,28,0.4)";
                (e.currentTarget as HTMLButtonElement).style.color = "#FFB81C";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,184,28,0.08)";
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,184,28,0.2)";
                (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.65)";
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="p-4"
        style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
      >
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={PLACEHOLDER_EXAMPLES[placeholderIdx]}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
            style={{
              background: "rgba(255,255,255,0.07)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "white",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "rgba(255,184,28,0.5)";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(255,184,28,0.1)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-xl px-5 py-2.5 text-sm font-bold text-black transition-all hover:scale-105 disabled:opacity-40 disabled:hover:scale-100"
            style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
          >
            전송
          </button>
        </div>
      </form>
    </div>
  );
}
