"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { api, audioUrl } from "@/lib/api";
import type { InterviewInterface, InterviewState, RespondResponse } from "@/lib/types";

type UIState = "loading" | "ai_speaking" | "ai_thinking" | "waiting" | "recording" | "transcribing" | "paused";

interface ChatMessage {
  role: "interviewer" | "candidate";
  text: string;
  isProbe?: boolean;
}

const STATE_LABELS: Record<string, string> = {
  OPENING: "开场",
  BEHAVIORAL: "行为面试",
  DEEP_DIVE: "深度追问",
  TECHNICAL: "技术面试",
  CLOSING: "结束",
  COMPLETED: "已完成",
};

const PERSONA_NAMES: Record<string, { name: string; title: string }> = {
  sarah: { name: "Sarah Chen", title: "高级HR经理" },
  marcus: { name: "Marcus Liu", title: "技术总监" },
  alex: { name: "Alex Wang", title: "产品VP" },
};

const PERSONA_EMOJIS: Record<string, string> = {
  sarah: "👩‍💼",
  marcus: "👨‍💻",
  alex: "🧑‍🎨",
};

export default function InterviewRoomPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [uiState, setUiState] = useState<UIState>("loading");
  const [interviewState, setInterviewState] = useState<InterviewState>("INIT");
  const [interviewInterface, setInterviewInterface] = useState<InterviewInterface>("voice");
  const [questionCount, setQuestionCount] = useState(0);
  const [maxQuestions] = useState(8);
  const [isProbe, setIsProbe] = useState(false);
  const [subtitle, setSubtitle] = useState(""); // voice mode text display
  const [messages, setMessages] = useState<ChatMessage[]>([]); // text mode chat
  const [textInput, setTextInput] = useState("");
  const [persona, setPersona] = useState("sarah");
  const [elapsed, setElapsed] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [showEndDialog, setShowEndDialog] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Timer
  useEffect(() => {
    timerRef.current = setInterval(() => {
      if (!isPaused) setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPaused]);

  // Scroll chat to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function playAudio(url: string, onEnd?: () => void) {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
    }
    audioRef.current = new Audio(audioUrl(url));
    audioRef.current.onended = onEnd ?? null;
    audioRef.current.play().catch((err) => {
      console.error("Audio play failed:", err);
      onEnd?.(); // advance state even if audio is blocked or fails
    });
  }

  const handleRespond = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setUiState("ai_thinking");
    setSubtitle(text); // voice mode: show candidate text briefly

    // Text mode: add candidate message
    setMessages(prev => [...prev, { role: "candidate", text }]);

    try {
      const res: RespondResponse = await api.respond(sessionId, text);
      setInterviewState(res.state);
      setQuestionCount(res.question_count);
      setIsProbe(res.is_probe);

      const addInterviewerMsg = () => {
        setMessages(prev => [...prev, {
          role: "interviewer",
          text: res.interviewer_text,
          isProbe: res.is_probe,
        }]);
      };

      if (res.should_end) {
        setSubtitle(res.interviewer_text);
        addInterviewerMsg();
        setUiState("ai_speaking");
        playAudio(res.audio_url, async () => {
          await api.finalize(sessionId);
          router.push(`/feedback/${sessionId}`);
        });
        return;
      }

      setSubtitle(res.interviewer_text);
      addInterviewerMsg();
      setUiState("ai_speaking");
      playAudio(res.audio_url, () => {
        setSubtitle("");
        setUiState("waiting");
      });
    } catch (e) {
      console.error(e);
      setUiState("waiting");
    }
  }, [sessionId, router]);

  // Load session and start interview
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const session = await api.getSession(sessionId);
        if (cancelled) return;
        setPersona(session.persona);
        setInterviewInterface(session.interview_interface ?? "voice");

        const start = await api.startInterview(sessionId);
        if (cancelled) return;
        setInterviewState(start.state);
        setQuestionCount(start.question_count);
        setSubtitle(start.interviewer_text);
        setMessages([{ role: "interviewer", text: start.interviewer_text }]);
        if (start.audio_url) {
          setUiState("ai_speaking");
          playAudio(start.audio_url, () => {
            setSubtitle("");
            setUiState("waiting");
          });
        } else {
          setUiState("waiting");
        }
      } catch (e) {
        if (!cancelled) console.error(e);
      }
    }

    init();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── MediaRecorder recording ───────────────────────────────────────────────

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      const mr = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const ext = mimeType.startsWith("audio/mp4") ? "mp4" : "webm";
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setUiState("transcribing");
        try {
          const { transcript } = await api.transcribe(sessionId, blob, ext);
          if (transcript.trim()) {
            await handleRespond(transcript);
          } else {
            setUiState("waiting");
          }
        } catch (err) {
          console.error("Transcribe error:", err);
          setUiState("waiting");
        }
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setUiState("recording");
    } catch (err) {
      console.error("Mic error:", err);
      // Mic not available — fall back to waiting
      setUiState("waiting");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
  }

  function toggleMic() {
    if (uiState === "waiting") startRecording();
    else if (uiState === "recording") stopRecording();
  }

  // ── Text input send ───────────────────────────────────────────────────────

  function sendText() {
    const text = textInput.trim();
    if (!text || uiState !== "waiting") return;
    setTextInput("");
    handleRespond(text);
  }

  // ── Misc controls ─────────────────────────────────────────────────────────

  async function togglePause() {
    if (!isPaused) {
      await api.pause(sessionId);
      audioRef.current?.pause();
      setIsPaused(true);
      setUiState("paused");
    } else {
      await api.resume(sessionId);
      audioRef.current?.play().catch(() => {});
      setIsPaused(false);
      setUiState("waiting");
    }
  }

  async function replayAudio() {
    try {
      const { audio_url } = await api.replayAudio(sessionId);
      playAudio(audio_url, () => setUiState("waiting"));
      setUiState("ai_speaking");
    } catch {}
  }

  async function confirmEndInterview() {
    setShowEndDialog(false);
    setUiState("ai_thinking");
    try {
      await api.finalize(sessionId);
      router.push(`/feedback/${sessionId}`);
    } catch (e) {
      console.error(e);
      setUiState("waiting");
    }
  }

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const avatarRing =
    uiState === "ai_speaking"
      ? "ring-4 ring-[#6366F1] ring-offset-2 animate-pulse"
      : isProbe
      ? "ring-4 ring-[#F59E0B] ring-offset-2"
      : uiState === "ai_thinking" || uiState === "transcribing"
      ? "ring-4 ring-[#6366F1]/40 ring-offset-2"
      : "";

  const pInfo = PERSONA_NAMES[persona] ?? { name: "Sarah Chen", title: "高级HR经理" };
  const isVoice = interviewInterface === "voice";
  const canInteract = uiState === "waiting" || uiState === "recording";

  return (
    <div className="h-screen bg-[#F8F9FF] flex flex-col overflow-hidden select-none">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[#E5E7EB] bg-white shadow-sm flex-shrink-0">
        <span className="font-bold text-[#6366F1]">MockMate</span>
        <div className="text-sm text-[#6B7280] font-medium">
          第{questionCount}题 · {STATE_LABELS[interviewState] ?? interviewState}
        </div>
        <div className="flex items-center gap-3">
          <div className="text-sm text-[#6B7280] font-mono">⏱ {formatTime(elapsed)}</div>
          <button
            onClick={() => setShowEndDialog(true)}
            className="text-xs text-[#EF4444] border border-[#EF4444]/30 hover:bg-[#FEF2F2] px-3 py-1.5 rounded-lg transition-colors"
          >
            结束面试
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="px-6 py-2 bg-white border-b border-[#E5E7EB] flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-[#9CA3AF]">
          <span className="text-[#10B981] font-medium">开场</span>
          <div className="flex-1 h-1.5 bg-[#E5E7EB] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#6366F1] rounded-full transition-all"
              style={{ width: `${(questionCount / maxQuestions) * 100}%` }}
            />
          </div>
          <span className="text-[#374151] font-medium">技术</span>
        </div>
      </div>

      {isVoice ? (
        /* ── Voice Mode Layout ───────────────────────────────────────────── */
        <>
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-8 overflow-hidden">
            <div className={`w-32 h-32 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-5xl mb-4 transition-all ${avatarRing}`}>
              {PERSONA_EMOJIS[persona] ?? "👩‍💼"}
            </div>
            <p className="font-semibold text-[#111827] text-lg">{pInfo.name}</p>
            <p className="text-sm text-[#6B7280] mb-2">{pInfo.title}</p>

            {isProbe && (
              <span className="bg-[#FEF3C7] text-[#D97706] text-xs font-medium px-3 py-1 rounded-full mb-2 border border-[#F59E0B]/30">
                🔶 追问
              </span>
            )}

            <div className="w-full max-w-lg min-h-[80px] flex items-center justify-center mt-6">
              {uiState === "ai_thinking" ? (
                <div className="flex items-center gap-2 text-[#6B7280]">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-sm">AI 思考中...</span>
                </div>
              ) : uiState === "transcribing" ? (
                <div className="flex items-center gap-2 text-[#6B7280]">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-[#10B981] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-[#10B981] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-[#10B981] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-sm">语音转文字中...</span>
                </div>
              ) : subtitle ? (
                <p className="text-center text-[#111827] text-base leading-relaxed">{subtitle}</p>
              ) : uiState === "recording" ? (
                <p className="text-center text-[#EF4444] text-base italic animate-pulse">● 录音中，点击停止</p>
              ) : null}
            </div>
          </div>

          <div className="bg-white border-t border-[#E5E7EB] px-6 py-4 flex-shrink-0">
            <div className="flex items-center justify-center gap-8">
              <button
                onClick={replayAudio}
                disabled={!canInteract}
                className="flex flex-col items-center gap-1 text-[#6B7280] hover:text-[#6366F1] disabled:text-[#D1D5DB] transition-colors"
              >
                <div className="w-10 h-10 rounded-full border border-current flex items-center justify-center text-lg">↺</div>
                <span className="text-xs">重播</span>
              </button>

              <button
                onClick={toggleMic}
                disabled={!canInteract}
                className={`w-16 h-16 rounded-full flex items-center justify-center text-2xl transition-all shadow-md ${
                  uiState === "recording"
                    ? "bg-[#EF4444] text-white animate-pulse"
                    : canInteract
                    ? "bg-[#6366F1] text-white hover:bg-[#4F46E5]"
                    : "bg-[#E5E7EB] text-[#9CA3AF] cursor-not-allowed"
                }`}
              >
                {uiState === "recording" ? "⏹" : "🎙️"}
              </button>

              <button
                onClick={togglePause}
                className="flex flex-col items-center gap-1 text-[#6B7280] hover:text-[#6366F1] transition-colors"
              >
                <div className="w-10 h-10 rounded-full border border-current flex items-center justify-center text-lg">
                  {isPaused ? "▶" : "⏸"}
                </div>
                <span className="text-xs">{isPaused ? "继续" : "暂停"}</span>
              </button>
            </div>

            {uiState === "waiting" && (
              <p className="text-center text-xs text-[#9CA3AF] mt-3">点击麦克风开始录音，再次点击停止并发送</p>
            )}
          </div>
        </>
      ) : (
        /* ── Text Mode Layout ────────────────────────────────────────────── */
        <>
          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "candidate" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "interviewer" && (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-sm mr-2 flex-shrink-0 mt-0.5">
                    {PERSONA_EMOJIS[persona] ?? "👩‍💼"}
                  </div>
                )}
                <div className={`max-w-[75%] ${msg.role === "candidate" ? "" : ""}`}>
                  {msg.isProbe && (
                    <span className="text-xs text-[#D97706] font-medium mb-1 block">🔶 追问</span>
                  )}
                  <div
                    className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      msg.role === "interviewer"
                        ? "bg-white border border-[#E5E7EB] text-[#111827] rounded-tl-sm"
                        : "bg-[#6366F1] text-white rounded-tr-sm"
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              </div>
            ))}

            {/* Thinking indicator */}
            {(uiState === "ai_thinking" || uiState === "transcribing") && (
              <div className="flex justify-start">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center text-sm mr-2 flex-shrink-0">
                  {PERSONA_EMOJIS[persona] ?? "👩‍💼"}
                </div>
                <div className="bg-white border border-[#E5E7EB] px-4 py-3 rounded-2xl rounded-tl-sm">
                  <div className="flex gap-1 items-center">
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Text input */}
          <div className="bg-white border-t border-[#E5E7EB] px-4 py-3 flex-shrink-0">
            <div className="flex items-end gap-2">
              {/* Mic button for voice-to-text in text mode */}
              <button
                onClick={toggleMic}
                disabled={!canInteract}
                title="语音输入"
                className={`w-10 h-10 rounded-full flex items-center justify-center text-lg transition-all flex-shrink-0 ${
                  uiState === "recording"
                    ? "bg-[#EF4444] text-white animate-pulse"
                    : canInteract
                    ? "bg-[#EEF2FF] text-[#6366F1] hover:bg-[#E0E7FF]"
                    : "bg-[#F3F4F6] text-[#D1D5DB] cursor-not-allowed"
                }`}
              >
                {uiState === "recording" ? "⏹" : "🎙️"}
              </button>

              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendText();
                  }
                }}
                disabled={uiState !== "waiting"}
                rows={1}
                placeholder={
                  uiState === "recording"
                    ? "录音中... 点击停止按钮结束录音"
                    : uiState === "transcribing"
                    ? "转录中..."
                    : uiState === "waiting"
                    ? "输入回答，或点击麦克风语音输入 (Enter 发送)"
                    : "等待面试官..."
                }
                className="flex-1 border border-[#E5E7EB] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#6366F1] resize-none disabled:bg-[#F9FAFB] disabled:text-[#9CA3AF] transition-colors"
              />

              <button
                onClick={sendText}
                disabled={uiState !== "waiting" || !textInput.trim()}
                className="w-10 h-10 bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] text-white disabled:text-[#9CA3AF] rounded-full flex items-center justify-center text-lg transition-colors flex-shrink-0"
              >
                ↑
              </button>
            </div>
          </div>
        </>
      )}

      {/* Pause overlay */}
      {isPaused && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 text-center shadow-xl">
            <p className="text-2xl font-bold text-[#111827] mb-2">已暂停</p>
            <p className="text-[#6B7280] text-sm mb-6">关闭浏览器将结束本场面试</p>
            <button
              onClick={togglePause}
              className="bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold px-8 py-3 rounded-xl transition-colors"
            >
              继续面试
            </button>
          </div>
        </div>
      )}

      {/* End interview confirmation dialog */}
      {showEndDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 text-center shadow-xl max-w-sm mx-4">
            <p className="text-xl font-bold text-[#111827] mb-2">确认结束面试？</p>
            <p className="text-[#6B7280] text-sm mb-6">
              将根据已完成的 {questionCount} 道题生成面试报告
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowEndDialog(false)}
                className="flex-1 border border-[#E5E7EB] text-[#374151] font-semibold py-3 rounded-xl hover:bg-[#F9FAFB] transition-colors"
              >
                继续面试
              </button>
              <button
                onClick={confirmEndInterview}
                className="flex-1 bg-[#EF4444] hover:bg-[#DC2626] text-white font-semibold py-3 rounded-xl transition-colors"
              >
                结束并生成报告
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
