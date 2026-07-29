"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "@/types/business";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[80%] rounded-2xl rounded-br-sm px-4 py-3 text-sm font-medium leading-relaxed text-black"
          style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-2.5">
      <div
        className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-black text-black shadow-md"
        style={{
          background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
          boxShadow: "0 2px 8px rgba(255,184,28,0.35)",
        }}
      >
        KB
      </div>
      <div
        className="max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-3 text-sm leading-relaxed"
        style={{
          background: "rgba(255,255,255,0.07)",
          border: "1px solid rgba(255,255,255,0.1)",
          color: "rgba(255,255,255,0.85)",
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => (
              <ul className="mb-2 list-disc space-y-1 pl-4">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="mb-2 list-decimal space-y-1 pl-4">{children}</ol>
            ),
            li: ({ children }) => (
              <li style={{ color: "rgba(255,255,255,0.7)" }}>{children}</li>
            ),
            strong: ({ children }) => (
              <strong className="font-bold text-white">{children}</strong>
            ),
            h3: ({ children }) => (
              <h3
                className="mb-1 mt-3 font-bold first:mt-0"
                style={{ color: "#FFB81C" }}
              >
                {children}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 className="mb-1 mt-2 font-semibold text-white first:mt-0">{children}</h4>
            ),
            code: ({ children }) => (
              <code
                className="rounded px-1.5 py-0.5 text-xs font-mono"
                style={{
                  background: "rgba(255,184,28,0.12)",
                  color: "#FFB81C",
                }}
              >
                {children}
              </code>
            ),
            hr: () => (
              <hr className="my-3" style={{ borderColor: "rgba(255,255,255,0.1)" }} />
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
