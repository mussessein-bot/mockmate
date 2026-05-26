# MockMate MVP 交接文档
> 供后续 Agent 或团队成员直接参考，无需任何前置对话记忆。
> 本文档描述当前已实现的完整状态（Phase 2 已完成）。

---

## 一、产品定位

**产品名：MockMate**
**Slogan：像真实面试一样练习**
**核心价值：** 基于 AI 的沉浸式模拟面试系统，支持语音和文字两种面试模式，面试结束后生成多维度反馈报告。

**目标用户：** 准备求职面试或研究生入学面试的学生/求职者
**演示场景：** 课程大作业答辩，需要当场可运行的完整 demo

---

## 二、技术栈（当前实际使用）

| 模块 | 技术选型 | 说明 |
|---|---|---|
| 后端框架 | Python + FastAPI | 异步支持，REST API |
| 数据库 | SQLite + aiosqlite | 单文件，异步读写 |
| LLM | 火山 ARK / DeepSeek-V4-Flash | OpenAI 兼容协议 |
| TTS（面试官发声） | 火山 WebSocket TTS（seed-tts-2.0） | 替换了原 edge-tts |
| STT（候选人转录） | 火山批量识别 STT（豆包录音文件识别2.0） | 替换了原 Web Speech API |
| 前端框架 | Next.js 14 + TypeScript | App Router，**无 src/ 目录** |
| CSS 框架 | Tailwind CSS | 现代浅色系，手写样式 |
| 历史记录存储 | localStorage | 无需登录，本机可见 |
| PDF 导出 | html2pdf.js（前端生成） | 反馈报告导出 |
| PDF 解析 | pdfplumber（后端） | 简历 PDF → 文本 |

### LLM 接入参数
```
base_url: https://ark.cn-beijing.volces.com/api/coding/v3
model: DeepSeek-V4-Flash
API Key 位置: 项目根目录 .env 文件，变量名 ARK_API_KEY
协议: OpenAI 兼容（使用 openai Python SDK，修改 base_url 即可）
```

### 火山 TTS 配置（seed-tts-2.0，WebSocket）
```
WS URL: wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream
Resource ID: seed-tts-2.0
Auth: X-Api-Key header（使用 VOLCANO_SPEECH_KEY）
```

```python
# Persona 语音 ID 映射（config.py PERSONA_VOICES）
"sarah":  {"zh": "zh_female_vv_uranus_bigtts",    "en": "en_female_dacey_uranus_bigtts"}
"marcus": {"zh": "zh_male_m191_uranus_bigtts",     "en": "en_male_tim_uranus_bigtts"}
"alex":   {"zh": "zh_female_xiaohe_uranus_bigtts", "en": "en_female_stokie_uranus_bigtts"}
```

### 火山 STT 配置（豆包录音文件识别2.0，批量 HTTP）
```
Submit URL: https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit
Query URL:  https://openspeech.bytedance.com/api/v3/auc/bigmodel/query
Resource ID: volc.seedasr.auc
Auth: x-api-key header（使用 VOLCANO_SPEECH_KEY）

⚠️ 重要限制：火山 STT 需要从公网 URL 下载音频文件，localhost 不可用。
本地 demo 需要 cloudflared 或 ngrok 将后端暴露到公网，并设置 BACKEND_URL。
```

---

## 三、环境变量（.env，位于项目根目录）

```env
ARK_API_KEY=ark-xxx           # 火山 ARK LLM 密钥
VOLCANO_SPEECH_KEY=xxx        # 火山语音（TTS + STT 共用同一个 key）
BACKEND_URL=https://xxx.trycloudflare.com  # 公网地址，供火山 STT 回调下载音频
```

**本地开发启动步骤：**
```bash
# 终端1：启动后端
cd interview_agent/backend
uvicorn app.main:app --reload

# 终端2：暴露公网（cloudflared，无需注册）
cloudflared tunnel --url http://localhost:8000
# 把输出的 URL 填到 .env BACKEND_URL，然后重启后端

# 终端3：启动前端
cd interview_agent/frontend
npm run dev
```

