import { useEffect, useRef, useState, type ChangeEvent, type FC } from "react";
import {
  AlertCircle,
  FastForward,
  Pause,
  Play,
  Rewind,
  Volume2,
  VolumeX,
} from "lucide-react";
import type { Recording } from "../../api/meetings";
import { getRecordingStreamUrl } from "../../api/meetings";

interface AudioPlayerBarProps {
  meetingId: number;
  recordings: Recording[];
  activeRecordingId: number | null;
  onSelectRecording: (id: number) => void;
  seekTimestamp: number | null;
  onTimeUpdate: (currentTime: number) => void;
}

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export const AudioPlayerBar: FC<AudioPlayerBarProps> = ({
  meetingId,
  recordings,
  activeRecordingId,
  onSelectRecording,
  seekTimestamp,
  onTimeUpdate,
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  const activeRecording =
    recordings.find((r) => r.id === activeRecordingId) || recordings[0];

  const streamUrl = activeRecording
    ? getRecordingStreamUrl(meetingId, activeRecording.id)
    : "";

  // Reload audio element when active recording changes
  useEffect(() => {
    if (audioRef.current && activeRecording) {
      setPlaybackError(null);
      setIsPlaying(false);
      setCurrentTime(0);
      audioRef.current.load();
    }
  }, [activeRecording?.id, streamUrl]);

  // React to seekTimestamp prop changes
  useEffect(() => {
    if (seekTimestamp !== null && audioRef.current) {
      audioRef.current.currentTime = seekTimestamp;
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => {
          console.warn("Autoplay / seek play prevented:", err);
        });
    }
  }, [seekTimestamp]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    setPlaybackError(null);

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current
        .play()
        .then(() => {
          setIsPlaying(true);
        })
        .catch((err) => {
          console.error("Playback error:", err);
          setPlaybackError("Audio playback error. Ensure recording is processed and available.");
          setIsPlaying(false);
        });
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const time = audioRef.current.currentTime;
    setCurrentTime(time);
    onTimeUpdate(time);
  };

  const handleLoadedMetadata = () => {
    if (!audioRef.current) return;
    setDuration(
      audioRef.current.duration || activeRecording?.duration_seconds || 0,
    );
  };

  const handleSeek = (e: ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
      setCurrentTime(val);
      onTimeUpdate(val);
    }
  };

  const skipSeconds = (delta: number) => {
    if (!audioRef.current) return;
    const newTime = Math.max(
      0,
      Math.min(duration, audioRef.current.currentTime + delta),
    );
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
    onTimeUpdate(newTime);
  };

  const handleSpeedChange = () => {
    const speeds = [1, 1.25, 1.5, 2];
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    const nextSpeed = speeds[nextIdx];
    setPlaybackRate(nextSpeed);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextSpeed;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    const nextMute = !isMuted;
    setIsMuted(nextMute);
    audioRef.current.muted = nextMute;
  };

  if (!activeRecording) return null;

  return (
    <div className="sticky top-0 z-30 mb-6 rounded-2xl border border-indigo-100 bg-white/95 p-4 shadow-lg backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95 transition-colors">
      <audio
        ref={audioRef}
        src={streamUrl}
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
        onError={() => {
          setPlaybackError(
            "Could not load recording audio. Make sure the file exists and recording is completed.",
          );
          setIsPlaying(false);
        }}
      />

      <div className="flex flex-col gap-3">
        {playbackError && (
          <div className="flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/40 px-3 py-1.5 text-xs text-red-700 dark:text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{playbackError}</span>
          </div>
        )}

        {/* Top row: Track Info & Selector */}
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex h-2.5 w-2.5 rounded-full ${
                isPlaying
                  ? "animate-pulse bg-emerald-500"
                  : "bg-slate-400"
              }`}
            />
            <span className="font-semibold text-slate-800 dark:text-slate-100">
              {activeRecording.file_name}
            </span>
            {recordings.length > 1 && (
              <select
                className="ml-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                value={activeRecording.id}
                onChange={(e) => onSelectRecording(Number(e.target.value))}
              >
                {recordings.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.file_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Time & Speed */}
          <div className="flex items-center gap-4 text-xs font-medium text-slate-600 dark:text-slate-300">
            <button
              onClick={handleSpeedChange}
              className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-mono transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
              title="Change playback speed"
            >
              {playbackRate}x
            </button>
            <div className="font-mono">
              <span className="text-indigo-600 dark:text-indigo-400">{formatTime(currentTime)}</span>
              <span className="text-slate-400"> / </span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>
        </div>

        {/* Middle row: Progress slider */}
        <div className="relative flex items-center">
          <input
            type="range"
            min={0}
            max={duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 dark:bg-slate-700 accent-indigo-600 dark:accent-indigo-500 transition hover:bg-slate-300 dark:hover:bg-slate-600"
          />
        </div>

        {/* Bottom row: Playback controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => skipSeconds(-5)}
              className="rounded-full p-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100 cursor-pointer"
              title="Rewind 5 seconds"
            >
              <Rewind className="h-4 w-4" />
            </button>

            <button
              onClick={togglePlay}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-white shadow-md transition hover:bg-indigo-700 active:scale-95 cursor-pointer"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? (
                <Pause className="h-5 w-5" />
              ) : (
                <Play className="ml-0.5 h-5 w-5" />
              )}
            </button>

            <button
              onClick={() => skipSeconds(5)}
              className="rounded-full p-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100 cursor-pointer"
              title="Forward 5 seconds"
            >
              <FastForward className="h-4 w-4" />
            </button>
          </div>

          {/* Volume control */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 cursor-pointer"
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="h-4 w-4" />
              ) : (
                <Volume2 className="h-4 w-4" />
              )}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setVolume(val);
                setIsMuted(val === 0);
                if (audioRef.current) {
                  audioRef.current.volume = val;
                  audioRef.current.muted = val === 0;
                }
              }}
              className="h-1.5 w-16 cursor-pointer appearance-none rounded-lg bg-slate-200 dark:bg-slate-700 accent-indigo-600 dark:accent-indigo-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
