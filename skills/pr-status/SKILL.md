---
name: pr-status
description: Audits open Pull Requests for review feedback after the latest commit, groups related PRs across repositories by task card ID, and verifies approval readiness. Use when asked to check PR status, list pending PR feedback, verify if PRs/tasks are approved for QA or merge, or audit task readiness.
---

# PR Status & Review Audit

Audits open Pull Requests authored by the developer across multiple repositories, detects review comments and change requests submitted **after** the latest commit, and aggregates related PRs by task card ID (e.g., `PROJ-123`, `TASK-456`) to determine overall readiness for QA or merge.

## Usage

Run from terminal:

```bash
pr-status
```

Or execute directly with Python:

```bash
python3 skills/pr-status/scripts/audit_prs.py
```

### Options

- `pr-status --json`: Export structured output in JSON format.
- `pr-status --owner <org>`: Filter PRs by GitHub organization or user account (optional; can also be configured via `PR_STATUS_ORG`).
- `pr-status --reviewer <user>`: Check approval status for a specific designated reviewer on the HEAD commit (optional; can also be configured via `PR_STATUS_REVIEWER`).
- `pr-status --author <user>`: Audit PRs for a specific author (defaults to the currently authenticated `gh` user).
