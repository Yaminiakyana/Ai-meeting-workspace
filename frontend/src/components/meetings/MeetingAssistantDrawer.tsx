import { useState } from "react";
import {
  Bot,
  CornerDownLeft,
  Loader2,
  Play,
  Sparkles,
  User,
  X,
} from "lucide-react";
import type { AssistantMessage, Citation } from "../../api/meetings";
import { askMeetingAssistant } from "../../api/meetings";

interface MeetingAssistantDrawerProps {
  meetingId?: number;
  meetingTitle?: string;
  isOpen: boolean;
  onClose: () => void;
  onJumpToTime: (seconds: number) => void;
}

interface ChatMessage extends AssistantMessage {
  citations?: Citation[];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export const MeetingAssistantDrawer: React.FC<MeetingAssistantDrawerProps> = ({
  meetingId,
  meetingTitle,
  isOpen,
  onClose,
  onJumpToTime,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: meetingTitle
        ? `Hello! I'm your AI meeting assistant for "${meetingTitle}". Ask me anything about what was discussed, decisions, deadlines, or who said what.`
        : "Hello! I'm your AI meeting workspace assistant. You can ask me questions across all your meetings or specific topics.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const quickPrompts = [
    "What were the key decisions made?",
    "List all action items and owners",
    "What was the main topic discussed?",
    "Summarize speaker viewpoints",
  ];

  const handleSend = async (questionText?: string) => {
    const textToSend = questionText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: ChatMessage = { role: "user", content: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const historyToSend = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await askMeetingAssistant(textToSend, meetingId, historyToSend);

      const aiMsg: ChatMessage = {
        role: "assistant",
        content: res.answer,
        citations: res.citations,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an issue retrieving an answer. Please check that transcripts are processed.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-indigo-600 p-1.5 text-white shadow-xs">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              AI Meeting Assistant
            </h2>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {meetingTitle ? `Context: ${meetingTitle}` : "Cross-meeting RAG"}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200 cursor-pointer"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={index}
              className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
            >
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  isUser
                    ? "bg-indigo-600 text-white"
                    : "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300"
                }`}
              >
                {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
              </div>

              <div
                className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                  isUser
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Citations with jump-to-audio buttons */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 border-t border-slate-200/60 dark:border-slate-700 pt-2 text-[11px]">
                    <p className="font-semibold text-slate-600 dark:text-slate-400">References:</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {msg.citations.map((c, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => onJumpToTime(c.start_time)}
                          className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-white px-2 py-0.5 font-medium text-indigo-700 shadow-2xs transition hover:bg-indigo-50 dark:border-indigo-900/60 dark:bg-slate-700 dark:text-indigo-300 dark:hover:bg-slate-600 cursor-pointer"
                          title={`"${c.text}"`}
                        >
                          <Play className="h-2.5 w-2.5 fill-indigo-600 text-indigo-600 dark:fill-indigo-400 dark:text-indigo-400" />
                          {formatTime(c.start_time)} ({c.speaker || "Speaker"})
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300">
              <Bot className="h-3.5 w-3.5" />
            </div>
            <div className="flex items-center gap-2 rounded-2xl bg-slate-100 px-4 py-3 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600 dark:text-indigo-400" />
              Searching transcripts & generating answer...
            </div>
          </div>
        )}
      </div>

      {/* Suggested prompts */}
      {messages.length < 3 && (
        <div className="border-t border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-950/40">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Suggested questions
          </p>
          <div className="flex flex-wrap gap-1.5">
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(p)}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-700 hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 cursor-pointer"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-slate-100 dark:border-slate-800 p-3 bg-white dark:bg-slate-900">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            placeholder="Ask about this meeting..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
          >
            <CornerDownLeft className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
