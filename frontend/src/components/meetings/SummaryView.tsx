import type { FC } from "react";
import { Brain, Cpu, Loader2, RefreshCw } from "lucide-react";
import type { MeetingSummary } from "../../api/meetings";

interface SummaryViewProps {
  summary: MeetingSummary | null;
  loading: boolean;
  onGenerate: (forceRegenerate?: boolean) => void;
}

export const SummaryView: FC<SummaryViewProps> = ({
  summary,
  loading,
  onGenerate,
}) => {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 transition-colors">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-indigo-50 p-1.5 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
            <Brain className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">AI Summary</h2>
            {summary && (
              <p className="flex items-center gap-1.5 text-xs text-slate-400">
                <Cpu className="h-3 w-3" />
                Generated using{" "}
                <span className="font-mono text-slate-600 dark:text-slate-300">
                  {summary.model_name}
                </span>{" "}
                • {new Date(summary.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={() => onGenerate(Boolean(summary))}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 disabled:opacity-50 cursor-pointer"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600 dark:text-indigo-400" />
              Generating...
            </>
          ) : (
            <>
              <RefreshCw className="h-3.5 w-3.5" />
              {summary ? "Regenerate Summary" : "Generate Summary"}
            </>
          )}
        </button>
      </div>

      {!summary ? (
        <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center dark:border-slate-800">
          <Brain className="mx-auto h-8 w-8 text-slate-300 dark:text-slate-600" />
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            No summary generated for this meeting yet.
          </p>
          <button
            onClick={() => onGenerate(false)}
            disabled={loading}
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-indigo-700 cursor-pointer"
          >
            {loading ? "Analyzing..." : "Generate AI Summary Now"}
          </button>
        </div>
      ) : (
        <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
          {summary.summary}
        </div>
      )}
    </div>
  );
};
