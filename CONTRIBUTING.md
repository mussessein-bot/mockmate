# 协作规范

## 分支规则

每个人在自己的分支上开发，**不要直接改 main**。

| 分支 | 用途 |
|------|------|
| `main` | 稳定可运行版本，只通过 PR 合并 |
| `feature/功能名` | 新功能开发 |
| `fix/问题名` | Bug 修复 |

创建分支示例：
```bash
git checkout main
git pull origin main          # 先拉取最新代码
git checkout -b feature/语音模式优化
```

---

## 日常工作流

```bash
# 每天开始前，同步最新代码
git pull origin main

# 写完代码后，保存并推送
git add .
git commit -m "简短描述做了什么"
git push origin feature/你的分支名
```

---

## Commit 信息怎么写

要让别人看懂你做了什么，一句话说清楚：

```
# 好的写法
feat: 新增语音面试倒计时功能
fix: 修复结果页评分显示为空的问题
style: 调整首页按钮颜色和间距

# 不好的写法
update
改了一些东西
aaa
```

前缀说明：
- `feat:` 新功能
- `fix:` 修 Bug
- `style:` 样式调整
- `docs:` 文档修改
- `refactor:` 重构代码

---

## 合并到 main 的流程

1. 在 GitHub 上发起 **Pull Request**（PR）
2. 选择 base: `main`，compare: 你的分支
3. 写清楚这个 PR 做了什么
4. 通知其他人 review，至少 1 人同意后合并

---

## 注意事项

- `.env` 文件**不要提交**，里面有 API Key，泄露会产生费用
- 每次开始工作前先 `git pull`，避免冲突
- 遇到合并冲突不会处理，找组长帮忙解决，不要乱改
