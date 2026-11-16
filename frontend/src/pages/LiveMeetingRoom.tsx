import { useCallback, useEffect, useMemo, useRef, useState, type FC } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Camera,
  Check,
  CheckSquare,
  Edit2,
  Loader2,
  Mic,
  MicOff,
  Milestone,
  Monitor,
  MonitorOff,
  PhoneOff,
  RefreshCw,
  Share2,
  Sparkles,
  Subtitles,
  Users,
  Video,
  VideoOff,
  Volume2,
  VolumeX,
} from "lucide-react";

import {
  createMeeting,
  generateMeetingSummary,
  getLiveInsights,
  getMeeting,
  saveLiveTranscripts,
  updateMeeting,
  uploadRecording,
  type Meeting,
} from "../api/meetings";
import { useAuthStore } from "../store/authStore";
import ThemeToggle from "../components/ThemeToggle";

interface LiveSegment {
  id: string;
  speaker: string;
  text: string;
  timestamp: string;
  startTimeSec: number;
  endTimeSec: number;
}

interface LiveActionItem {
  description: string;
  assignee_name?: string;
  priority: string;
}

interface LiveDecision {
  description: string;
  decision_type?: string;
}

interface RemotePeer {
  peerId: string;
  userName: string;
  stream?: MediaStream;
  isMicOn: boolean;
  isVideoOn: boolean;
  isSpeaking: boolean;
}

const ICE_SERVERS = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
  ],
};

// Remote Participant Video Tile Component
const RemoteVideoTile: FC<{ peer: RemotePeer }> = ({ peer }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isSpeakerMuted, setIsSpeakerMuted] = useState(false);

  // Dedicated audio playback ensures remote speech is always heard even if camera is off
  useEffect(() => {
    if (audioRef.current && peer.stream) {
      if (audioRef.current.srcObject !== peer.stream) {
        audioRef.current.srcObject = peer.stream;
      }
      audioRef.current.muted = isSpeakerMuted;
      audioRef.current.play().catch(() => {});
    }
  }, [peer.stream, isSpeakerMuted]);

  useEffect(() => {
    if (videoRef.current && peer.stream) {
      if (videoRef.current.srcObject !== peer.stream) {
        videoRef.current.srcObject = peer.stream;
      }
      videoRef.current.play().catch(() => {});
    }
  }, [peer.stream, peer.isVideoOn]);

  const showVideo = Boolean(peer.isVideoOn && peer.stream);

  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-xl min-h-[220px]">
      {/* Hidden audio element dedicated to remote audio */}
      <audio ref={audioRef} autoPlay playsInline />

      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`h-full w-full object-cover ${showVideo ? "block" : "hidden"}`}
      />

      {!showVideo && (
        <div className="flex flex-col items-center justify-center">
          <div
            className={`relative flex h-24 w-24 items-center justify-center rounded-full text-2xl font-extrabold text-white transition-all duration-300 ${
              peer.isSpeaking
                ? "bg-indigo-600 ring-8 ring-indigo-500/30 scale-105"
                : "bg-slate-800 ring-4 ring-slate-700/50"
            }`}
          >
            {peer.userName ? peer.userName.charAt(0).toUpperCase() : "P"}
            {peer.isSpeaking && (
              <span className="absolute -bottom-1 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-black">
                Speaking
              </span>
            )}
          </div>
          <span className="mt-3 text-sm font-semibold text-slate-200">
            {peer.userName}
          </span>
          <span className="mt-0.5 text-[11px] text-slate-500">Camera is off</span>
        </div>
      )}

      {/* Top right: Mute Remote Speaker button (solves echo on same laptop!) */}
      <button
        onClick={() => setIsSpeakerMuted(!isSpeakerMuted)}
        className={`absolute top-3 right-3 flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold backdrop-blur-md transition shadow-md cursor-pointer ${
          isSpeakerMuted
            ? "bg-red-600/90 text-white ring-1 ring-red-400/50 hover:bg-red-700"
            : "bg-black/70 text-slate-200 ring-1 ring-white/20 hover:bg-black/90"
        }`}
        title={isSpeakerMuted ? "Unmute participant speaker" : "Mute participant speaker (solves echo on same laptop)"}
      >
        {isSpeakerMuted ? (
          <>
            <VolumeX className="h-3.5 w-3.5 text-white" />
            <span>Speaker Muted</span>
          </>
        ) : (
          <>
            <Volume2 className="h-3.5 w-3.5 text-slate-300" />
            <span className="text-[11px] text-slate-300">Mute Speaker (Stop Echo)</span>
          </>
        )}
      </button>

      <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-black/60 px-2.5 py-1 text-xs text-white backdrop-blur-md">
        <span>{peer.userName}</span>
        {peer.isMicOn ? (
          <div
            className={`h-2 w-2 rounded-full ${
              peer.isSpeaking ? "bg-emerald-400 animate-pulse" : "bg-slate-400"
            }`}
          />
        ) : (
          <MicOff className="h-3 w-3 text-red-400" />
        )}
      </div>
    </div>
  );
};