---

## 四、整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                         前端（Next.js）                       │
│  Landing → Setup → Interview Room → Feedback → History       │
│                                                              │
│  语音模式：MediaRecorder → /transcribe → respond             │
│  文字模式：textarea 输入 → respond（TTS 仍播放）              │
└─────────────────────────┬────────────────────────────────────┘
                          │ REST API (HTTP)
┌─────────────────────────▼────────────────────────────────────┐
│                      后端（FastAPI）                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Interviewer │  │   Strategy   │  │    Evaluator     │   │
│  │    Agent     │  │    Agent     │  │     Agent        │   │
│  │（生成对话）   │  │（决定下一步）│  │（评分+维度更新）  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 状态机        │  │  记忆系统    │  │  火山 TTS/STT    │   │
│  │（面试流程）   │  │（候选人画像）│  │  （语音服务）    │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    SQLite                            │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## 五、项目目录结构（实际状态）

```
interview_agent/
├── .env                          # ARK_API_KEY, VOLCANO_SPEECH_KEY, BACKEND_URL
├── MVP_SPEC.md                   # 本文档
├── RESEARCH_SPEC.md
│
├── backend/
│   ├── requirements.txt          # 见第十三节
│   ├── mockmate.db               # SQLite 数据库（自动创建）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口，lifespan 初始化 DB，挂载 /audio 静态目录
│   │   ├── config.py             # 所有环境变量 + 常量（PERSONA_VOICES, PERSONAS 等）
│   │   │
│   │   ├── core/
│   │   │   ├── models.py         # Pydantic 数据模型（含 InterviewInterface 枚举）
│   │   │   ├── state_machine.py  # 面试状态机
│   │   │   ├── memory.py         # 候选人画像管理
│   │   │   ├── dimensions.py     # 15维度池
│   │   │   └── exceptions.py
│   │   │
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── interviewer.py
│   │   │   ├── strategy.py
│   │   │   └── evaluator.py
│   │   │
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   └── prompts/
│   │   │       ├── interviewer_prompts.py
│   │   │       ├── strategy_prompts.py
│   │   │       └── evaluator_prompts.py
│   │   │
│   │   ├── services/
│   │   │   ├── tts.py            # 火山 WebSocket TTS（二进制协议）
│   │   │   └── stt.py            # 火山批量 STT（submit+poll HTTP）
│   │   │
│   │   ├── api/
│   │   │   ├── router.py         # 汇总所有路由
│   │   │   ├── sessions.py       # Session CRUD
│   │   │   ├── interview.py      # 核心对话 + 转录接口
│   │   │   ├── feedback.py       # finalize + feedback
│   │   │   ├── upload.py         # PDF 解析接口
│   │   │   └── schemas.py        # 请求/响应 Schema
│   │   │
│   │   └── storage/
│   │       ├── database.py       # aiosqlite 初始化（asynccontextmanager）
│   │       └── session_store.py  # Session 持久化
│   │
│   └── audio/                    # TTS 生成的临时音频（每 session 只保留最新一条）
│
└── frontend/                     # Next.js 14，无 src/ 目录
    ├── package.json
    ├── tailwind.config.ts
    ├── app/                      # App Router 根目录（注意：不是 src/app）
    │   ├── layout.tsx
    │   ├── globals.css
    │   ├── page.tsx              # Landing Page
    │   ├── setup/
    │   │   └── page.tsx          # Setup Page（4步）
    │   ├── interview/
    │   │   └── [sessionId]/
    │   │       └── page.tsx      # Interview Room（语音+文字双模式）
    │   ├── feedback/
    │   │   └── [sessionId]/
    │   │       └── page.tsx      # Feedback Page
    │   └── history/
    │       └── page.tsx          # History Page
    │
    └── lib/
        ├── api.ts                # 所有后端 API 调用（含 parsePdf, transcribe）
        ├── types.ts              # TypeScript 类型（含 InterviewInterface）
        ├── speech.ts             # Web Speech API 封装（已基本弃用，仅保留）
        └── storage.ts            # localStorage 操作
```

