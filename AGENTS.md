# Agent instructions

Use the repository coden607/skills as the shared skills catalog. Before substantive work, automatically select the relevant skills for the task. Preserve project-specific requirements. Only use tools and integrations that are actually available in the current runtime.

## Shared agent skills

Canonical library: https://github.com/coden607/skills

For every agent session in this project:
1. Read this project's instructions before planning or editing.
2. Reuse or clone the complete canonical skills library, sync it before selecting skills, and inspect the relevant SKILL.md files. Do not install just a hand-picked subset.
3. Select skills according to the task; do not execute all skills automatically. Follow their instructions within the current user's authorization and this project's safety and product rules.
4. Keep this policy usable by Codex/ChatGPT, Claude Code, Gemini CLI, Copilot, Kimi, OpenClaw, Chatty and other agents. Agents without automatic instruction discovery must load AGENTS.md explicitly.
5. Never put credentials, private customer data or secrets in skills, prompts, commits or logs.
6. Prefer the canonical library over divergent copied skills. Installing a skill does not authorize sending messages, changing customer systems, deployments, billing or other external actions.

This is persistent project guidance. It does not prove that an AI service or remote machine has the library installed.