export default function LiveMeetingRoom() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Determine if current user is the host / meeting creator
  const isHost = useMemo(() => {
    if (!meeting) return meetingId === "new" || !meetingId;
    return meeting.owner_id === user?.id;
  }, [meeting, user?.id, meetingId]);

  const isHostRef = useRef<boolean>(isHost);
  useEffect(() => {
    isHostRef.current = isHost;
  }, [isHost]);

  const [hostEndedNotice, setHostEndedNotice] = useState<boolean>(false);
  const connectedAudioSources = useRef<Map<string, MediaStreamAudioSourceNode>>(new Map());

  // Editable Meeting Title
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  // Media streams & device states
  const [isMicOn, setIsMicOn] = useState(true);
  const [isVideoOn, setIsVideoOn] = useState(true);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [isCaptionsOn, setIsCaptionsOn] = useState(true);
  const isCaptionsOnRef = useRef<boolean>(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [mediaPermissionDenied, setMediaPermissionDenied] = useState(false);
  const [speechActive, setSpeechActive] = useState(false);
  const [speechPermissionNotice, setSpeechPermissionNotice] = useState<string | null>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);

  // Video element refs
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const screenVideoRef = useRef<HTMLVideoElement | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);

  // Tracking all tracks and lifetime state for absolute hardware release
  const isMeetingEndedRef = useRef<boolean>(false);
  const activeTracksRef = useRef<Set<MediaStreamTrack>>(new Set());
  const speechRestartTimerRef = useRef<any>(null);

  // Multi-Participant WebRTC Peers & Signaling
  const myPeerId = useRef<string>(`peer_${Math.random().toString(36).substring(2, 9)}`);
  const [remotePeers, setRemotePeers] = useState<Map<string, RemotePeer>>(new Map());
  const peerConnections = useRef<Map<string, RTCPeerConnection>>(new Map());
  const signalingSocketRef = useRef<WebSocket | null>(null);

  // Audio analysis for speaking ripple
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const mixedAudioDestinationRef = useRef<MediaStreamAudioDestinationNode | null>(null);

  // In-browser recording
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const recordingSecondsRef = useRef<number>(0);
  const [isSavingMeeting, setIsSavingMeeting] = useState(false);
  const [saveProgressMessage, setSaveProgressMessage] = useState("");

  // Live Speech Recognition & Intelligence
  const speechRecognitionRef = useRef<any>(null);
  const isSpeechRunningRef = useRef<boolean>(false);
  const isMicOnRef = useRef<boolean>(true);
  const [interimText, setInterimText] = useState("");
  const [segments, setSegments] = useState<LiveSegment[]>([]);
  const [actionItems, setActionItems] = useState<LiveActionItem[]>([]);
  const [decisions, setDecisions] = useState<LiveDecision[]>([]);
  const [isAnalyzingInsights, setIsAnalyzingInsights] = useState(false);

  // In-meeting notes & manual text
  const [meetingNotes, setMeetingNotes] = useState("");
  const [manualInput, setManualInput] = useState("");

  // Sidebar Drawer
  const [activeTab, setActiveTab] = useState<"transcript" | "actions" | "decisions" | "notes">("transcript");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Link copy feedback
  const [copiedLink, setCopiedLink] = useState(false);
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null);

  // Absolute cleanup of camera, microphone, Web Speech API, and AudioContext (stable ref-based)
  const releaseAllMediaDevices = useCallback(() => {
    isMeetingEndedRef.current = true;
    isMicOnRef.current = false;
    isCaptionsOnRef.current = false;

    // 1. Immediately abort Web Speech API and clear timers
    if (speechRestartTimerRef.current) {
      clearTimeout(speechRestartTimerRef.current);
      speechRestartTimerRef.current = null;
    }
    if (speechRecognitionRef.current) {
      try {
        speechRecognitionRef.current.onend = null;
        speechRecognitionRef.current.onerror = null;
        speechRecognitionRef.current.onresult = null;
        speechRecognitionRef.current.abort();
      } catch {}
      speechRecognitionRef.current = null;
    }
    isSpeechRunningRef.current = false;
    setSpeechActive(false);

    // 2. Stop audio volume analysis loop
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    // 3. Close AudioContext so all media stream source nodes release hardware
    connectedAudioSources.current.forEach((source) => {
      try {
        source.disconnect();
      } catch {}
    });
    connectedAudioSources.current.clear();

    if (audioContextRef.current) {
      try {
        audioContextRef.current.close().catch(() => {});
      } catch {}
      audioContextRef.current = null;
    }
    mixedAudioDestinationRef.current = null;

    // Stop MediaRecorder if running
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }
    mediaRecorderRef.current = null;
    setIsRecording(false);

    // 4. Stop ALL tracks in activeTracksRef (guaranteeing hardware LEDs turn off)
    activeTracksRef.current.forEach((track) => {
      try {
        track.enabled = false;
        track.stop();
      } catch {}
    });
    activeTracksRef.current.clear();

    // 5. Stop all tracks on local stream ref
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        try {
          track.enabled = false;
          track.stop();
        } catch {}
      });
      localStreamRef.current = null;
    }

    // 6. Stop all tracks on screen share stream
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((track) => {
        try {
          track.enabled = false;
          track.stop();
        } catch {}
      });
      screenStreamRef.current = null;
    }

    // 7. Clear video elements and stop their attached streams
    if (localVideoRef.current) {
      if (localVideoRef.current.srcObject) {
        try {
          const s = localVideoRef.current.srcObject as MediaStream;
          s.getTracks().forEach((t) => {
            t.enabled = false;
            t.stop();
          });
        } catch {}
      }
      localVideoRef.current.srcObject = null;
    }
    if (screenVideoRef.current) {
      if (screenVideoRef.current.srcObject) {
        try {
          const s = screenVideoRef.current.srcObject as MediaStream;
          s.getTracks().forEach((t) => {
            t.enabled = false;
            t.stop();
          });
        } catch {}
      }
      screenVideoRef.current.srcObject = null;
    }

    // 8. Close WebRTC peer connections and stop their senders
    peerConnections.current.forEach((pc) => {
      try {
        pc.getSenders().forEach((sender) => {
          if (sender.track) {
            try {
              sender.track.enabled = false;
              sender.track.stop();
            } catch {}
          }
        });
        pc.close();
      } catch {}
    });
    peerConnections.current.clear();

    // 9. Close WebSocket signaling
    if (signalingSocketRef.current) {
      try {
        signalingSocketRef.current.close();
      } catch {}
      signalingSocketRef.current = null;
    }

    setLocalStream(null);
    setIsMicOn(false);
    setIsVideoOn(false);
    setIsSpeaking(false);
    setIsScreenSharing(false);
  }, []);

  // Window beforeunload listener to guarantee devices release if tab is closed
  useEffect(() => {
    const handleBeforeUnload = () => {
      releaseAllMediaDevices();
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [releaseAllMediaDevices]);

  useEffect(() => {
    recordingSecondsRef.current = recordingSeconds;
  }, [recordingSeconds]);

  useEffect(() => {
    isMicOnRef.current = isMicOn;
  }, [isMicOn]);

  // Proactively resume AudioContext on user interaction to guarantee host voice is never silent
  useEffect(() => {
    const resumeAudioEngine = () => {
      if (audioContextRef.current && audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(() => {});
      }
    };
    window.addEventListener("pointerdown", resumeAudioEngine);
    window.addEventListener("click", resumeAudioEngine);
    window.addEventListener("keydown", resumeAudioEngine);
    return () => {
      window.removeEventListener("pointerdown", resumeAudioEngine);
      window.removeEventListener("click", resumeAudioEngine);
      window.removeEventListener("keydown", resumeAudioEngine);
    };
  }, []);

  // Robust Callback Ref for Local Video (Guaranteeing face shows on screen)
  const attachLocalStreamToVideo = useCallback((node: HTMLVideoElement | null) => {
    localVideoRef.current = node;
    if (node && localStreamRef.current) {
      if (node.srcObject !== localStreamRef.current) {
        node.srcObject = localStreamRef.current;
      }
      node.muted = true;
      node.defaultMuted = true;
      node.play().catch((err) => console.warn("Local video play notice:", err));
    }
  }, []);

  // 1. Initialize Meeting
  useEffect(() => {
    let active = true;

    async function initializeRoom() {
      try {
        setError(null);

        // If meetingId is "new" or undefined, create a brand-new live meeting
        if (!meetingId || meetingId === "new") {
          const now = new Date();
          const formatted = now.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          });
          const created = await createMeeting({
            title: `Live Meeting - ${formatted}`,
            description: "Live session with camera, microphone, screen share, and automated intelligence.",
            meeting_date: now.toISOString(),
          });

          if (active) {
            setMeeting(created);
            setTitleDraft(created.title);
            window.history.replaceState(null, "", `/meetings/${created.id}/room`);
          }
        } else {
          const numericId = Number(meetingId);
          if (isNaN(numericId)) {
            throw new Error("Invalid meeting ID");
          }
          const existing = await getMeeting(numericId);
          if (active) {
            setMeeting(existing);
            setTitleDraft(existing.title);
          }
        }
      } catch (err: any) {
        if (active) {
          const status = err.response?.status;
          if (status === 401) {
            useAuthStore.getState().logout();
            navigate(`/login?from=${encodeURIComponent(window.location.pathname)}`);
            return;
          }
          releaseAllMediaDevices();
          setError(
            err.response?.data?.detail ||
            err.message ||
            "Failed to initialize live meeting"
          );
        }
      }
    }

    initializeRoom();

    return () => {
      active = false;
    };
  }, [meetingId, navigate, releaseAllMediaDevices]);

  // 2. Setup Camera & Microphone Stream Immediately
  async function requestMediaPermissions() {
    setMediaPermissionDenied(false);
    try {
      let stream: MediaStream | null = null;
      try {
        // Preferred high-resolution video without mobile-specific facingMode
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch (hdErr) {
        console.warn("Retrying with simple video/audio constraints:", hdErr);
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
      }

      // Track all tracks for complete hardware shutdown on exit
      stream.getTracks().forEach((track) => {
        activeTracksRef.current.add(track);
      });

      localStreamRef.current = stream;
      setLocalStream(stream);
      setIsVideoOn(true);
      setIsMicOn(true);

      // Attach immediately to local video element
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
        localVideoRef.current.muted = true;
        localVideoRef.current.defaultMuted = true;
        localVideoRef.current.play().catch(() => {});
      }

      // Add tracks to any existing peer connections
      peerConnections.current.forEach((pc) => {
        stream?.getTracks().forEach((track) => {
          pc.addTrack(track, stream!);
        });
      });

      // Audio analysis for speaking ripple & mixed destination
      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioContextClass) {
          const ctx = new AudioContextClass();
          audioContextRef.current = ctx;
          if (ctx.state === "suspended") {
            ctx.resume().catch(() => {});
          }

          // Mixed destination node for recording all audio streams
          const dest = ctx.createMediaStreamDestination();
          mixedAudioDestinationRef.current = dest;

          const source = ctx.createMediaStreamSource(stream);
          source.connect(dest);
          connectedAudioSources.current.set("local", source);

          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          source.connect(analyser);
          analyserRef.current = analyser;

          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          const checkVolume = () => {
            if (!analyserRef.current || isMeetingEndedRef.current) return;
            analyserRef.current.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
              sum += dataArray[i];
            }
            const average = sum / bufferLength;
            const speakingNow = average > 14;
            setIsSpeaking(speakingNow);

            if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
              signalingSocketRef.current.send(
                JSON.stringify({
                  type: "media_state",
                  isMicOn: isMicOnRef.current,
                  isVideoOn: true,
                  isSpeaking: speakingNow,
                })
              );
            }

            animFrameRef.current = requestAnimationFrame(checkVolume);
          };
          checkVolume();
        }
      } catch (audioErr) {
        console.warn("Audio analyser setup skipped:", audioErr);
      }
    } catch (err: any) {
      console.warn("Camera/Mic access notice:", err);
      // Fallback: try audio-only if camera is unavailable
      try {
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStream.getTracks().forEach((track) => {
          activeTracksRef.current.add(track);
        });
        localStreamRef.current = audioStream;
        setLocalStream(audioStream);
        setIsVideoOn(false);
        setIsMicOn(true);
      } catch (audioErr) {
        console.warn("Microphone access unavailable:", audioErr);
        setMediaPermissionDenied(true);
      }
    }
  }

  // Master Recording for the Whole Meeting (Host only: records host video + all mixed audio)
  const startMasterRecording = useCallback(async () => {
    if (!isHostRef.current || isRecording || mediaRecorderRef.current) return;

    try {
      if (audioContextRef.current && audioContextRef.current.state === "suspended") {
        try {
          await audioContextRef.current.resume();
          console.log("AudioContext active and resumed for master recording.");
        } catch {}
      }

      let audioTrack: MediaStreamTrack | null = null;
      if (mixedAudioDestinationRef.current) {
        audioTrack = mixedAudioDestinationRef.current.stream.getAudioTracks()[0];
      }
      if (!audioTrack && localStreamRef.current) {
        audioTrack = localStreamRef.current.getAudioTracks()[0];
      }

      const videoTrack = screenStreamRef.current?.getVideoTracks()[0] || localStreamRef.current?.getVideoTracks()[0];

      const tracksToRecord: MediaStreamTrack[] = [];
      if (videoTrack) tracksToRecord.push(videoTrack);
      if (audioTrack) tracksToRecord.push(audioTrack);

      if (tracksToRecord.length === 0) return;

      const recordStream = new MediaStream(tracksToRecord);
      startMediaRecording(recordStream);
      console.log("Master recording started by host for the whole meeting.");
    } catch (err) {
      console.warn("startMasterRecording notice:", err);
    }
  }, [isRecording]);

  useEffect(() => {
    if (!isHost || isRecording || !meeting) return;
    if (localStreamRef.current || mixedAudioDestinationRef.current) {
      startMasterRecording();
    }
  }, [isHost, meeting, isRecording, localStream, startMasterRecording]);

  useEffect(() => {
    requestMediaPermissions();

    return () => {
      releaseAllMediaDevices();
    };
  }, []);

  // Guarantee local video stream stays attached whenever localStream, isVideoOn, or isScreenSharing changes
  useEffect(() => {
    const streamToAttach = localStream || localStreamRef.current;
    if (localVideoRef.current && streamToAttach) {
      if (localVideoRef.current.srcObject !== streamToAttach) {
        localVideoRef.current.srcObject = streamToAttach;
      }
      localVideoRef.current.muted = true;
      localVideoRef.current.defaultMuted = true;
      localVideoRef.current.play().catch(() => {});
    }
  }, [localStream, isVideoOn, isScreenSharing]);

  useEffect(() => {
    if (screenVideoRef.current && screenStreamRef.current) {
      if (screenVideoRef.current.srcObject !== screenStreamRef.current) {
        screenVideoRef.current.srcObject = screenStreamRef.current;
      }
      screenVideoRef.current.play().catch(() => {});
    }
  }, [isScreenSharing]);

  // 3. Multi-Participant WebRTC Signaling over WebSocket
  useEffect(() => {
    if (!meeting?.id) return;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/ws/meetings/${meeting.id}`;
    const ws = new WebSocket(wsUrl);
    signalingSocketRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "join",
          peerId: myPeerId.current,
          userName: user?.full_name || "Guest Participant",
        })
      );
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "room_users": {
            for (const u of msg.users) {
              if (u.peerId === myPeerId.current) continue;
              await createPeerConnection(u.peerId, u.userName, true);
            }
            break;
          }

          case "user_joined": {
            if (msg.peerId !== myPeerId.current) {
              await createPeerConnection(msg.peerId, msg.userName, false);
            }
            break;
          }

          case "offer": {
            if (msg.target === myPeerId.current) {
              const pc = await getOrCreatePC(msg.sender, "Participant");
              await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
              const answer = await pc.createAnswer();
              await pc.setLocalDescription(answer);
              ws.send(
                JSON.stringify({
                  type: "answer",
                  target: msg.sender,
                  sdp: answer,
                })
              );
            }
            break;
          }

          case "answer": {
            if (msg.target === myPeerId.current) {
              const pc = peerConnections.current.get(msg.sender);
              if (pc) {
                await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
              }
            }
            break;
          }

          case "candidate": {
            if (msg.target === myPeerId.current) {
              const pc = peerConnections.current.get(msg.sender);
              if (pc && msg.candidate) {
                await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
              }
            }
            break;
          }

          case "media_state": {
            setRemotePeers((prev) => {
              const updated = new Map(prev);
              const peer = updated.get(msg.sender);
              if (peer) {
                updated.set(msg.sender, {
                  ...peer,
                  isMicOn: msg.isMicOn ?? peer.isMicOn,
                  isVideoOn: msg.isVideoOn ?? peer.isVideoOn,
                  isSpeaking: msg.isSpeaking ?? peer.isSpeaking,
                });
              }
              return updated;
            });
            break;
          }

          case "user_left": {
            closePeerConnection(msg.peerId);
            break;
          }

          case "live_transcript_segment": {
            if (msg.segment && msg.sender !== myPeerId.current) {
              setSegments((prev) => {
                if (prev.some((s) => s.id === msg.segment.id)) return prev;
                return [...prev, msg.segment];
              });
            }
            break;
          }

          case "meeting_ended": {
            releaseAllMediaDevices();
            setHostEndedNotice(true);
            const target = meeting?.id || meetingId;
            setTimeout(() => {
              navigate(`/meetings/${target}`);
            }, 1800);
            break;
          }
        }
      } catch (e) {
        console.warn("Signaling notice:", e);
      }
    };

    async function getOrCreatePC(peerId: string, peerName: string): Promise<RTCPeerConnection> {
      let pc = peerConnections.current.get(peerId);
      if (!pc) {
        pc = await createPeerConnection(peerId, peerName, false);
      }
      return pc;
    }

    async function createPeerConnection(peerId: string, peerName: string, isInitiator: boolean) {
      if (peerConnections.current.has(peerId)) {
        return peerConnections.current.get(peerId)!;
      }

      const pc = new RTCPeerConnection(ICE_SERVERS);
      peerConnections.current.set(peerId, pc);

      setRemotePeers((prev) => {
        const next = new Map(prev);
        next.set(peerId, {
          peerId,
          userName: peerName,
          isMicOn: true,
          isVideoOn: true,
          isSpeaking: false,
        });
        return next;
      });

      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => {
          pc.addTrack(track, localStreamRef.current!);
        });
      }

      pc.onicecandidate = (event) => {
        if (event.candidate && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: "candidate",
              target: peerId,
              candidate: event.candidate,
            })
          );
        }
      };

      pc.ontrack = (event) => {
        const remoteStream = event.streams[0] || new MediaStream([event.track]);
        setRemotePeers((prev) => {
          const next = new Map(prev);
          const peer = next.get(peerId);
          if (peer) {
            next.set(peerId, {
              ...peer,
              stream: remoteStream,
            });
          }
          return next;
        });

        // Mix remote participant audio into master recorder destination (Host only)
        const audioTrack = event.track.kind === "audio" ? event.track : remoteStream?.getAudioTracks()[0];
        if (isHostRef.current && audioTrack && audioContextRef.current && mixedAudioDestinationRef.current) {
          try {
            if (!connectedAudioSources.current.has(peerId)) {
              if (audioContextRef.current.state === "suspended") {
                audioContextRef.current.resume().catch(() => {});
              }
              const remoteSource = audioContextRef.current.createMediaStreamSource(new MediaStream([audioTrack]));
              remoteSource.connect(mixedAudioDestinationRef.current);
              connectedAudioSources.current.set(peerId, remoteSource);
              console.log(`Mixed remote audio for peer ${peerId} into master recording.`);
            }
          } catch (mixErr) {
            console.warn("Could not connect remote audio to master recorder destination:", mixErr);
          }
        }
      };

      if (isInitiator) {
        try {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          ws.send(
            JSON.stringify({
              type: "offer",
              target: peerId,
              sdp: offer,
            })
          );
        } catch (offerErr) {
          console.warn("Offer error:", offerErr);
        }
      }

      return pc;
    }

    function closePeerConnection(peerId: string) {
      const pc = peerConnections.current.get(peerId);
      if (pc) {
        pc.close();
        peerConnections.current.delete(peerId);
      }
      const source = connectedAudioSources.current.get(peerId);
      if (source) {
        try {
          source.disconnect();
        } catch {}
        connectedAudioSources.current.delete(peerId);
      }
      setRemotePeers((prev) => {
        const next = new Map(prev);
        next.delete(peerId);
        return next;
      });
    }

    return () => {
      ws.close();
      peerConnections.current.forEach((pc) => pc.close());
      peerConnections.current.clear();
      setRemotePeers(new Map());
    };
  }, [meeting?.id, user]);

  // 4. Bulletproof MediaRecorder for continuous recording
  function startMediaRecording(stream: MediaStream) {
    try {
      recordedChunksRef.current = [];
      const types = [
        "video/webm;codecs=vp8,opus",
        "video/webm;codecs=vp9,opus",
        "video/webm",
        "video/mp4",
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "",
      ];

      let selectedType = "";
      for (const t of types) {
        if (!t || (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t))) {
          selectedType = t;
          break;
        }
      }

      const options = selectedType ? { mimeType: selectedType } : {};
      const recorder = new MediaRecorder(stream, options);

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      recorder.start(1000); // 1-second timeslices
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      console.log("MediaRecorder started successfully with mimeType:", recorder.mimeType);
    } catch (e) {
      console.warn("MediaRecorder start notice:", e);
    }
  }

  // 5. Timer for live meeting duration
  useEffect(() => {
    const timer = setInterval(() => {
      setRecordingSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 6. Robust Continuous Background Speech Recognition
  useEffect(() => {
    isCaptionsOnRef.current = isCaptionsOn;
  }, [isCaptionsOn]);

  const startCaptionsWithUserGesture = useCallback(() => {
    setSpeechPermissionNotice(null);
    setIsCaptionsOn(true);
    isCaptionsOnRef.current = true;
    if (speechRecognitionRef.current) {
      try {
        speechRecognitionRef.current.start();
      } catch (e) {
        console.warn("Manual speech start notice:", e);
      }
    }
  }, []);

  useEffect(() => {
    const SpeechRecognitionClass =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionClass) {
      console.warn("SpeechRecognition API is not supported in this browser.");
      return;
    }

    let isDisposed = false;
    let recognition: any = null;
    let consecutiveErrors = 0;
    let isFatal = false;

    try {
      recognition = new SpeechRecognitionClass();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        isSpeechRunningRef.current = true;
        setSpeechActive(true);
        setSpeechPermissionNotice(null);
        consecutiveErrors = 0;
        isFatal = false;
      };

      recognition.onresult = (event: any) => {
        let currentInterim = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          const transcript = res[0]?.transcript || "";
          if (res.isFinal) {
            const trimmed = transcript.trim();
            if (trimmed) {
              const nowSec = recordingSecondsRef.current;
              const m = Math.floor(nowSec / 60);
              const s = nowSec % 60;
              const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

              const newSegment: LiveSegment = {
                id: Math.random().toString(36).substring(2, 9),
                speaker: user?.full_name?.split(" ")[0] || (isHostRef.current ? "Host" : "Participant"),
                text: trimmed,
                timestamp: timeStr,
                startTimeSec: Math.max(0, nowSec - 4),
                endTimeSec: nowSec,
              };

              setSegments((prev) => [...prev, newSegment]);

              // Broadcast speech segment to all peers over WebSocket
              if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
                try {
                  signalingSocketRef.current.send(
                    JSON.stringify({
                      type: "live_transcript_segment",
                      segment: newSegment,
                    })
                  );
                } catch {}
              }
            }
          } else {
            currentInterim += transcript;
          }
        }
        setInterimText(currentInterim);
      };

      recognition.onerror = (err: any) => {
        if (err.error === "no-speech") return;
        consecutiveErrors++;
        console.warn("Live speech recognition notice:", err.error);

        if (err.error === "not-allowed" || err.error === "service-not-allowed") {
          isFatal = true;
          setSpeechActive(false);
          setSpeechPermissionNotice(
            "Speech recognition requires permission. Click 'Enable Captions' to turn on real-time transcription."
          );
        }
      };

      recognition.onend = () => {
        isSpeechRunningRef.current = false;
        if (isDisposed || isFatal || isMeetingEndedRef.current || !isMicOnRef.current || !isCaptionsOnRef.current) {
          setSpeechActive(false);
          return;
        }

        // Throttled restart with backoff so it never loops uncontrollably
        const delay = consecutiveErrors > 3 ? 3000 : 1000;
        if (speechRestartTimerRef.current) {
          clearTimeout(speechRestartTimerRef.current);
        }
        speechRestartTimerRef.current = setTimeout(() => {
          if (!isDisposed && !isFatal && !isMeetingEndedRef.current && isMicOnRef.current && isCaptionsOnRef.current && !isSpeechRunningRef.current) {
            try {
              recognition.start();
            } catch {
              // ignore
            }
          }
        }, delay);
      };

      // Try initial start; if browser blocks without user gesture, catch gracefully
      try {
        recognition.start();
      } catch (startErr) {
        console.warn("Initial speech recognition start notice:", startErr);
      }
      speechRecognitionRef.current = recognition;
    } catch (e) {
      console.warn("Speech recognition init notice:", e);
    }

    return () => {
      isDisposed = true;
      if (speechRestartTimerRef.current) {
        clearTimeout(speechRestartTimerRef.current);
        speechRestartTimerRef.current = null;
      }
      if (recognition) {
        try {
          recognition.onend = null;
          recognition.onerror = null;
          recognition.onresult = null;
          recognition.abort();
        } catch {}
      }
    };
  }, [user]);

  // Auto-scroll transcript when new segments arrive
  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [segments, interimText]);

  // 7. Background Real-Time Action Items & Decisions Extraction
  async function triggerInsightsAnalysis() {
    if (!meeting?.id || segments.length === 0) return;
    try {
      setIsAnalyzingInsights(true);
      const fullText = segments.map((s) => `${s.speaker}: ${s.text}`).join("\n");
      const res = await getLiveInsights(meeting.id, fullText, meeting?.title);
      if (res.action_items && Array.isArray(res.action_items)) {
        setActionItems(res.action_items);
      }
      if (res.decisions && Array.isArray(res.decisions)) {
        setDecisions(res.decisions);
      }
    } catch (e) {
      console.warn("Live insights extraction notice:", e);
    } finally {
      setIsAnalyzingInsights(false);
    }
  }

  // Auto-sync insights periodically during conversation
  useEffect(() => {
    if (segments.length > 0 && segments.length % 3 === 0) {
      triggerInsightsAnalysis();
    }
  }, [segments.length]);

  // Controls: Toggle Microphone
  async function toggleMic() {
    const nextMic = !isMicOn;
    setIsMicOn(nextMic);
    isMicOnRef.current = nextMic;

    const activeAudioTrack = localStreamRef.current?.getAudioTracks().find((t) => t.readyState === "live");

    if (nextMic) {
      if (activeAudioTrack) {
        activeAudioTrack.enabled = true;
      } else {
        try {
          const freshStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });
          const newTrack = freshStream.getAudioTracks()[0];
          if (newTrack) {
            activeTracksRef.current.add(newTrack);
            const otherTracks = localStreamRef.current ? localStreamRef.current.getVideoTracks() : [];
            const updatedStream = new MediaStream([...otherTracks, newTrack]);
            localStreamRef.current = updatedStream;
            setLocalStream(updatedStream);

            // Re-route into audio context for analyser & speaking ripple
            if (audioContextRef.current && mixedAudioDestinationRef.current) {
              try {
                if (audioContextRef.current.state === "suspended") {
                  audioContextRef.current.resume().catch(() => {});
                }
                const source = audioContextRef.current.createMediaStreamSource(new MediaStream([newTrack]));
                source.connect(mixedAudioDestinationRef.current);
                if (analyserRef.current) {
                  source.connect(analyserRef.current);
                }
              } catch (audioCtxErr) {
                console.warn("AudioContext reconnection notice:", audioCtxErr);
              }
            }

            peerConnections.current.forEach(async (pc, peerId) => {
              const sender = pc.getSenders().find((s) => s.track && s.track.kind === "audio");
              if (sender) {
                await sender.replaceTrack(newTrack);
              } else {
                pc.addTrack(newTrack, updatedStream);
                try {
                  const offer = await pc.createOffer();
                  await pc.setLocalDescription(offer);
                  if (signalingSocketRef.current?.readyState === WebSocket.OPEN) {
                    signalingSocketRef.current.send(
                      JSON.stringify({
                        type: "offer",
                        target: peerId,
                        sdp: offer,
                      })
                    );
                  }
                } catch {}
              }
            });
          }
        } catch (e) {
          console.warn("Could not start fresh microphone audio track:", e);
        }
      }
    } else {
      if (localStreamRef.current) {
        localStreamRef.current.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }
      setIsSpeaking(false);
    }

    // Pause/Resume Speech Recognition accordingly
    if (speechRecognitionRef.current) {
      if (nextMic && isCaptionsOnRef.current && !isSpeechRunningRef.current) {
        try {
          speechRecognitionRef.current.start();
        } catch {}
      } else if (!nextMic && isSpeechRunningRef.current) {
        try {
          speechRecognitionRef.current.abort();
        } catch {}
      }
    }

    if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
      signalingSocketRef.current.send(
        JSON.stringify({
          type: "media_state",
          isMicOn: nextMic,
          isVideoOn,
          isSpeaking: false,
        })
      );
    }
  }

  // Controls: Toggle Camera
  async function toggleCamera() {
    const nextVideo = !isVideoOn;
    setIsVideoOn(nextVideo);

    const activeVideoTrack = localStreamRef.current?.getVideoTracks().find((t) => t.readyState === "live");

    if (nextVideo) {
      if (activeVideoTrack) {
        activeVideoTrack.enabled = true;
        if (localVideoRef.current && localStreamRef.current) {
          if (localVideoRef.current.srcObject !== localStreamRef.current) {
            localVideoRef.current.srcObject = localStreamRef.current;
          }
          localVideoRef.current.play().catch(() => {});
        }
      } else {
        try {
          let freshStream: MediaStream | null = null;
          try {
            freshStream = await navigator.mediaDevices.getUserMedia({
              video: { width: { ideal: 1280 }, height: { ideal: 720 } },
            });
          } catch {
            freshStream = await navigator.mediaDevices.getUserMedia({ video: true });
          }

          const newTrack = freshStream.getVideoTracks()[0];
          if (newTrack) {
            activeTracksRef.current.add(newTrack);
            const otherTracks = localStreamRef.current ? localStreamRef.current.getAudioTracks() : [];
            const updatedStream = new MediaStream([...otherTracks, newTrack]);
            localStreamRef.current = updatedStream;
            setLocalStream(updatedStream);

            if (localVideoRef.current) {
              localVideoRef.current.srcObject = updatedStream;
              localVideoRef.current.play().catch(() => {});
            }

            peerConnections.current.forEach(async (pc, peerId) => {
              const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
              if (sender) {
                await sender.replaceTrack(newTrack);
              } else {
                pc.addTrack(newTrack, updatedStream);
                try {
                  const offer = await pc.createOffer();
                  await pc.setLocalDescription(offer);
                  if (signalingSocketRef.current?.readyState === WebSocket.OPEN) {
                    signalingSocketRef.current.send(
                      JSON.stringify({
                        type: "offer",
                        target: peerId,
                        sdp: offer,
                      })
                    );
                  }
                } catch {}
              }
            });
          }
        } catch (e) {
          console.warn("Could not start fresh video track:", e);
          setIsVideoOn(false);
        }
      }
    } else {
      if (localStreamRef.current) {
        localStreamRef.current.getVideoTracks().forEach((track) => {
          track.enabled = false;
        });
      }
    }

    if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
      signalingSocketRef.current.send(
        JSON.stringify({
          type: "media_state",
          isMicOn,
          isVideoOn: nextVideo,
          isSpeaking,
        })
      );
    }
  }

  // Controls: Screen Share
  async function toggleScreenShare() {
    if (isScreenSharing) {
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((t) => t.stop());
        screenStreamRef.current = null;
      }
      setIsScreenSharing(false);

      if (localStreamRef.current) {
        const videoTrack = localStreamRef.current.getVideoTracks()[0];
        if (videoTrack) {
          peerConnections.current.forEach((pc) => {
            const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
            if (sender) {
              sender.replaceTrack(videoTrack);
            }
          });
        }
      }
    } else {
      try {
        const stream = await navigator.mediaDevices.getDisplayMedia({
          video: { cursor: "always" } as any,
          audio: true,
        });

        screenStreamRef.current = stream;
        if (screenVideoRef.current) {
          screenVideoRef.current.srcObject = stream;
        }
        setIsScreenSharing(true);

        const screenTrack = stream.getVideoTracks()[0];
        if (screenTrack) {
          peerConnections.current.forEach((pc) => {
            const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
            if (sender) {
              sender.replaceTrack(screenTrack);
            }
          });

          screenTrack.onended = () => {
            toggleScreenShare();
          };
        }
      } catch (err) {
        console.warn("Screen share notice:", err);
      }
    }
  }

  // Controls: Toggle Live Captions
  function toggleCaptions() {
    if (isCaptionsOn) {
      setIsCaptionsOn(false);
      setSpeechActive(false);
      if (speechRecognitionRef.current) {
        try {
          speechRecognitionRef.current.stop();
        } catch {}
      }
    } else {
      startCaptionsWithUserGesture();
    }
  }

  // Save Custom Meeting Title
  async function handleSaveTitle() {
    if (!meeting || !titleDraft.trim()) {
      setIsEditingTitle(false);
      return;
    }
    try {
      const updated = await updateMeeting(meeting.id, { title: titleDraft.trim() });
      setMeeting(updated);
    } catch (err) {
      console.warn("Failed to update title:", err);
    } finally {
      setIsEditingTitle(false);
    }
  }

  // Add Manual Speech / Note Segment
  function handleAddManualSegment(e: React.FormEvent) {
    e.preventDefault();
    if (!manualInput.trim()) return;

    const nowSec = recordingSecondsRef.current;
    const m = Math.floor(nowSec / 60);
    const s = nowSec % 60;
    const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

    const newSegment: LiveSegment = {
      id: Math.random().toString(36).substring(2, 9),
      speaker: user?.full_name?.split(" ")[0] || (isHostRef.current ? "Host" : "Participant"),
      text: manualInput.trim(),
      timestamp: timeStr,
      startTimeSec: Math.max(0, nowSec - 2),
      endTimeSec: nowSec,
    };

    setSegments((prev) => [...prev, newSegment]);

    if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
      try {
        signalingSocketRef.current.send(
          JSON.stringify({
            type: "live_transcript_segment",
            segment: newSegment,
          })
        );
      } catch {}
    }

    setManualInput("");
  }

  // Copy Meeting Link
  function copyMeetingLink() {
    const targetId = meeting?.id || meetingId;
    const url =
      targetId && targetId !== "new"
        ? `${window.location.origin}/meetings/${targetId}/room`
        : window.location.href;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  }

  // 8. End Meeting & Finalize Intelligence (Host only - stops master recorder, broadcasts end, uploads 1 recording)
  async function handleEndAndSaveMeeting() {
    const targetId = meeting?.id || Number(meetingId);
    if (!targetId || isNaN(targetId)) {
      releaseAllMediaDevices();
      navigate("/meetings");
      return;
    }

    setIsSavingMeeting(true);
    setSaveProgressMessage("Shutting down camera & microphone...");

    // 1. Broadcast to all participants that host ended the meeting
    if (signalingSocketRef.current && signalingSocketRef.current.readyState === WebSocket.OPEN) {
      try {
        signalingSocketRef.current.send(
          JSON.stringify({
            type: "meeting_ended",
            meetingId: targetId,
          })
        );
      } catch {}
    }

    try {
      // 2. Stop recorder and capture final Blob
      let finalBlob: Blob | null = null;
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        const stopPromise = new Promise<Blob>((resolve) => {
          const timeout = setTimeout(() => {
            resolve(
              new Blob(recordedChunksRef.current, {
                type: mediaRecorderRef.current?.mimeType || "video/webm",
              })
            );
          }, 800);

          mediaRecorderRef.current!.onstop = () => {
            clearTimeout(timeout);
            resolve(
              new Blob(recordedChunksRef.current, {
                type: mediaRecorderRef.current?.mimeType || "video/webm",
              })
            );
          };

          try {
            mediaRecorderRef.current!.requestData();
          } catch {}
          mediaRecorderRef.current!.stop();
        });
        finalBlob = await stopPromise;
      } else if (recordedChunksRef.current.length > 0) {
        finalBlob = new Blob(recordedChunksRef.current, { type: "video/webm" });
      }

      // 3. IMMEDIATELY SHUT DOWN ALL CAMERA & MICROPHONE HARDWARE
      releaseAllMediaDevices();

      // 4. Upload the single whole-meeting master recording file
      if (finalBlob && finalBlob.size > 0) {
        const rawMime = finalBlob.type || "video/webm";
        const cleanMime = rawMime.split(";")[0].trim().toLowerCase() || "video/webm";
        const ext = cleanMime.includes("mp4") ? "mp4" : "webm";
        const fileName = `meeting_${targetId}_recording_${Date.now()}.${ext}`;
        const recordingFile = new File([finalBlob], fileName, { type: cleanMime });

        setSaveProgressMessage(`Uploading whole meeting recording (${(recordingFile.size / (1024 * 1024)).toFixed(1)} MB)...`);
        try {
          await uploadRecording(targetId, recordingFile);
        } catch (uploadErr) {
          console.warn("Upload recording notice:", uploadErr);
        }
      }

      // 5. Save live speech transcripts to database if any were captured live
      if (segments.length > 0) {
        setSaveProgressMessage("Saving speech transcripts...");
        try {
          await saveLiveTranscripts(
            targetId,
            segments.map((s, idx) => ({
              text: s.text,
              speaker_label: s.speaker,
              speaker_name: s.speaker,
              start_time: s.startTimeSec,
              end_time: s.endTimeSec,
              sequence_number: idx + 1,
            }))
          );
        } catch (transcriptErr) {
          console.warn("Live transcript save notice:", transcriptErr);
        }

        // Trigger AI summary in background without blocking navigation
        generateMeetingSummary(targetId, true).catch((sumErr) => {
          console.warn("Async summary generation notice:", sumErr);
        });
      }

      setSaveProgressMessage("Complete! Opening your meeting intelligence workspace...");
      navigate(`/meetings/${targetId}`);
    } catch (err: any) {
      console.error("Failed to finalize meeting:", err);
      releaseAllMediaDevices();
      navigate(`/meetings/${targetId}`);
    } finally {
      setIsSavingMeeting(false);
    }
  }

  // Guest Leave Function (Guest leaves cleanly, does NOT upload duplicate recording)
  function handleLeaveMeeting() {
    releaseAllMediaDevices();
    navigate("/meetings");
  }

  // Format timer
  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const remotePeerList = Array.from(remotePeers.values());
  const totalParticipants = 1 + remotePeerList.length;

  if (error) {
    const isAuthError =
      error.toLowerCase().includes("token") ||
      error.toLowerCase().includes("unauthorized") ||
      error.toLowerCase().includes("credential");

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-6 text-white text-center">
        <AlertCircle className="h-12 w-12 text-red-400" />
        <h2 className="mt-4 text-xl font-bold">
          {isAuthError ? "Sign In Required to Join Room" : "Unable to Join Live Room"}
        </h2>
        <p className="mt-2 text-sm text-slate-400 max-w-md">
          {isAuthError
            ? "Your login session has expired or is invalid. Please sign in with your account to continue into this meeting."
            : error}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {isAuthError ? (
            <button
              onClick={() => {
                releaseAllMediaDevices();
                useAuthStore.getState().logout();
                navigate(`/login?from=${encodeURIComponent(window.location.pathname)}`);
              }}
              className="rounded-xl bg-emerald-600 px-5 py-2.5 font-semibold text-white transition hover:bg-emerald-700 cursor-pointer shadow-lg shadow-emerald-900/30"
            >
              Sign In to Join Meeting
            </button>
          ) : (
            <button
              onClick={() => {
                releaseAllMediaDevices();
                navigate("/meetings");
              }}
              className="rounded-xl bg-emerald-600 px-5 py-2.5 font-semibold text-white transition hover:bg-emerald-700 cursor-pointer"
            >
              Return to Meetings
            </button>
          )}
          <button
            onClick={() => {
              releaseAllMediaDevices();
              navigate("/meetings/new/room");
            }}
            className="rounded-xl bg-slate-800 border border-slate-700 px-5 py-2.5 font-semibold text-slate-200 transition hover:bg-slate-700 cursor-pointer"
          >
            Create New Room
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      {/* Saving / Processing Overlay */}
      {isSavingMeeting && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/85 backdrop-blur-md">
          <div className="flex flex-col items-center rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl max-w-md text-center">
            <Loader2 className="h-12 w-12 animate-spin text-emerald-500" />
            <h3 className="mt-4 text-lg font-bold text-white">Finalizing Meeting</h3>
            <p className="mt-2 text-sm text-slate-300">{saveProgressMessage}</p>
            <span className="mt-4 text-xs text-slate-500">
              Your recording, transcripts, AI summary, action items, and decisions are being organized in your meeting page.
            </span>
          </div>
        </div>
      )}

      {/* Host Ended Meeting Notice for Guests */}
      {hostEndedNotice && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/85 backdrop-blur-md text-white p-6 text-center">
          <div className="flex flex-col items-center rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl max-w-md">
            <PhoneOff className="h-12 w-12 text-red-400 mb-3 animate-pulse" />
            <h3 className="text-lg font-bold text-white">The host has ended this meeting</h3>
            <p className="mt-2 text-sm text-slate-400">
              Opening the meeting workspace where the recording and intelligence are organized...
            </p>
          </div>
        </div>
      )}

      {/* Top Header Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-900/90 px-5 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/meetings")}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-white cursor-pointer"
            title="Back to Meetings"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>

          {/* Editable Meeting Title */}
          <div>
            {isEditingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSaveTitle()}
                  autoFocus
                  className="rounded-lg border border-indigo-500 bg-slate-800 px-2 py-0.5 text-sm font-bold text-white focus:outline-hidden"
                />
                <button
                  onClick={handleSaveTitle}
                  className="rounded p-1 text-emerald-400 hover:bg-slate-800 cursor-pointer"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 group">
                <h1 className="text-sm font-bold text-white sm:text-base leading-none">
                  {meeting?.title || "Live Meeting Room"}
                </h1>
                {meeting && (
                  <button
                    onClick={() => setIsEditingTitle(true)}
                    className="opacity-0 group-hover:opacity-100 transition p-1 text-slate-400 hover:text-white cursor-pointer"
                    title="Rename meeting"
                  >
                    <Edit2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            )}

            <div className="mt-1 flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                Live ({totalParticipants} {totalParticipants === 1 ? "person" : "people"})
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-[11px] font-mono text-slate-400">
                {formatTimer(recordingSeconds)}
              </span>
              {speechActive && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-[10px] text-emerald-400/90 font-medium">Captions active</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Center: Recording Status Badge */}
        {isHost ? (
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs font-semibold text-red-400">
            <span className={`h-2 w-2 rounded-full ${isRecording ? "bg-red-500 animate-ping" : "bg-slate-500"}`} />
            {isRecording ? "REC LIVE • Recording whole meeting" : "Preparing Master Recording..."}
          </div>
        ) : (
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>Participant • Connected</span>
          </div>
        )}

        {/* Right Side: Invite Link & Drawer Toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={copyMeetingLink}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white cursor-pointer"
            title="Copy Meeting Invite Link"
          >
            {copiedLink ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span>Copied Link!</span>
              </>
            ) : (
              <>
                <Share2 className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Invite Others</span>
              </>
            )}
          </button>

          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition cursor-pointer ${
              isSidebarOpen
                ? "border-emerald-500/50 bg-emerald-600/20 text-emerald-300"
                : "border-slate-700 bg-slate-800/70 text-slate-300 hover:bg-slate-700"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">AI Intelligence</span>
          </button>

          <ThemeToggle />
        </div>
      </header>

      {/* Permission Warning Banner if camera/mic blocked */}
      {mediaPermissionDenied && (
        <div className="bg-amber-950/80 border-b border-amber-800/60 px-4 py-2 text-xs text-amber-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-amber-400" />
            <span>Camera or microphone access was not granted. Please allow browser permissions to see your video and capture speech.</span>
          </div>
          <button
            onClick={requestMediaPermissions}
            className="rounded bg-amber-600 px-2.5 py-1 font-semibold text-white hover:bg-amber-700 cursor-pointer"
          >
            Allow Access
          </button>
        </div>
      )}

      {/* Main Workspace Stage + Sidebar */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Video Grid Stage (Google Meet Layout) */}
        <div className="relative flex flex-1 flex-col items-center justify-center p-3 sm:p-5 bg-slate-950 overflow-hidden">
          {/* Echo Prevention Helper Tip when testing multiple participants on same laptop */}
          {totalParticipants > 1 && (
            <div className="absolute top-4 z-20 flex items-center gap-2 rounded-full bg-slate-900/95 border border-indigo-500/50 px-3.5 py-1.5 text-xs text-slate-200 backdrop-blur-md shadow-2xl">
              <Volume2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>
                Testing on 1 laptop? <strong>Click &quot;Mute Speaker&quot; on the participant tile</strong> so your mic doesn&apos;t pick up the speaker audio. (The master recording still captures all voices!)
              </span>
            </div>
          )}
          {/* Presentation Mode (Screen Share active) */}
          {isScreenSharing ? (
            <div className="relative flex h-full w-full flex-col lg:flex-row gap-4">
              {/* Main Shared Screen Canvas */}
              <div className="relative flex flex-1 items-center justify-center overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
                <video
                  ref={screenVideoRef}
                  autoPlay
                  playsInline
                  className="h-full w-full object-contain"
                />
                <div className="absolute top-3 left-3 flex items-center gap-2 rounded-lg bg-black/60 px-3 py-1.5 text-xs text-emerald-400 backdrop-blur-md">
                  <Monitor className="h-3.5 w-3.5" />
                  <span>You are presenting your screen</span>
                </div>
              </div>

              {/* Side Participant Gallery Strip */}
              <div className="flex lg:flex-col gap-3 lg:w-56 shrink-0 overflow-x-auto lg:overflow-y-auto">
                <div className="relative h-32 w-48 lg:w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shrink-0">
                  <video
                    ref={attachLocalStreamToVideo}
                    autoPlay
                    playsInline
                    muted
                    className={`h-full w-full object-cover transform -scale-x-100 ${
                      isVideoOn ? "block" : "hidden"
                    }`}
                  />
                  {!isVideoOn && (
                    <div className="flex h-full w-full items-center justify-center bg-slate-800 text-base font-bold text-white">
                      {user?.full_name?.charAt(0) || "U"}
                    </div>
                  )}
                  <div className="absolute bottom-1.5 left-2 text-[10px] font-semibold text-white/90 drop-shadow">
                    You
                  </div>
                </div>

                {remotePeerList.map((peer) => (
                  <div key={peer.peerId} className="h-32 w-48 lg:w-full shrink-0">
                    <RemoteVideoTile peer={peer} />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Multi-Participant Balanced Video Grid */
            <div
              className={`h-full w-full max-h-[82vh] grid gap-4 ${
                totalParticipants === 1
                  ? "grid-cols-1"
                  : totalParticipants === 2
                  ? "grid-cols-1 md:grid-cols-2"
                  : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-2"
              }`}
            >
              {/* Local Participant Tile (Your Camera Feed) */}
              <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl min-h-[220px]">
                <video
                  ref={localVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`h-full w-full object-cover transform -scale-x-100 ${
                    isVideoOn ? "block" : "hidden"
                  }`}
                />
                {!isVideoOn && (
                  <div className="flex flex-col items-center justify-center">
                    <div
                      className={`relative flex h-24 w-24 items-center justify-center rounded-full text-2xl font-extrabold text-white transition-all duration-300 ${
                        isSpeaking
                          ? "bg-emerald-600 ring-8 ring-emerald-500/30 scale-105"
                          : "bg-slate-800 ring-4 ring-slate-700/50"
                      }`}
                    >
                      {user?.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
                      {isSpeaking && (
                        <span className="absolute -bottom-1 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-black">
                          Speaking
                        </span>
                      )}
                    </div>
                    <span className="mt-3 text-sm font-semibold text-slate-200">
                      {user?.full_name || "You"} (Host)
                    </span>
                    <span className="mt-0.5 text-[11px] text-slate-500">Camera is off</span>
                  </div>
                )}

                {/* Local user badge */}
                <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-black/60 px-2.5 py-1 text-xs text-white backdrop-blur-md">
                  <span>{user?.full_name?.split(" ")[0] || "You"} (You)</span>
                  {isMicOn ? (
                    <div
                      className={`h-2 w-2 rounded-full ${
                        isSpeaking ? "bg-emerald-400 animate-pulse" : "bg-slate-400"
                      }`}
                    />
                  ) : (
                    <MicOff className="h-3 w-3 text-red-400" />
                  )}
                </div>

                {/* If alone in the room: Google Meet-style invite helper */}
                {totalParticipants === 1 && (
                  <div className="absolute top-3 right-3 flex items-center gap-2 rounded-xl bg-slate-900/80 border border-slate-700/80 px-3 py-1.5 text-xs text-slate-300 backdrop-blur-md shadow-lg">
                    <Users className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Waiting for others to join</span>
                    <button
                      onClick={copyMeetingLink}
                      className="ml-1 rounded-md bg-emerald-600 px-2 py-0.5 text-[11px] font-bold text-white hover:bg-emerald-700 cursor-pointer"
                    >
                      Copy Link
                    </button>
                  </div>
                )}
              </div>

              {/* Remote Participants' Tiles */}
              {remotePeerList.map((peer) => (
                <RemoteVideoTile key={peer.peerId} peer={peer} />
              ))}
            </div>
          )}

          {/* Real-time Floating Subtitles / Captions (Over video) */}
          {isCaptionsOn && (interimText || (segments.length > 0 && segments[segments.length - 1])) && (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 max-w-xl w-[90%] rounded-xl bg-black/85 px-4 py-2.5 text-center text-sm text-white backdrop-blur-md border border-white/10 shadow-xl pointer-events-none transition-all z-10">
              <span className="font-semibold text-emerald-300">
                {interimText
                  ? `${user?.full_name?.split(" ")[0] || "You"}: `
                  : `${segments[segments.length - 1]?.speaker}: `}
              </span>
              <span className="text-slate-100">
                {interimText || segments[segments.length - 1]?.text}
              </span>
            </div>
          )}
        </div>

        {/* Right: Expandable AI Intelligence & Live Transcript Drawer */}
        {isSidebarOpen && (
          <aside className="w-80 sm:w-96 shrink-0 border-l border-slate-800 bg-slate-900/95 flex flex-col justify-between">
            {/* Tab Headers */}
            <div className="border-b border-slate-800 p-2">
              <div className="grid grid-cols-4 gap-1 rounded-xl bg-slate-950 p-1">
                <button
                  onClick={() => setActiveTab("transcript")}
                  className={`rounded-lg py-1.5 text-[11px] font-bold transition cursor-pointer ${
                    activeTab === "transcript"
                      ? "bg-emerald-600 text-white shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Captions
                </button>
                <button
                  onClick={() => setActiveTab("actions")}
                  className={`rounded-lg py-1.5 text-[11px] font-bold transition cursor-pointer relative ${
                    activeTab === "actions"
                      ? "bg-emerald-600 text-white shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Actions
                  {actionItems.length > 0 && (
                    <span className="ml-1 rounded-full bg-emerald-500/20 text-emerald-400 px-1 py-0.2 text-[9px]">
                      {actionItems.length}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setActiveTab("decisions")}
                  className={`rounded-lg py-1.5 text-[11px] font-bold transition cursor-pointer relative ${
                    activeTab === "decisions"
                      ? "bg-emerald-600 text-white shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Decisions
                  {decisions.length > 0 && (
                    <span className="ml-1 rounded-full bg-purple-500/20 text-purple-400 px-1 py-0.2 text-[9px]">
                      {decisions.length}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setActiveTab("notes")}
                  className={`rounded-lg py-1.5 text-[11px] font-bold transition cursor-pointer ${
                    activeTab === "notes"
                      ? "bg-emerald-600 text-white shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Notes
                </button>
              </div>
            </div>

            {/* Tab Body */}
            <div className="flex-1 overflow-y-auto p-4" ref={transcriptScrollRef}>
              {/* Tab 1: Live Transcript */}
              {activeTab === "transcript" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between pb-1">
                    <span className="text-xs font-semibold text-slate-400">Live Speech Feed</span>
                    <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                      Listening in background
                    </span>
                  </div>

                  {/* Browser Permission Alert for Speech Recognition */}
                  {speechPermissionNotice && (
                    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
                      <p className="font-semibold text-amber-300">Live Captions Notice</p>
                      <p className="mt-1 text-[11px] text-amber-200/90 leading-relaxed">
                        Browser speech recognition requires a click to activate. Click the button below to turn on live captions.
                      </p>
                      <button
                        onClick={startCaptionsWithUserGesture}
                        className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 cursor-pointer shadow-xs"
                      >
                        <Mic className="h-3.5 w-3.5" />
                        Enable Live Captions
                      </button>
                    </div>
                  )}

                  {segments.length === 0 && !interimText && (
                    <div className="flex flex-col items-center justify-center py-12 text-center text-slate-500">
                      <Subtitles className="h-8 w-8 text-slate-600 mb-2" />
                      <p className="text-xs font-semibold text-slate-400">Speak into your microphone</p>
                      <p className="mt-1 text-[11px] text-slate-500 leading-relaxed max-w-xs">
                        Speech will appear live with timestamps and speaker tags, and will be saved automatically when the meeting ends.
                      </p>
                    </div>
                  )}

                  {segments.map((seg) => (
                    <div
                      key={seg.id}
                      className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs shadow-xs"
                    >
                      <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                        <span className="font-bold text-emerald-400">{seg.speaker}</span>
                        <span className="font-mono text-[10px] text-slate-500">{seg.timestamp}</span>
                      </div>
                      <p className="text-slate-200 leading-relaxed">{seg.text}</p>
                    </div>
                  ))}

                  {/* Real-time interim preview */}
                  {interimText && (
                    <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-3 text-xs italic text-emerald-200 animate-pulse">
                      <span className="font-bold text-emerald-400 not-italic mr-1.5">
                        {user?.full_name?.split(" ")[0] || "You"}:
                      </span>
                      {interimText}...
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Live Action Items */}
              {activeTab === "actions" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Live Action Items</span>
                    <button
                      onClick={triggerInsightsAnalysis}
                      disabled={isAnalyzingInsights}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 disabled:opacity-50 cursor-pointer"
                    >
                      <RefreshCw className={`h-3 w-3 ${isAnalyzingInsights ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  </div>

                  {actionItems.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center text-slate-500">
                      <CheckSquare className="h-8 w-8 text-slate-600 mb-2" />
                      <p className="text-xs">No action items detected yet.</p>
                      <p className="mt-1 text-[11px] text-slate-600">
                        Discuss tasks (e.g. "I will prepare the presentation by Friday") and AI extracts them in real time.
                      </p>
                    </div>
                  ) : (
                    actionItems.map((item, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-xs shadow-xs"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                          <span
                            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                              item.priority === "high"
                                ? "bg-red-500/20 text-red-400"
                                : item.priority === "low"
                                ? "bg-slate-700 text-slate-300"
                                : "bg-amber-500/20 text-amber-400"
                            }`}
                          >
                            {item.priority}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            Assignee: <strong className="text-slate-200">{item.assignee_name || "Unassigned"}</strong>
                          </span>
                        </div>
                        <p className="text-slate-200">{item.description}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 3: Live Decisions */}
              {activeTab === "decisions" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400">Live Decisions & Consensus</span>
                    <button
                      onClick={triggerInsightsAnalysis}
                      disabled={isAnalyzingInsights}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 disabled:opacity-50 cursor-pointer"
                    >
                      <RefreshCw className={`h-3 w-3 ${isAnalyzingInsights ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  </div>

                  {decisions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center text-slate-500">
                      <Milestone className="h-8 w-8 text-slate-600 mb-2" />
                      <p className="text-xs">No decisions recorded yet.</p>
                      <p className="mt-1 text-[11px] text-slate-600">
                        When the group reaches an agreement (e.g. "We decided to launch on Monday"), AI logs it here.
                      </p>
                    </div>
                  ) : (
                    decisions.map((dec, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-purple-900/30 bg-purple-950/20 p-3 text-xs shadow-xs"
                      >
                        <span className="rounded-md bg-purple-500/20 px-1.5 py-0.5 text-[10px] font-bold text-purple-300 uppercase">
                          {dec.decision_type || "Decision"}
                        </span>
                        <p className="mt-2 text-slate-200">{dec.description}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 4: Meeting Notes */}
              {activeTab === "notes" && (
                <div className="h-full flex flex-col">
                  <span className="text-xs font-semibold text-slate-400 mb-2">Scratchpad Notes</span>
                  <textarea
                    value={meetingNotes}
                    onChange={(e) => setMeetingNotes(e.target.value)}
                    placeholder="Type in-meeting observations, ideas, or agenda items here..."
                    className="flex-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-hidden resize-none"
                  />
                </div>
              )}
            </div>

            {/* Bottom Input for adding a manual speech point */}
            <form
              onSubmit={handleAddManualSegment}
              className="border-t border-slate-800 p-3 bg-slate-950/80 flex items-center gap-2"
            >
              <input
                type="text"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                placeholder="Say or type something..."
                className="flex-1 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-hidden"
              />
              <button
                type="submit"
                disabled={!manualInput.trim()}
                className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50 cursor-pointer"
              >
                Send
              </button>
            </form>
          </aside>
        )}
      </div>

      {/* Bottom Meeting Controls Bar (Google Meet Style) */}
      <footer className="flex h-20 shrink-0 items-center justify-between border-t border-slate-800/80 bg-slate-900 px-6 backdrop-blur-md">
        {/* Left: Meeting Details & Info */}
        <div className="hidden md:flex items-center gap-3">
          <div className="text-left">
            <div className="text-xs font-bold text-white">{meeting?.title || "Live Session"}</div>
            <div className="text-[11px] text-slate-400 font-mono">
              Room Code: meet-{meeting?.id || "..."} • {formatTimer(recordingSeconds)}
            </div>
          </div>
        </div>

        {/* Center: Device Controls */}
        <div className="flex items-center gap-3 mx-auto">
          {/* Microphone Button */}
          <button
            onClick={toggleMic}
            className={`flex h-12 w-12 items-center justify-center rounded-full transition shadow-md cursor-pointer ${
              isMicOn
                ? "bg-slate-800 text-white hover:bg-slate-700"
                : "bg-red-600 text-white hover:bg-red-700 ring-2 ring-red-400/40"
            }`}
            title={isMicOn ? "Mute Microphone" : "Unmute Microphone"}
          >
            {isMicOn ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
          </button>

          {/* Camera Button */}
          <button
            onClick={toggleCamera}
            className={`flex h-12 w-12 items-center justify-center rounded-full transition shadow-md cursor-pointer ${
              isVideoOn
                ? "bg-slate-800 text-white hover:bg-slate-700"
                : "bg-red-600 text-white hover:bg-red-700 ring-2 ring-red-400/40"
            }`}
            title={isVideoOn ? "Turn Off Camera" : "Turn On Camera"}
          >
            {isVideoOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
          </button>

          {/* Screen Share Button */}
          <button
            onClick={toggleScreenShare}
            className={`flex h-12 w-12 items-center justify-center rounded-full transition shadow-md cursor-pointer ${
              isScreenSharing
                ? "bg-emerald-600 text-white hover:bg-emerald-700 ring-2 ring-emerald-400/40"
                : "bg-slate-800 text-white hover:bg-slate-700"
            }`}
            title={isScreenSharing ? "Stop Screen Share" : "Share Screen"}
          >
            {isScreenSharing ? <MonitorOff className="h-5 w-5" /> : <Monitor className="h-5 w-5" />}
          </button>

          {/* Captions Toggle */}
          <button
            onClick={toggleCaptions}
            className={`flex h-12 w-12 items-center justify-center rounded-full transition shadow-md cursor-pointer ${
              isCaptionsOn
                ? "bg-emerald-600/30 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-600/40"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white"
            }`}
            title={isCaptionsOn ? "Hide Captions" : "Turn On Live Captions"}
          >
            <Subtitles className="h-5 w-5" />
          </button>

          {/* End Call / Leave Meeting */}
          {isHost ? (
            <button
              onClick={handleEndAndSaveMeeting}
              className="flex items-center gap-2 rounded-full bg-red-600 px-5 py-3 font-semibold text-white shadow-lg transition hover:bg-red-700 active:scale-95 cursor-pointer ml-2"
              title="End Meeting for all & Save Master Recording"
            >
              <PhoneOff className="h-5 w-5" />
              <span className="hidden sm:inline">End & Save Meeting</span>
            </button>
          ) : (
            <button
              onClick={handleLeaveMeeting}
              className="flex items-center gap-2 rounded-full bg-slate-800 border border-slate-700 px-5 py-3 font-semibold text-red-400 shadow-lg transition hover:bg-red-950/50 hover:text-red-300 active:scale-95 cursor-pointer ml-2"
              title="Leave Room"
            >
              <PhoneOff className="h-5 w-5" />
              <span className="hidden sm:inline">Leave Room</span>
            </button>
          )}
        </div>

        {/* Right: Drawer Button */}
        <div className="hidden md:flex items-center gap-2">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`flex h-10 w-10 items-center justify-center rounded-xl transition cursor-pointer ${
              isSidebarOpen
                ? "bg-emerald-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white"
            }`}
            title="Toggle Live Intelligence Panel"
          >
            <Sparkles className="h-5 w-5" />
          </button>
        </div>
      </footer>
    </div>
  );
}