---

## 六、核心数据模型（backend/app/core/models.py）

```python
class InterviewType(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL  = "technical"
    GRADUATE   = "graduate"

class InterviewMode(str, Enum):
    PRESET  = "preset"    # 固定8题
    DYNAMIC = "dynamic"   # AI自主

class InterviewInterface(str, Enum):  # ← Phase 2 新增
    VOICE = "voice"   # 录音作答，MediaRecorder → /transcribe
    TEXT  = "text"    # 文字作答（TTS 仍播放）

class InterviewState(str, Enum):
    INIT       = "INIT"
    OPENING    = "OPENING"
    BEHAVIORAL = "BEHAVIORAL"
    DEEP_DIVE  = "DEEP_DIVE"    # 追问，不计入主题数
    TECHNICAL  = "TECHNICAL"
    CLOSING    = "CLOSING"
    COMPLETED  = "COMPLETED"

class PersonaType(str, Enum):
    SARAH  = "sarah"
    MARCUS = "marcus"
    ALEX   = "alex"

class Language(str, Enum):
    ZH = "zh"
    EN = "en"

class EvaluationResult(BaseModel):
    model_config = {"protected_namespaces": ()}  # 必须：避免 Pydantic model_ 命名冲突
    question_index:     int
    question_text:      str
    answer_transcript:  str
    dimension_scores:   list[DimensionScore]
    overall_score:      float
    is_probe:           bool = False
    is_probe_triggered: bool = False
    probe_reason:       Optional[str] = None
    model_answer:       Optional[str] = None

class InterviewSession(BaseModel):
    session_id:          str
    profile:             CandidateProfile
    interview_type:      InterviewType
    interview_mode:      InterviewMode
    interview_interface: InterviewInterface = InterviewInterface.VOICE  # ← Phase 2 新增
    persona:             PersonaType
    state:               InterviewState = InterviewState.INIT
    messages:            list[Message]
    question_count:      int = 0    # 主题计数（不含追问）
    max_questions:       int = 8
    probe_count:         int = 0    # 全场追问次数，最多2次
    last_was_probe:      bool = False  # 禁止连续追问同一答案
    active_dimensions:   list[str]
    candidate_profile_json: dict
    evaluations:         list[EvaluationResult]
    summary:             Optional[SessionSummary] = None
```

---

## 七、15维度池（backend/app/core/dimensions.py）

```python
DEFAULT_DIMENSIONS = {
    "behavioral": ["relevance", "structure", "specificity", "impact", "expression"],
    "technical":  ["logic", "tech_depth", "specificity", "expression", "data_thinking"],
    "graduate":   ["academic", "logic", "learning", "expression", "relevance"],
}
```

---

## 八、三 Agent 架构

每轮交互流程（`POST /api/interview/{id}/respond`）：

```
候选人文字 / 语音转录结果
    ↓
① Evaluator Agent → DimensionScore[] + is_probe_triggered + profile_update
② Strategy Agent  → {next_action: "probe"|"continue"|"close", topic}
③ Interviewer Agent → 面试官回复文字
④ 火山 TTS → audio_file（保存到 /audio/，每 session 只保留最新一个）
    ↓
返回 RespondResponse
```

**追问规则：**
- 全场最多 2 次追问（`probe_count < 2`）
- 不能对追问的回答再追问（`last_was_probe == True` 时跳过追问）
- 追问不计入 `question_count`
- 追问报告中独立展示

---

## 九、完整 API 接口

### Session 管理
```
POST /api/sessions
  Body: {
    name, target_role, target_company?, resume_text?,
    language, interview_type, interview_mode,
    interview_interface,   ← "voice" | "text"
    persona
  }
  Response: { session_id, state, active_dimensions, interview_interface }

GET  /api/sessions/{session_id}   → InterviewSession 完整状态
DELETE /api/sessions/{session_id} → { success: true }
```

