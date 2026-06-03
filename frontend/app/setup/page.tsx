"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, audioUrl } from "@/lib/api";
import type {
  Language, InterviewType, InterviewInterface,
  PersonaType, JobAnalysisResponse, ExtractedQuestion,
} from "@/lib/types";

const TECH_ROLE_PRESETS = [
  { zh: "前端工程师", en: "Frontend Engineer" },
  { zh: "后端工程师", en: "Backend Engineer" },
  { zh: "算法工程师", en: "Algorithm Engineer" },
  { zh: "数据工程师", en: "Data Engineer" },
  { zh: "机器学习工程师", en: "ML Engineer" },
  { zh: "移动端工程师", en: "Mobile Engineer" },
  { zh: "全栈工程师", en: "Full Stack Engineer" },
  { zh: "DevOps 工程师", en: "DevOps Engineer" },
];

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
    icon: "🏢",
  },
  {
    id: "technical" as InterviewType,
    label: "技术专项面",
    labelEn: "Technical",
    desc: "技术深度、系统设计、逻辑分析",
    icon: "💻",
  },
  {
    id: "graduate" as InterviewType,
    label: "研究生招生面",
    labelEn: "Graduate",
    desc: "科研经历、学术动机、未来规划",
    icon: "🎓",
  },
];

const STEP_LABELS_ZH = ["语言", "面试类型", "基本信息", "岗位分析", "面试设置", "面试官"];
const STEP_LABELS_EN = ["Language", "Type", "Info", "Analysis", "Settings", "Interviewer"];

