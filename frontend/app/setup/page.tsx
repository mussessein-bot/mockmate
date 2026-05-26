"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, audioUrl } from "@/lib/api";
import type { Language, InterviewType, InterviewMode, InterviewInterface, PersonaType } from "@/lib/types";

const PERSONAS = [
  {
    id: "sarah" as PersonaType,
    name: "Sarah Chen",
    title: "高级HR经理",
    titleEn: "Senior HR Manager",
    style: "温和引导，善于挖掘亮点",
    styleEn: "Warm & encouraging",
    color: "border-emerald-400",
    bg: "bg-emerald-50",
    emoji: "👩‍💼",
  },
  {
    id: "marcus" as PersonaType,
    name: "Marcus Liu",
    title: "技术总监",
    titleEn: "Tech Director",
    style: "直接犀利，零容忍模糊",
    styleEn: "Direct & demanding",
    color: "border-red-400",
    bg: "bg-red-50",
    emoji: "👨‍💻",
  },
  {
    id: "alex" as PersonaType,
    name: "Alex Wang",
    title: "产品VP",
    titleEn: "Product VP",
    style: "节奏快，喜欢情景假设",
    styleEn: "Fast-paced & hypothetical",
    color: "border-violet-400",
    bg: "bg-violet-50",
    emoji: "🧑‍🎨",
  },
];