### 核心对话
```
POST /api/interview/{session_id}/start
  Response: { interviewer_text, audio_url, state, question_count, active_dimensions }

POST /api/interview/{session_id}/respond
  Body: { transcript: str }
  Response: {
    interviewer_text, audio_url, state, question_count,
    is_probe, probe_reason, active_dimensions,
    evaluation: EvaluationResult | null,
    should_end: bool
  }

POST /api/interview/{session_id}/pause   → { paused: true }
POST /api/interview/{session_id}/resume  → { resumed: true }
GET  /api/interview/{session_id}/replay-audio → { audio_url }
```

### 语音转录（Phase 2 新增）
```
POST /api/interview/{session_id}/transcribe
  Body: multipart/form-data，file 字段（音频文件，webm/mp4）
  处理：保存到 /audio/，提交 URL 给火山 STT，poll 结果，删除文件
  Response: { transcript: str }

  ⚠️ 依赖 BACKEND_URL 为公网地址（火山需下载音频）
```

### PDF 解析（Phase 2 新增）
```
POST /api/parse-pdf
  Body: multipart/form-data，file 字段（PDF 文件，max 10MB）
  处理：pdfplumber 提取文本
  Response: { text: str }
```

### 反馈报告
```
POST /api/sessions/{session_id}/finalize
  支持截断：面试中途调用也能生成报告（按已完成题数）
  Response: SessionSummary

GET /api/sessions/{session_id}/feedback
  Response: SessionSummary（已生成）
```

### 音频服务
```
GET  /audio/{filename}          → 静态文件服务（FastAPI StaticFiles）
POST /api/tts/preview           Body: {persona, language} → { audio_url }
```

---

## 十、状态机

```
INIT → OPENING(1题) → BEHAVIORAL(5题) ↔ DEEP_DIVE(最多2次/场)
     → TECHNICAL(2题) → CLOSING → COMPLETED

动态模式：Strategy Agent 输出 next_action="close" 触发 CLOSING
预设模式：question_count >= 8 自动触发
```

---

## 十一、各页面详细规格

### Setup Page（/setup）
4步单页滚动：

1. **语言**：中文 / English
2. **基本信息**：
   - 姓名（必填）、目标职位（必填）
   - 简历文本（可选）+ **上传 PDF 按钮**（调 `/api/parse-pdf`，自动填入文本框）
3. **面试类型 + 模式 + 回答方式**：
   - 面试类型：行为面 / 技术面 / 研究生面
   - 面试模式：结构化练习 / 真实模拟
   - **回答方式**（Phase 2 新增）：语音面试 / 文字面试
4. **选择面试官**：Sarah / Marcus / Alex，含"试听声音"按钮

**跳转**：`router.push('/interview/${session_id}?interface=${interviewInterface}')`

### Interview Room（/interview/[sessionId]）

**通用 UI 元素（两种模式都有）：**
- 顶栏：MockMate logo | 第N题·阶段 | ⏱计时 | **结束面试**按钮（Phase 2 新增）
- 进度条：题目数 / max_questions
- 结束面试确认弹窗："将根据已完成 N 道题生成报告" → 调 `/finalize` → 跳转 feedback

**语音模式（interface=voice）：**
```
大头像（居中）+ 追问时橙色边框 + 说话时蓝色 pulse
字幕区：面试官文字 / 录音中红色"● 录音中"提示 / 转录中绿色 dots
底部控制：↺ 重播 | ● 麦克风（MediaRecorder）| ⏸ 暂停
```
录音流程：点击麦克风 → MediaRecorder 录音 → 再点停止 → 发送 blob 到 `/transcribe` → 显示"语音转文字中..."→ 获得 transcript → 发 `/respond`

**文字模式（interface=text）：**
```
聊天气泡布局（满屏滚动）：
  面试官消息：左侧气泡（白底）+ 小头像
  候选人消息：右侧气泡（indigo 底色）
  追问消息：面试官气泡上方显示"🔶 追问"标签
  AI 思考/转录中：左侧三点动画

底部输入栏：
  🎙️ 麦克风按钮（录音后 transcribe，填到输入框中发送）
  文字输入框（Enter 发送，Shift+Enter 换行）
  ↑ 发送按钮
```
TTS 在文字模式下仍然播放（面试官消息出现同时音频播放）

