import Link from "next/link";

const features = [
  {
    icon: "🎙️",
    title: "语音沉浸",
    titleEn: "Voice Immersion",
    desc: "面试官语音提问，候选人语音回答，最真实的面试体验。",
  },
  {
    icon: "🤖",
    title: "AI 动态追问",
    titleEn: "AI Follow-ups",
    desc: "AI 实时分析你的回答，针对薄弱点深度追问，让练习更有针对性。",
  },
  {
    icon: "📊",
    title: "多维反馈",
    titleEn: "Multi-Dimension Feedback",
    desc: "15个能力维度雷达图，每题详细点评，模范回答对比。",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#FAFAFA] flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-[#E5E7EB] bg-white">
        <span className="font-bold text-xl text-[#6366F1]">MockMate</span>
        <Link
          href="/history"
          className="text-sm text-[#6B7280] hover:text-[#111827] transition-colors"
        >
          历史记录
        </Link>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        <div className="inline-block bg-[#EEF2FF] text-[#6366F1] text-sm font-medium px-4 py-1.5 rounded-full mb-6">
          AI 模拟面试 · 沉浸式练习
        </div>
        <h1 className="text-5xl font-bold text-[#111827] mb-4 leading-tight">
          像真实面试一样练习
        </h1>
        <p className="text-lg text-[#6B7280] max-w-xl mb-10">
          选择你的面试官，用语音对话练习，获得专业多维度反馈报告。
        </p>
        <Link
          href="/setup"
          className="bg-[#6366F1] hover:bg-[#4F46E5] text-white font-semibold px-8 py-4 rounded-xl text-lg transition-colors shadow-sm"
        >
          开始面试 →
        </Link>

        {/* Feature cards */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-xl p-6 text-left shadow-sm border border-[#E5E7EB] hover:shadow-md transition-shadow"
            >
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-[#111827] text-lg mb-2">{f.title}</h3>
              <p className="text-[#6B7280] text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </main>

      <footer className="text-center py-6 text-[#9CA3AF] text-sm">
        MockMate · 模拟面试练习系统
      </footer>
    </div>
  );
}
