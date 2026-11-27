# PR Status & Review Audit

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub CLI](https://img.shields.io/badge/GitHub%20CLI-gh-green.svg)](https://cli.github.com/)
[![Python 3](https://img.shields.io/badge/Python-3.8+-yellow.svg)](https://www.python.org/)
[![AI Agent Skill](https://img.shields.io/badge/Agent%20Skill-Antigravity%20%2F%20Gemini-purple.svg)](#ai-agent-integration)

A powerful CLI utility and AI Agent skill that audits open Pull Requests across multiple repositories, groups related pull requests by task/issue card ID (e.g. Jira, Linear, GitHub Issues), detects review comments submitted **after** the author's latest commit, and validates commit-level approval readiness for QA or merge.

---

## Recommended Repository Details

If you are publishing or configuring this repository on GitHub:

- **Repository Name:** `pr-status`
- **Short Description:**
  > Multi-repository Pull Request review auditor and approval readiness tracker grouped by task card ID. CLI and AI Agent skill.
- **Topics / Tags:**
  `pull-requests`, `github`, `code-review`, `qa`, `developer-tools`, `cli`, `ai-agent`, `antigravity`, `productivity`

---

## Key Features

- 🧩 **Multi-Repo Task Grouping**: Automatically correlates open PRs across separate repositories (e.g. backend, frontend, mobile apps) using task or ticket patterns in branch names or titles (e.g. `PROJ-123`, `TASK-456`).
- 💬 **Post-Commit Feedback Detection**: Accurately detects inline code review comments and PR discussions submitted **after** the author's last commit, helping you address changes that were requested after your updates.
- 🎯 **Commit-Level Approval Verification**: Differentiates between approvals on the current `HEAD` commit versus approvals on older commits (`APPROVED_STALE`), ensuring unreviewed changes aren't slipped through.
- 🚦 **Readiness Tracking**: Evaluates overall task readiness across all connected PRs:
  - 🟢 **ALL APPROVED**: Every PR in the task is approved on the latest commit.
  - 🟡 **NEEDS RE-APPROVAL**: PR was previously approved, but newer commits were pushed and need re-verification.
  - ❌ **CHANGES REQUESTED**: Blocked by reviewer change requests.
  - 🔴 **PENDING REVIEW**: Awaiting initial or required reviews.
- 🤖 **Universal AI Agent Skill**: Pre-packaged as a plug-and-play skill for AI engineering assistants (Antigravity CLI, Gemini CLI, Claude Code, Cursor, etc.).

---

## Prerequisites

1. **Python 3.8+** installed.
2. **GitHub CLI (`gh`)** installed and authenticated (`gh auth login`).

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/maycon8609/pr-status.git
cd pr-status
./install.sh
```

The installer will:

- Link the executable `pr-status` to `~/.local/bin/pr-status`.
- Automatically register the agent skill in `~/.gemini/config/skills/pr-status` (if the agent directory exists).

### 2. Verify Installation

```bash
pr-status --help
```

---

## Usage

### Simple Audit

Audit all open pull requests authored by the current authenticated GitHub user:

```bash
pr-status
```

### Options & Flags

| Flag               | Environment Variable | Default            | Description                                                                         |
| :----------------- | :------------------- | :----------------- | :---------------------------------------------------------------------------------- |
| `--owner`, `--org` | `PR_STATUS_ORG`      | _(All / Detected)_ | Filter PRs by GitHub organization or user account.                                  |
| `--reviewer`       | `PR_STATUS_REVIEWER` | _(All Reviews)_    | Require approval on `HEAD` from a specific reviewer (e.g. Tech Lead or Code Owner). |
| `--author`         | `PR_STATUS_AUTHOR`   | `gh` user          | Target PR author's GitHub username.                                                 |
| `--json`           | -                    | `false`            | Output results in structured JSON format.                                           |

### Examples

```bash
# Scope to a specific organization:
pr-status --owner my-organization

# Require a designated reviewer's approval on HEAD:
pr-status --owner my-organization --reviewer octocat

# Audit another teammate's open PRs:
pr-status --author teammate_username

# Export structured JSON for pipelines or reporting scripts:
pr-status --json > pr_report.json
```

---

## Example Output

### 1. Terminal Markdown Report

```markdown
### 1. PRs with Comments / Feedback After Latest Commit

#### 📌 [PROJ-102] web-client [#42](https://github.com/my-org/web-client/pull/42)

- **Branch:** `feature/PROJ-102-checkout-flow`
- **Title:** feat: update checkout flow validation
- **Latest Commit:** `a1b2c3d` (2026-11-27T10:15:00Z)
- **Comments after latest commit (1):**
  - `inline_review_comment` by @reviewer_jane: Please ensure error states reset when retrying payment.

### 2. Task Summary and Approval Readiness

| Task Card    | Repository                 | PR                                       | Branch                                           | PR Status                                                      | Overall Task Status                                                          |
| :----------- | :------------------------- | :--------------------------------------- | :----------------------------------------------- | :------------------------------------------------------------- | :--------------------------------------------------------------------------- |
| **PROJ-101** | auth-service<br>web-client | [#18](https://...)<br>[#39](https://...) | `feature/PROJ-101-sso`<br>`feature/PROJ-101-sso` | ✅ **Approved**<br>✅ **Approved**                             | 🟢 **ALL APPROVED**<br>_(Ready for QA / Merge)_                              |
| **PROJ-102** | web-client                 | [#42](https://...)                       | `feature/PROJ-102-checkout-flow`                 | ⏳ **Commented with feedback**                                 | 🔴 **PENDING REVIEW**<br>_(Awaiting required reviews)_                       |
| **PROJ-103** | billing-api                | [#87](https://...)                       | `feature/PROJ-103-invoices`                      | ⚠️ **Approved on previous commit** (new commit pending review) | 🟡 **NEEDS RE-APPROVAL**<br>_(Approved earlier; new commits pending review)_ |
```

---

## AI Agent Integration

This repository includes a standard Agent Skill (`skills/pr-status/SKILL.md`) and `plugin.json` compatible with:

- **Google Antigravity CLI / Gemini CLI**
- **Claude Code / MCP toolchains**
- **Cursor / Custom Agent Runtimes**

### Enabling the Skill in Antigravity / Gemini CLI

Running `./install.sh` automatically links the skill to `~/.gemini/config/skills/pr-status`. Once installed, your agent can naturally answer requests such as:

- _"Check the review status of my open PRs"_
- _"Are there any new comments on my PRs after my last push?"_
- _"Which of my Jira/task cards are ready to move to QA?"_

---

## Uninstallation

To remove symlinks created during installation:

```bash
./uninstall.sh
```

---

## License

This project is licensed under the [MIT License](LICENSE).

2. Reiniciar o Git do zero (sem histórico antigo)

   rm -rf .git
   git init -b main
   git add .
   git commit -m "feat: initial commit for pr-status"
   ──────

3. Criar o repositório público no GitHub com descrição e tags

   gh repo create pr-status --public \
    --description "Multi-repo GitHub PR auditor: groups open PRs by task ID, flags review
   feedback posted after your latest commit, and checks whether approvals still apply to HEAD.
   CLI + AI agent skill." \
    --source=. \
    --remote=origin \
    --push

────── 4. Adicionar os tópicos/tags no repositório criado

    gh repo edit --add-topic pull-requests \
                 --add-topic github \
                 --add-topic code-review \
                 --add-topic qa \
                 --add-topic developer-tools \
                 --add-topic cli \
                 --add-topic ai-agent