**UIState 枚举：**
`"loading" | "ai_speaking" | "ai_thinking" | "waiting" | "recording" | "transcribing" | "paused"`

### Feedback Page（/feedback/[sessionId]）
- 总分 + 等级 + AI 评语
- 雷达图（Recharts）+ 点击维度显示详情面板
- 每题卡片（折叠我的回答 / 查看示范回答）
- 追问题有 "🔶 已追问" 标签
- 按钮：再来一场 | 保存记录（localStorage）| 返回首页 | 导出 PDF（html2pdf.js）

### History Page（/history）
- 读取 localStorage 所有记录，列表展示
- 支持删除，空状态引导

---

## 十二、前端设计规范

```
背景：   #FAFAFA / #F8F9FF
主色：   #6366F1（indigo-500）
主色深： #4F46E5
成功色： #10B981（emerald-500）
警告色： #F59E0B（amber-500，追问状态）
错误色： #EF4444
文字主： #111827
文字副： #6B7280
边框：   #E5E7EB

圆角：rounded-xl（12px）
动效：transition-all duration-200
```

---

## 十三、requirements.txt（当前）

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.8.0
sqlalchemy==2.0.35
aiosqlite==0.20.0
openai==1.51.0
aiofiles==24.1.0
python-multipart==0.0.12
python-dotenv==1.0.1
httpx==0.27.2
websockets>=12.0
pdfplumber>=0.11.0
```

---

## 十四、已知问题 / 待修复

### 🔴 TTS 不可用（阻塞性）
**症状：** `POST /api/interview/{id}/start` 返回 500；TTS 报 `"No audio data received from Volcano TTS"`。

**根因分析：**
- WebSocket 收到的服务端消息中，type=9 的 JSON payload 解码失败（`json.loads` 误判编码）→ 已修复为 `payload.decode("utf-8")`
- 修复后仍报 "No audio data"，推测：
  - 消息解析逻辑与实际协议不匹配（header 字节位置偏差）
  - 或 `_EVENT_FINISHED=50` 判断不准确导致提前退出
  - 或火山 TTS 返回错误 code 未被正确捕获

**调试数据（实测消息结构）：**
```
msg0: type=9  raw_len=88  payload_sz=350   ← JSON，但解码失败（可能是 event/error）
msg1: type=11 raw_len=2401 payload_sz=352  ← 音频数据 ✓
msg2-4: type=11, 352 bytes each            ← 音频数据 ✓
msg5-6: type=9  ← JSON，解码失败
```
说明音频数据（type=11）确实在发送，但代码在 msg0 的 type=9 处理时出错后可能提前 break 了。

**下一步：** 检查 `_synthesize` 中 type=9 消息的 `except` 分支是否误 `break`，以及 payload 解析的 byte offset 是否正确（可能 header 是 4 字节但 payload_size 字段位置不同）。

**临时绕过方案：** 前端 `playAudio` 已加 `.catch(() => onEnd?.())` 处理，播放失败时不卡 UI，但没有声音。

### 🟡 STT 需要公网 URL
本地开发需 cloudflared 暴露后端，设置 `BACKEND_URL`，每次重启 cloudflared URL 会变化，需手动更新 `.env` 并重启后端。

---

## 十五、实现完成度

```
✅ 后端 Session 管理 + 状态机 + 三 Agent + LLM 接入
✅ 雷达图可交互 + 模范回答生成
✅ Persona 试听
✅ 历史记录页
✅ Landing Page
✅ PDF 导出
✅ 动态模式 + 研究生面试类型
✅ 文字/语音面试模式切换（InterviewInterface）
✅ 随时结束面试 → 截断式报告
✅ PDF 简历上传解析（pdfplumber）
✅ MediaRecorder 录音 → 火山 STT 转录
✅ 火山 WebSocket TTS（代码已写，存在解析 bug 待修复）
🔴 TTS 实际不可用（见第十四节）
```

---

*文档版本：MVP v2.0 | 最后更新：2026-05-25*
