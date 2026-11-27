# Security Policy

(中文版见下方。)

## Reporting a security problem

If you find a vulnerability (for example a credential-leak path, command injection, unsafe file writes, or a publisher that makes content public by mistake), **please do not disclose it in a public issue**.

Use **Security -> Report a vulnerability** (a private security advisory) on the GitHub repository, and include if you can:

- the affected file or command;
- steps to reproduce and the impact;
- a fix you suggest, if any.

We will confirm and follow up as soon as we can; please keep the details confidential until a fix is released.

## Scope

- The core flow of this project runs on your machine, needs no account or key, and does not go online on its own (except when installing the screenshot component).
- The optional GitHub Pages publisher uses the `GITHUB_TOKEN` you provide: it is read only from an environment variable, only placed in request headers, and never printed or written to a file. The published site is **public** and every publish needs explicit confirmation.
- If a token has ever leaked (pasted into a chat, a screenshot, or committed to a repository), revoke it on GitHub immediately and create a new one.

---

# 安全策略

## 报告安全问题

如果你发现了安全漏洞（例如凭证泄露路径、命令注入、不安全的文件写入、发布器误公开内容等），**请不要在公开 Issue 中披露**。

请通过 GitHub 仓库的 **Security → Report a vulnerability**（私密安全公告）提交，并尽量包含：

- 受影响的文件或命令；
- 复现步骤与影响范围；
- 你建议的修复方式（如有）。

我们会尽快确认并跟进，修复发布前请对细节保密。

## 范围说明

- 本项目的核心流程在本机运行，不需要任何账号或密钥，也不主动联网（安装截图组件时除外）。
- 可选的 GitHub Pages 发布器会使用你提供的 `GITHUB_TOKEN`：令牌只从环境变量读取，只放在请求头里，不会被打印或写入文件。发布的站点是**公开**的，每次发布都需要显式确认。
- 如果你的令牌曾经泄露（贴到聊天、截图、提交到仓库），请立即在 GitHub 上作废并重新申请。
