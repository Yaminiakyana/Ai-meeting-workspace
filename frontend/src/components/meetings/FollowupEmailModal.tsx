import { useState } from "react";
import { Check, Copy, Loader2, Mail, Send, X } from "lucide-react";
import { generateFollowupEmail } from "../../api/meetings";

interface FollowupEmailModalProps {
  meetingId: number;
  isOpen: boolean;
  onClose: () => void;
}

export const FollowupEmailModal: React.FC<FollowupEmailModalProps> = ({
  meetingId,
  isOpen,
  onClose,
}) => {
  const [instructions, setInstructions] = useState("");
  const [loading, setLoading] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await generateFollowupEmail(meetingId, instructions || undefined);
      setSubject(res.subject);
      setBody(res.body);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to generate follow-up email");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    const fullText = `Subject: ${subject}\n\n${body}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl transition-colors">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-indigo-50 p-1.5 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
              <Mail className="h-5 w-5" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Generate Follow-Up Email
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200 cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/40 p-3 text-xs text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-700 dark:text-slate-300">
              Custom instructions (optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Keep it concise, emphasize marketing deadlines"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 dark:border-slate-300 dark:bg-white dark:text-black dark:placeholder:text-slate-500 dark:focus:border-indigo-500"
            />
          </div>

          {!body && (
            <div className="rounded-xl border border-dashed border-slate-200 dark:border-slate-800 py-8 text-center">
              <Mail className="mx-auto h-8 w-8 text-slate-300 dark:text-slate-600" />
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Generate a ready-to-send summary and action item email for your meeting attendees.
              </p>
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Drafting Email...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Generate Email Draft
                  </>
                )}
              </button>
            </div>
          )}

          {body && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Subject Line
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-900 dark:border-slate-300 dark:bg-white dark:text-black"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Email Body
                </label>
                <textarea
                  rows={10}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-3 text-xs leading-relaxed text-slate-900 font-mono dark:border-slate-300 dark:bg-white dark:text-black"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-6 py-4 rounded-b-2xl dark:border-slate-800 dark:bg-slate-950">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200/50 dark:text-slate-400 dark:hover:bg-slate-800 cursor-pointer"
          >
            Close
          </button>

          {body && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
              >
                {loading ? "Regenerating..." : "Regenerate"}
              </button>

              <button
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy Email
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
