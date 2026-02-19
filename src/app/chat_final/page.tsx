import { ChatFinalMessage } from "@/components/chat_final/ChatFinalMessage";

type ApiMessage = {
  question_number: number | null;
  item_number: number | null;
  message: {
    role: "assistant";
    render: "markdown+math";
    content_markdown: string;
  };
};

export default async function ChatFinalPage() {
  const backendBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
  const extractedPath =
    process.env.NEXT_PUBLIC_CHAT_FINAL_EXTRACTED_PATH ||
    "e:/uaskstudents/reports/ollama_extracted_short_final.json";

  const url =
    `${backendBase}/api/chat_final/from_extracted?path=` + encodeURIComponent(extractedPath);
  const res = await fetch(url, { cache: "no-store" });

  if (!res.ok) {
    return <div className="p-6">Failed to load chat_final data.</div>;
  }

  const data = await res.json();
  const items: ApiMessage[] = Array.isArray(data?.items) ? data.items : [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Final Answers</h1>

      {items.map((it, idx) => (
        <div key={idx} className="rounded-xl border p-4 bg-white">
          <div className="text-xs opacity-60 mb-2">
            Q{it.question_number ?? "?"} / Item {it.item_number ?? "?"}
          </div>
          <ChatFinalMessage content={it.message?.content_markdown ?? ""} />
        </div>
      ))}
    </div>
  );
}

