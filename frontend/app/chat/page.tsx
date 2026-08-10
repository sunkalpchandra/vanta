import type { Metadata } from "next";
import { ChatConsole } from "@/components/ChatConsole";

export const metadata: Metadata = {
  title: "chat — vanta",
  description: "Ask vanta a question and watch the agent pipeline deliberate live.",
};

export default function ChatPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Ask vanta — live agent reasoning</h1>
        <p className="mt-1 text-sm text-ink-2">
          Agent reports stream in as the pipeline deliberates. Every number comes from the
          deterministic quant pipeline; the prose narratives are optional LLM output.
        </p>
      </div>
      <ChatConsole />
    </div>
  );
}
