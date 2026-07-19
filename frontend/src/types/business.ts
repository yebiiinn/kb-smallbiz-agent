export type BusinessStage = "startup" | "operation" | "expansion";

export interface BusinessContext {
  region: string;
  industry: string;
  stage: BusinessStage;
  revenue?: number | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