export default function SetupPage() {
  const router = useRouter();

  // Step 0: Language
  const [language, setLanguage] = useState<Language>("zh");

  // Step 1: Interview type
  const [interviewType, setInterviewType] = useState<InterviewType>("behavioral");

  // Step 2: Basic info — shared
  const [name, setName] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  // behavioral / technical
  const [targetRole, setTargetRole] = useState("");
  const [targetCompany, setTargetCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [techStack, setTechStack] = useState("");
  // graduate
  const [targetSchool, setTargetSchool] = useState("");
  const [targetDepartment, setTargetDepartment] = useState("");
  const [targetAdvisor, setTargetAdvisor] = useState("");
  const [researchDirection, setResearchDirection] = useState("");

  // Step 3: Job analysis
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<JobAnalysisResponse | null>(null);
  const [extractedQuestions, setExtractedQuestions] = useState<ExtractedQuestion[]>([]);
  const [searchAvailable, setSearchAvailable] = useState(true);
  const [webSearchLoading, setWebSearchLoading] = useState(false);
  const [webSearchDone, setWebSearchDone] = useState(false);
  const [refineNote, setRefineNote] = useState("");
  const [refineLoading, setRefineLoading] = useState(false);

  // Step 4: Settings
  const [interviewInterface, setInterviewInterface] = useState<InterviewInterface>("voice");

  // Step 5: Persona
  const [persona, setPersona] = useState<PersonaType | null>(null);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const zh = language === "zh";

  // Derived helpers
  const effectiveRole = interviewType === "graduate"
    ? (targetDepartment || targetRole || "研究生申请")
    : targetRole;

  const effectiveCompany = interviewType === "graduate"
    ? [targetSchool, targetDepartment].filter(Boolean).join(" ")
    : targetCompany;

  function isProfileComplete() {
    if (!name.trim()) return false;
    if (interviewType === "graduate") {
      return targetSchool.trim().length > 0 && researchDirection.trim().length > 0;
    }
    return targetRole.trim().length > 0;
  }

  async function handlePdfUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPdfLoading(true);
    setPdfError("");
    try {
      const { text } = await api.parsePdf(file);
      setResumeText(text);
    } catch {
      setPdfError(zh ? "PDF解析失败，请手动粘贴" : "PDF parse failed, please paste manually");
    } finally {
      setPdfLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const effectiveJobDesc = (() => {
    const parts = [jobDescription, interviewType === "technical" && techStack ? `技术栈：${techStack}` : ""].filter(Boolean);
    return parts.length > 0 ? parts.join("\n\n") : undefined;
  })();

  async function handleProfileNext() {
    setStep(3);
    setAnalysisLoading(true);
    setWebSearchDone(false);
    setExtractedQuestions([]);
    try {
      const result = await api.analyzeRole({
        target_role: effectiveRole,
        target_company: effectiveCompany || undefined,
        job_description: effectiveJobDesc,
        interview_type: interviewType,
        language,
      });
      setAnalysisResult(result);
    } catch (e) {
      console.error(e);
    } finally {
      setAnalysisLoading(false);
    }
  }

  async function handleWebSearch() {
    setWebSearchLoading(true);
    try {
      const result = await api.webSearchAnalyze({
        interview_type: interviewType,
        target_role: effectiveRole,
        target_company: effectiveCompany || undefined,
        job_description: effectiveJobDesc,
        target_school: targetSchool || undefined,
        target_department: targetDepartment || undefined,
        target_advisor: targetAdvisor || undefined,
        research_direction: researchDirection || undefined,
        language,
      });
      setAnalysisResult(result);
      setExtractedQuestions(result.extracted_questions ?? []);
      setSearchAvailable(result.search_available);
      setWebSearchDone(true);
    } catch (e) {
      console.error(e);
    } finally {
      setWebSearchLoading(false);
    }
  }

  async function handleRefine() {
    if (!refineNote.trim()) return;
    setRefineLoading(true);
    try {
      const result = await api.refineAnalysis({
        target_role: effectiveRole,
        target_company: effectiveCompany || undefined,
        job_description: effectiveJobDesc,
        user_note: refineNote,
        interview_type: interviewType,
        language,
      });
      setAnalysisResult(result);
      setRefineNote("");
    } catch (e) {
      console.error(e);
    } finally {
      setRefineLoading(false);
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
        target_role: effectiveRole,
        target_company: effectiveCompany || undefined,
        job_description: effectiveJobDesc,
        job_analysis: analysisResult ?? undefined,
        resume_text: resumeText || undefined,
        language,
        interview_type: interviewType,
        interview_mode: "dynamic",
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
    step >= 2,
    step >= 3 && isProfileComplete(),
    step >= 4,
    step >= 5,
  ];

  const stepLabels = zh ? STEP_LABELS_ZH : STEP_LABELS_EN;

  return (
    <div className="min-h-screen bg-[#FAFAFA] py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <span className="text-2xl font-bold text-[#6366F1]">MockMate</span>
          <p className="text-[#6B7280] mt-1 text-sm">{zh ? "面试前准备" : "Interview Setup"}</p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-1.5 mb-10 flex-wrap">
          {stepLabels.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                    step === i
                      ? "bg-[#6366F1] text-white"
                      : step > i
                      ? "bg-[#10B981] text-white"
                      : "bg-[#E5E7EB] text-[#9CA3AF]"
                  }`}
                >
                  {step > i ? "✓" : i + 1}
                </div>
                <span className="text-[10px] text-[#9CA3AF]">{s}</span>
              </div>
              {i < stepLabels.length - 1 && (
                <div className={`w-6 h-px mb-4 ${step > i ? "bg-[#10B981]" : "bg-[#E5E7EB]"}`} />
              )}
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

        {/* Step 1: Interview type */}
        {stepUnlocked[1] && (
          <StepCard title={zh ? "面试类型" : "Interview Type"} active={step === 1}>
            <div className="space-y-3">
              {INTERVIEW_TYPES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => { setInterviewType(t.id); setStep(2); }}
                  className={`w-full p-4 rounded-xl border-2 text-left transition-all flex items-center gap-4 ${
                    interviewType === t.id
                      ? "border-[#6366F1] bg-[#EEF2FF]"
                      : "border-[#E5E7EB] bg-white hover:border-[#6366F1]/50"
                  }`}
                >
                  <span className="text-2xl">{t.icon}</span>
                  <div>
                    <div className="font-semibold text-[#111827] text-sm">
                      {zh ? t.label : t.labelEn}
                    </div>
                    <div className="text-xs text-[#6B7280] mt-0.5">{t.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </StepCard>
        )}

        {/* Step 2: Basic info — type-specific */}
        {stepUnlocked[2] && (
          <StepCard title={zh ? "基本信息" : "Your Information"} active={step === 2}>
            <div className="space-y-4">
              {/* Name — always */}
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

              {/* Behavioral / Technical fields */}
              {(interviewType === "behavioral" || interviewType === "technical") && (
                <>
                  {interviewType === "technical" && (
                    <div>
                      <p className="text-sm font-medium text-[#374151] mb-2">
                        {zh ? "快速选择技术岗位" : "Quick Select"}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {TECH_ROLE_PRESETS.map((r) => (
                          <button
                            key={r.zh}
                            onClick={() => setTargetRole(zh ? r.zh : r.en)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                              targetRole === (zh ? r.zh : r.en)
                                ? "border-[#6366F1] bg-[#EEF2FF] text-[#6366F1]"
                                : "border-[#E5E7EB] bg-white text-[#374151] hover:border-[#6366F1]/50"
                            }`}
                          >
                            {zh ? r.zh : r.en}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
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
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "目标公司（选填）" : "Target Company (optional)"}
                    </label>
                    <input
                      value={targetCompany}
                      onChange={(e) => setTargetCompany(e.target.value)}
                      placeholder={zh ? "如：字节跳动、腾讯" : "e.g. Google, Meta"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                    />
                  </div>
                  {interviewType === "technical" && (
                    <div>
                      <label className="text-sm font-medium text-[#374151] block mb-1">
                        {zh ? "技术栈（选填）" : "Tech Stack (optional)"}
                      </label>
                      <input
                        value={techStack}
                        onChange={(e) => setTechStack(e.target.value)}
                        placeholder={zh ? "如：React / Node.js / PostgreSQL" : "e.g. React / Node.js / PostgreSQL"}
                        className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                      />
                    </div>
                  )}
                  <div>
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "职位描述 / JD（选填）" : "Job Description (optional)"}
                    </label>
                    <textarea
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      rows={3}
                      placeholder={zh ? "粘贴招聘 JD，AI 将据此定制考察方向" : "Paste the job description — AI will tailor the interview focus"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors resize-none"
                    />
                  </div>
                </>
              )}

              {/* Graduate fields */}
              {interviewType === "graduate" && (
                <>
                  <div>
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "目标学校" : "Target School"} *
                    </label>
                    <input
                      value={targetSchool}
                      onChange={(e) => setTargetSchool(e.target.value)}
                      placeholder={zh ? "如：清华大学、北京大学" : "e.g. Tsinghua University"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "学院 / 专业（选填）" : "Department / Program (optional)"}
                    </label>
                    <input
                      value={targetDepartment}
                      onChange={(e) => setTargetDepartment(e.target.value)}
                      placeholder={zh ? "如：计算机科学与技术、软件工程" : "e.g. Computer Science, Software Engineering"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "目标导师（选填）" : "Target Advisor (optional)"}
                    </label>
                    <input
                      value={targetAdvisor}
                      onChange={(e) => setTargetAdvisor(e.target.value)}
                      placeholder={zh ? "如：张伟教授（不填则按学院搜索）" : "e.g. Prof. Zhang Wei (leave blank to search by department)"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#374151] block mb-1">
                      {zh ? "研究方向 / 申请方向" : "Research Direction"} *
                    </label>
                    <input
                      value={researchDirection}
                      onChange={(e) => setResearchDirection(e.target.value)}
                      placeholder={zh ? "如：计算机视觉、自然语言处理" : "e.g. Computer Vision, NLP"}
                      className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors"
                    />
                  </div>
                </>
              )}

              {/* Resume — always */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-[#374151]">
                    {interviewType === "graduate"
                      ? (zh ? "简历 / 个人陈述（选填）" : "CV / Personal Statement (optional)")
                      : (zh ? "简历内容（选填）" : "Resume (optional)")}
                  </label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={pdfLoading}
                    className="text-xs bg-[#EEF2FF] hover:bg-[#E0E7FF] text-[#6366F1] px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {pdfLoading ? (zh ? "解析中..." : "Parsing...") : (zh ? "上传 PDF" : "Upload PDF")}
                  </button>
                  <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handlePdfUpload} />
                </div>
                {pdfError && <p className="text-xs text-red-500 mb-1">{pdfError}</p>}
                <textarea
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  rows={4}
                  placeholder={zh ? "粘贴简历文本，或上传 PDF 自动解析，可跳过" : "Paste resume text, or upload PDF to auto-parse"}
                  className="w-full border border-[#E5E7EB] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#6366F1] transition-colors resize-none"
                />
              </div>

              <button
                disabled={!isProfileComplete()}
                onClick={handleProfileNext}
                className="w-full bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF] text-white font-semibold py-3 rounded-xl transition-colors"
              >
                {zh ? "下一步" : "Next"}
              </button>
            </div>
          </StepCard>
        )}

        {/* Step 3: Job Analysis */}
        {stepUnlocked[3] && (
          <StepCard title={zh ? "岗位分析" : "Role Analysis"} active={step === 3}>
            {analysisLoading ? (
              <div className="flex flex-col items-center py-8 gap-3 text-[#6B7280]">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-[#6366F1] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-sm">{zh ? "正在分析..." : "Analyzing..."}</span>
              </div>
            ) : analysisResult ? (
              <div className="space-y-4">
                {/* Analysis result */}
                <div className="bg-[#F8F9FF] rounded-xl p-4 border border-[#E5E7EB]">
                  <p className="text-xs text-[#6B7280] mb-1">{zh ? "岗位总结" : "Summary"}</p>
                  <p className="text-sm text-[#111827] font-medium">{analysisResult.summary}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-[#374151] mb-2">{zh ? "核心考察方向" : "Core Assessment Areas"}</p>
                  <div className="space-y-2">
                    {analysisResult.core_dimensions.map((d, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-white border border-[#E5E7EB] rounded-xl">
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0 mt-0.5 ${
                          d.weight === "高" || d.weight === "high" ? "bg-[#FEE2E2] text-[#DC2626]" :
                          d.weight === "中" || d.weight === "medium" ? "bg-[#FEF3C7] text-[#D97706]" :
                          "bg-[#F3F4F6] text-[#6B7280]"
                        }`}>{d.weight}</span>
                        <div>
                          <p className="text-sm font-medium text-[#111827]">{d.name}</p>
                          <p className="text-xs text-[#6B7280] mt-0.5">{d.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="bg-[#ECFDF5] rounded-xl p-3 border border-[#D1FAE5]">
                  <p className="text-xs text-[#065F46] font-medium mb-1">{zh ? "面试风格" : "Interview Style"}</p>
                  <p className="text-xs text-[#047857]">{analysisResult.interview_style}</p>
                </div>
                <div className="bg-[#FFFBEB] rounded-xl p-3 border border-[#FDE68A]">
                  <p className="text-xs text-[#92400E] font-medium mb-1">{zh ? "准备建议" : "Preparation Tips"}</p>
                  <p className="text-xs text-[#78350F]">{analysisResult.key_tips}</p>
                </div>

                {/* Web search — only for behavioral / graduate */}
                {(interviewType === "behavioral" || interviewType === "graduate") && (
                  <div className="border border-[#E5E7EB] rounded-xl p-4 bg-[#F9FAFB]">
                    {!webSearchDone ? (
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-[#374151]">
                            {zh ? "网络搜索真题增强" : "Search for Real Questions"}
                          </p>
                          <p className="text-xs text-[#6B7280] mt-0.5">
                            {zh
                              ? interviewType === "graduate"
                                ? "搜索真实面经，优化岗位分析并展示参考题目"
                                : "搜索真实面经，优化岗位分析并展示参考题目"
                              : "Search real interview experiences to refine analysis and show reference questions"}
                          </p>
                        </div>
                        <button
                          onClick={handleWebSearch}
                          disabled={webSearchLoading}
                          className="px-4 py-2 bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF] text-white text-xs rounded-xl transition-colors flex-shrink-0"
                        >
                          {webSearchLoading
                            ? (zh ? "搜索中..." : "Searching...")
                            : (zh ? "开始搜索" : "Search")}
                        </button>
                      </div>
                    ) : (
                      <div>
                        {!searchAvailable ? (
                          <p className="text-xs text-[#6B7280]">
                            {zh ? "网络搜索暂时不可用，已使用 AI 直接分析" : "Search unavailable, using AI analysis only"}
                          </p>
                        ) : extractedQuestions.length > 0 ? (
                          <div>
                            <p className="text-xs font-medium text-[#374151] mb-2">
                              {zh
                                ? `搜索完成，岗位分析已优化 · 发现 ${extractedQuestions.length} 道参考真题`
                                : `Analysis refined · Found ${extractedQuestions.length} reference questions`}
                            </p>
                            <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                              {extractedQuestions.map((q, i) => (
                                <div key={i} className="flex gap-2 text-xs">
                                  <span className="text-[#6366F1] flex-shrink-0 font-medium bg-[#EEF2FF] px-1.5 py-0.5 rounded text-[10px]">
                                    {q.category}
                                  </span>
                                  <span className="text-[#374151]">{q.question}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-xs text-[#6B7280]">
                            {zh ? "搜索完成，岗位分析已优化（未提取到结构化题目）" : "Analysis refined with search results (no structured questions extracted)"}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Refine */}
                <div className="border-t border-[#E5E7EB] pt-4">
                  <p className="text-xs font-medium text-[#374151] mb-2">
                    {zh ? "有不准确的地方？告诉我" : "Something off? Tell me"}
                  </p>
                  <div className="flex gap-2">
                    <input
                      value={refineNote}
                      onChange={e => setRefineNote(e.target.value)}
                      placeholder={zh ? "如：更偏向 B 端运营，不是增长方向" : "e.g. More B2B ops, not growth"}
                      className="flex-1 border border-[#E5E7EB] rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-[#6366F1]"
                    />
                    <button
                      onClick={handleRefine}
                      disabled={!refineNote.trim() || refineLoading}
                      className="px-4 py-2 bg-[#6366F1] hover:bg-[#4F46E5] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF] text-white text-xs rounded-xl transition-colors flex-shrink-0"
                    >
                      {refineLoading ? (zh ? "分析中..." : "Analyzing...") : zh ? "重新分析" : "Re-analyze"}
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => setStep(4)}
                  className="w-full bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold py-3 rounded-xl text-sm transition-colors"
                >
                  {zh ? "下一步" : "Next"}
                </button>
              </div>
            ) : (
              <div className="text-center py-6 space-y-4">
                <p className="text-sm text-[#6B7280]">
                  {zh ? "分析加载失败，可以跳过此步骤" : "Analysis unavailable, you can skip this step"}
                </p>
                <button
                  onClick={() => setStep(4)}
                  className="bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold px-8 py-3 rounded-xl text-sm transition-colors"
                >
                  {zh ? "跳过 →" : "Skip →"}
                </button>
              </div>
            )}
          </StepCard>
        )}

        {/* Step 4: Interface */}
        {stepUnlocked[4] && (
          <StepCard title={zh ? "面试设置" : "Interview Settings"} active={step === 4}>
            <div className="space-y-6">
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
                onClick={() => setStep(5)}
                className="w-full bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold py-3 rounded-xl transition-colors"
              >
                {zh ? "下一步" : "Next"}
              </button>
            </div>
          </StepCard>
        )}

        {/* Step 5: Persona */}
        {stepUnlocked[5] && (
          <StepCard title={zh ? "选择面试官" : "Choose Your Interviewer"} active={step === 5}>
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
                        <div className="text-xs text-[#6B7280]">{zh ? p.title : p.titleEn}</div>
                        <div className="text-xs text-[#6B7280] mt-0.5">{zh ? p.style : p.styleEn}</div>
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
