import type { FC } from "react";
import { Check, Milestone, Play } from "lucide-react";
import type { Decision } from "../../api/meetings";

interface DecisionsListProps {
  decisions: Decision[];
  onJumpToTime: (seconds: number) => void;
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export const DecisionsList: FC<DecisionsListProps> = ({
  decisions,
  onJumpToTime,
}) => {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 transition-colors">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Decisions</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Key agreements and strategic conclusions finalized in this session.
          </p>
        </div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border dark:border-emerald-800/40">
          {decisions.length} recorded
        </span>
      </div>

      {decisions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
          No decisions recorded for this meeting yet.
        </div>
      ) : (
        <div className="space-y-3">
          {decisions.map((decision) => (
            <div
              key={decision.id}
              className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 bg-emerald-50/20 p-4 transition hover:border-emerald-300 hover:shadow-xs dark:border-slate-800 dark:bg-emerald-950/10 dark:hover:border-emerald-800/50 md:flex-row md:items-center"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full bg-emerald-100 p-1 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300">
                  <Check className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {decision.description}
                  </p>
                  {decision.decision_type && (
                    <span className="mt-1.5 inline-flex items-center gap-1 rounded-md bg-white border border-emerald-200 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-slate-800 dark:border-emerald-800/50 dark:text-emerald-300">
                      <Milestone className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                      {decision.decision_type}
                    </span>
                  )}
                </div>
              </div>

              {decision.source_start_time !== null && decision.source_start_time !== undefined && (
                <button
                  onClick={() => onJumpToTime(decision.source_start_time!)}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-emerald-200 bg-white px-2.5 py-1 text-xs font-semibold text-emerald-800 transition hover:bg-emerald-50 dark:border-emerald-800/60 dark:bg-slate-800 dark:text-emerald-300 dark:hover:bg-slate-700 cursor-pointer"
                  title="Jump to recording moment"
                >
                  <Play className="h-3 w-3 fill-emerald-600 text-emerald-600 dark:fill-emerald-400 dark:text-emerald-400" />
                  {formatTimestamp(decision.source_start_time)}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
