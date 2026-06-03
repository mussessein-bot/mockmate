# MockMate — AI 模拟面试练习平台

MockMate 是一个 AI 驱动的模拟面试练习工具，支持文字和语音两种面试模式，提供实时反馈与结果分析。

## 功能特点

- 多种面试官人设（HR、技术总监、产品VP）
- 支持文字 / 语音双模式面试
- 面试结束后逐句评分 + 参考答案
- 联网检索岗位信息，针对性出题

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | FastAPI + Python 3.11 |
| LLM  | 火山方舟 DeepSeek-V4-Flash |
| 语音 | 火山语音 TTS / STT |
| 搜索 | Tavily Search API |
| 穿透 | Cloudflare Tunnel |

---

## 环境要求

- **Node.js** >= 18
- **Python** >= 3.11
- **cloudflared**（Cloudflare Tunnel 客户端）

安装 cloudflared（Mac）：
```bash
brew install cloudflared
```

---

## 快速开始

### 1. 克隆仓库

**方式一：HTTPS（推荐新手，无需额外配置）**
```bash
git clone https://github.com/mussessein-bot/mockmate.git
cd mockmate
```
> 推送代码时会要求输入 GitHub 用户名和 Personal Access Token（不是密码）。Token 申请地址：https://github.com/settings/tokens → Generate new token (classic)，勾选 `repo` 权限即可。

**方式二：SSH（配置一次，之后免密）**

先检查本机是否已有 SSH key：
```bash
ls ~/.ssh/id_*.pub
```
- 有输出 → 已有 key，跳过生成步骤
- 报错 → 需要生成：

```bash
ssh-keygen -t ed25519 -C "你的GitHub邮箱" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub   # 复制输出内容
```
将复制的内容粘贴到 https://github.com/settings/ssh/new 添加，然后克隆：
```bash
git clone git@github.com:mussessein-bot/mockmate.git
cd mockmate
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

用文本编辑器打开 `.env`，填入你的 API Key（每个人需要自行申请，见文件内的获取地址）。

### 3. 安装依赖

**后端：**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows 用: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

**前端：**
```bash
cd frontend
npm install
cd ..
```

### 4. 启动项目

```bash
./start.sh
```

启动成功后，终端会显示一个公网访问地址（`trycloudflare.com` 域名），复制给别人即可访问。

本地调试地址：
- 前端：http://localhost:3001
- 后端 API 文档：http://localhost:8000/docs

---

## 项目结构

```
interview_agent/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── config.py        # 配置与环境变量
│   │   ├── llm/             # LLM 调用
│   │   ├── services/        # TTS / STT / 搜索
│   │   └── storage/         # 数据库
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js 页面
│   │   └── components/      # UI 组件
│   └── package.json
├── .env.example             # 环境变量模板
├── start.sh                 # 一键启动脚本
└── README.md
```

---

## 常见问题

**Q：启动报错 CORS 问题？**
Cloudflare Tunnel 链接过期了，重新运行 `./start.sh` 即可。

**Q：语音功能没有声音？**
检查 `.env` 里的 `VOLCANO_SPEECH_KEY` 是否填写正确。

**Q：项目跑不起来，提示缺少依赖？**
确认已激活 Python 虚拟环境（`source backend/venv/bin/activate`），并且运行过 `pip install -r requirements.txt`。