const INTERVIEW_TYPES = [
  {
    id: "behavioral" as InterviewType,
    label: "公司行为面",
    labelEn: "Behavioral",
    desc: "STAR法则，考察过往经历与软技能",
  },
  {
    id: "technical" as InterviewType,
    label: "技术专项面",
    labelEn: "Technical",
    desc: "技术深度、系统设计、逻辑分析",
  },
  {
    id: "graduate" as InterviewType,
    label: "研究生招生面",
    labelEn: "Graduate",
    desc: "科研经历、学术动机、未来规划",
  },
];

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [language, setLanguage] = useState<Language>("zh");
  const [name, setName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const [interviewType, setInterviewType] = useState<InterviewType>("behavioral");
  const [interviewMode, setInterviewMode] = useState<InterviewMode>("preset");
  const [interviewInterface, setInterviewInterface] = useState<InterviewInterface>("voice");
  const [persona, setPersona] = useState<PersonaType | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const zh = language === "zh";

  async function handlePdfUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPdfLoading(true);
    setPdfError("");
    try {
      const { text } = await api.parsePdf(file);
      setResumeText(text);
    } catch (err) {
      setPdfError(zh ? "PDF解析失败，请手动粘贴" : "PDF parse failed, please paste manually");
      console.error(err);
    } finally {
      setPdfLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function playPreview(personaId: string) {
    setPreviewLoading(personaId);
    try {
      const { audio_url } = await api.ttsPreview(personaId, language);
      if (audioRef.current) audioRef.current.pause();
      audioRef.current = new Audio(audioUrl(audio_url));
      audioRef.current.play();
    } catch {
      // ignore
    } finally {
      setPreviewLoading(null);
    }
  }

  async function handleStart() {
    if (!persona) return;
    setLoading(true);
    try {
      const { session_id } = await api.createSession({
        name,
        target_role: targetRole,
        resume_text: resumeText || undefined,
        language,
        interview_type: interviewType,
        interview_mode: interviewMode,
        interview_interface: interviewInterface,
        persona,
      });
      router.push(`/interview/${session_id}?interface=${interviewInterface}`);
    } finally {
      setLoading(false);
    }
  }

  const stepUnlocked = [
    true,
    step >= 1,
    step >= 2 && name.trim().length > 0 && targetRole.trim().length > 0,
    step >= 3,
  ];

  return (
    <div className="min-h-screen bg-[#FAFAFA] py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <span className="text-2xl font-bold text-[#6366F1]">MockMate</span>
          <p className="text-[#6B7280] mt-1 text-sm">面试前准备</p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-2 mb-10">
          {["语言", "基本信息", "面试设置", "选择面试官"].map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                  step === i
                    ? "bg-[#6366F1] text-white"
                    : step > i
                    ? "bg-[#10B981] text-white"
                    : "bg-[#E5E7EB] text-[#9CA3AF]"
                }`}
              >
                {step > i ? "✓" : i + 1}
              </div>
              {i < 3 && <div className={`w-8 h-px ${step > i ? "bg-[#10B981]" : "bg-[#E5E7EB]"}`} />}
            </div>
          ))}
        </div>

        {/* Step 0: Language */}
        <StepCard title={zh ? "选择语言" : "Select Language"} active={step === 0}>
          <div className="grid grid-cols-2 gap-4">
            {(["zh", "en"] as Language[]).map((l) => (
              <button
                key={l}
                onClick={() => { setLanguage(l); setStep(1); }}
                className={`p-6 rounded-xl border-2 text-center transition-all ${
                  language === l
                    ? "border-[#6366F1] bg-[#EEF2FF]"
                    : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/50"
                }`}
              >
                <div className="text-3xl mb-2">{l === "zh" ? "🇨🇳" : "🇺🇸"}</div>
                <div className="font-semibold text-[#111827]">
                  {l === "zh" ? "中文" : "English"}
                </div>
              </button>
            ))}
          </div>
        </StepCard>

        {/* Step 1: Profile */}
        {stepUnlocked[1] && (
          <StepCard title={zh ? "基本信息" : "Your Information"} active={step === 1}>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-[#374151] block mb-1">
                  {zh ? "姓名" : "Name"} *
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={zh ? "你的姓名" : "Your name"}
                  className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-[#374151] block mb-1">
                  {zh ? "目标职位" : "Target Role"} *
                </label>
                <input
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                  placeholder={zh ? "如：产品经理、前端工程师" : "e.g. Product Manager, Frontend Engineer"}
                  className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-[#374151]">
                    {zh ? "简历内容（可选）" : "Resume (optional)"}
                  </label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={pdfLoading}
                    className="text-xs bg-[#EEF2FF] hover:bg-[#E0E7FF] text-[#6366F1] px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {pdfLoading
                      ? (zh ? "解析中..." : "Parsing...")
                      : (zh ? "上传 PDF" : "Upload PDF")}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handlePdfUpload}
                  />
                </div>
                {pdfError && (
                  <p className="text-xs text-red-500 mb-1">{pdfError}</p>
                )}
                <textarea
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  rows={4}
                  placeholder={zh ? "粘贴简历文本，或上传 PDF 自动解析，可跳过" : "Paste resume text, or upload PDF to auto-parse"}
                  className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors resize-none"
                />
              </div>
              <button
                disabled={!name.trim() || !targetRole.trim()}
                onClick={() => setStep(2)}
                className="w-full bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF] text-white font-semibold py-3 rounded-xl transition-colors"
              >
                {zh ? "下一步" : "Next"}
              </button>
            </div>
          </StepCard>
        )}

        {/* Step 2: Type + Mode + Interface */}
        {stepUnlocked[2] && (
          <StepCard title={zh ? "面试类型与模式" : "Interview Type & Mode"} active={step === 2}>
            <div className="space-y-6">
              <div>
                <p className="text-sm font-medium text-[#374151] mb-3">
                  {zh ? "面试类型" : "Interview Type"}
                </p>
                <div className="space-y-3">
                  {INTERVIEW_TYPES.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setInterviewType(t.id)}
                      className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                        interviewType === t.id
                          ? "border-[#6366F1] bg-[#EEF2FF]"
                          : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/50"
                      }`}
                    >
                      <div className="font-semibold text-[#111827] text-sm">
                        {zh ? t.label : t.labelEn}
                      </div>
                      <div className="text-xs text-[#6B7280] mt-0.5">{t.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-[#374151] mb-3">
                  {zh ? "面试模式" : "Interview Mode"}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {(["preset", "dynamic"] as InterviewMode[]).map((m) => (
                    <button
                      key={m}
                      onClick={() => setInterviewMode(m)}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        interviewMode === m
                          ? "border-[#6366F1] bg-[#EEF2FF]"
                          : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/50"
                      }`}
                    >
                      <div className="font-semibold text-sm text-[#111827]">
                        {m === "preset"
                          ? zh ? "结构化练习" : "Structured"
                          : zh ? "真实模拟" : "Dynamic"}
                      </div>
                      <div className="text-xs text-[#6B7280] mt-1">
                        {m === "preset"
                          ? zh ? "固定8题，可重现" : "8 fixed questions"
                          : zh ? "AI自主调整，每场不同" : "AI adapts in real time"}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-[#374151] mb-3">
                  {zh ? "回答方式" : "Answer Mode"}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {(["voice", "text"] as InterviewInterface[]).map((iface) => (
                    <button
                      key={iface}
                      onClick={() => setInterviewInterface(iface)}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        interviewInterface === iface
                          ? "border-[#6366F1] bg-[#EEF2FF]"
                          : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/50"
                      }`}
                    >
                      <div className="text-lg mb-1">{iface === "voice" ? "🎙️" : "⌨️"}</div>
                      <div className="font-semibold text-sm text-[#111827]">
                        {iface === "voice"
                          ? zh ? "语音面试" : "Voice"
                          : zh ? "文字面试" : "Text"}
                      </div>
                      <div className="text-xs text-[#6B7280] mt-1">
                        {iface === "voice"
                          ? zh ? "录音作答，TTS播放" : "Speak your answer"
                          : zh ? "打字作答，可语音转文字" : "Type or dictate"}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => setStep(3)}
                className="w-full bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold py-3 rounded-xl transition-colors"
              >
                {zh ? "下一步" : "Next"}
              </button>
            </div>
          </StepCard>
        )}

        {/* Step 3: Persona */}
        {stepUnlocked[3] && (
          <StepCard title={zh ? "选择面试官" : "Choose Your Interviewer"} active={step === 3}>
            <div className="space-y-4">
              {PERSONAS.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setPersona(p.id)}
                  className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
                    persona === p.id
                      ? `${p.color} ${p.bg}`
                      : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/40"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="text-4xl">{p.emoji}</div>
                      <div>
                        <div className="font-semibold text-[#111827]">{p.name}</div>
                        <div className="text-xs text-[#6B7280]">
                          {zh ? p.title : p.titleEn}
                        </div>
                        <div className="text-xs text-[#6B7280] mt-0.5">
                          {zh ? p.style : p.styleEn}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); playPreview(p.id); }}
                      disabled={previewLoading === p.id}
                      className="text-xs bg-white border border-[#E5E7EB] hover:border-[#6366F1] text-[#6B7280] hover:text-[#6366F1] px-3 py-1.5 rounded-lg transition-colors"
                    >
                      {previewLoading === p.id ? "▶ ..." : zh ? "试听声音" : "Preview"}
                    </button>
                  </div>
                </div>
              ))}

              <button
                disabled={!persona || loading}
                onClick={handleStart}
                className="w-full mt-2 bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF] text-white font-semibold py-4 rounded-xl text-lg transition-colors"
              >
                {loading ? (zh ? "正在创建..." : "Creating...") : zh ? "进入面试 →" : "Start Interview →"}
              </button>
            </div>
          </StepCard>
        )}
      </div>
    </div>
  );
}

function StepCard({
  title,
  children,
  active,
}: {
  title: string;
  children: React.ReactNode;
  active: boolean;
}) {
  return (
    <div className={`bg-white rounded-xl border shadow-sm mb-6 overflow-hidden transition-all ${active ? "border-[#6366F1]/30 shadow-md" : "border-[#E5E7EB]"}`}>
      <div className={`px-6 py-4 border-b ${active ? "border-[#6366F1]/20 bg-[#F8F9FF]" : "border-[#E5E7EB]"}`}>
        <h2 className="font-semibold text-[#111827]">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}
