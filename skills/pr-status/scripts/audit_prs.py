#!/usr/bin/env python3
"""
PR Status & Review Audit
Audits open pull requests across multi-repository task features, flags review comments
after the latest commit, and verifies commit-level approval readiness.
"""

import argparse
import concurrent.futures
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys

STATE_OVERRIDING = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def run_cmd(cmd):
    """Run a subprocess command and return trimmed stdout, or None on failure."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def run_cmd_checked(cmd):
    """Run a subprocess command and return (stdout, stderr, returncode)."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip(), res.returncode


def get_current_user():
    """Identify the currently authenticated GitHub CLI user."""
    user = run_cmd(["gh", "api", "user", "--jq", ".login"])
    if user:
        return user
    out, err, _ = run_cmd_checked(["gh", "auth", "status"])
    combined = f"{out}\n{err}"
    m = re.search(r"account\s+([a-zA-Z0-9_\-]+)", combined)
    if m:
        return m.group(1)
    return None


def parse_date(date_str):
    """Parse ISO date string safely into a UTC datetime."""
    if not date_str:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    clean_str = date_str.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def extract_task_id(branch, title):
    """Extract standard task or ticket ID (e.g. PROJ-123) from branch name or title."""
    m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", (branch or "").upper()) or \
        re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", (title or "").upper())
    return m.group(1).upper() if m else None


def gh_api_paginated(endpoint):
    """Fetch paginated API results using gh api --paginate --slurp."""
    out = run_cmd(["gh", "api", "--paginate", "--slurp", endpoint])
    if not out:
        return []
    try:
        pages = json.loads(out)
        items = []
        for page in pages:
            if isinstance(page, list):
                items.extend(page)
            elif isinstance(page, dict):
                items.append(page)
        return items
    except json.JSONDecodeError:
        return []


def fetch_pr_details(repo, pr_num):
    """Fetch PR details, inline review comments, and formal reviews."""
    pr_json = run_cmd([
        "gh", "pr", "view", str(pr_num), "--repo", repo,
        "--json", "number,title,headRefName,baseRefName,headRefOid,url,commits,comments,reviewDecision"
    ])
    if not pr_json:
        return None
    try:
        pr_data = json.loads(pr_json)
    except json.JSONDecodeError:
        return None

    # Fetch paginated inline review comments
    review_comments = gh_api_paginated(f"repos/{repo}/pulls/{pr_num}/comments")

    # Fetch paginated reviews (to inspect commit_id on reviews reliably)
    reviews_api = gh_api_paginated(f"repos/{repo}/pulls/{pr_num}/reviews")

    return {
        "repo": repo,
        "pr_num": pr_num,
        "data": pr_data,
        "review_comments": review_comments,
        "reviews_api": reviews_api
    }


def analyze_pr(item, author_login, designated_reviewer):
    """Analyze review status, stale approvals, and feedback posted after latest commit."""
    repo = item["repo"]
    pr_num = item["pr_num"]
    data = item["data"]
    review_comments = item["review_comments"]
    reviews_api = item["reviews_api"]

    branch = data.get("headRefName", "")
    title = data.get("title", "")
    head_oid = data.get("headRefOid", "")
    url = data.get("url", f"https://github.com/{repo}/pull/{pr_num}")

    task_id = extract_task_id(branch, title) or f"NO_TASK_ID-#{pr_num}"

    commits = data.get("commits", [])
    last_commit = commits[-1] if commits else {}
    last_commit_date_str = last_commit.get("committedDate")
    last_commit_date = parse_date(last_commit_date_str)
    last_commit_oid = last_commit.get("oid", head_oid)

    author_lower = author_login.lower()
    rev_state = "NO_REVIEW"
    rev_approved_on_head = False
    effective_reviewer = designated_reviewer or ""
    last_rev_body = ""

    # Sort reviews chronologically
    sorted_reviews = sorted(
        reviews_api,
        key=lambda r: parse_date(r.get("submitted_at"))
    )

    if designated_reviewer:
        # Check specific designated reviewer
        rev_history = [
            r for r in sorted_reviews
            if (r.get("user") or {}).get("login", "").lower() == designated_reviewer.lower()
        ]
        # Look for the latest decision in STATE_OVERRIDING
        decisive_reviews = [r for r in rev_history if r.get("state") in STATE_OVERRIDING]
        if decisive_reviews:
            last_rev = decisive_reviews[-1]
            last_state = last_rev.get("state", "NONE")
            last_rev_body = last_rev.get("body", "")
            if last_state == "APPROVED":
                if last_rev.get("commit_id") == head_oid:
                    rev_approved_on_head = True
                    rev_state = "APPROVED"
                else:
                    rev_state = "APPROVED_STALE"
            else:
                rev_state = last_state
        else:
            commented_reviews = [r for r in rev_history if r.get("state") == "COMMENTED"]
            if commented_reviews:
                rev_state = "COMMENTED"
                last_rev_body = commented_reviews[-1].get("body", "")
    else:
        # Generic mode: analyze latest reviews per user (excluding the PR author)
        latest_decisive_by_user = {}
        latest_commented_by_user = {}

        for r in sorted_reviews:
            user = (r.get("user") or {}).get("login", "")
            if not user or user.lower() == author_lower:
                continue
            state = r.get("state")
            if state in STATE_OVERRIDING:
                latest_decisive_by_user[user.lower()] = r
            elif state == "COMMENTED":
                latest_commented_by_user[user.lower()] = r

        changes_requested = [
            r for r in latest_decisive_by_user.values()
            if r.get("state") == "CHANGES_REQUESTED"
        ]
        approved_reviews = [
            r for r in latest_decisive_by_user.values()
            if r.get("state") == "APPROVED"
        ]

        if changes_requested:
            rev_state = "CHANGES_REQUESTED"
            last_cr = changes_requested[-1]
            effective_reviewer = (last_cr.get("user") or {}).get("login", "")
            last_rev_body = last_cr.get("body", "")
        elif approved_reviews:
            head_approvals = [r for r in approved_reviews if r.get("commit_id") == head_oid]
            if head_approvals:
                rev_approved_on_head = True
                rev_state = "APPROVED"
                effective_reviewer = ", ".join(
                    (r.get("user") or {}).get("login", "") for r in head_approvals if (r.get("user") or {}).get("login")
                )
            else:
                rev_state = "APPROVED_STALE"
                effective_reviewer = ", ".join(
                    (r.get("user") or {}).get("login", "") for r in approved_reviews if (r.get("user") or {}).get("login")
                )
        elif latest_commented_by_user:
            rev_state = "COMMENTED"
            last_commented = list(latest_commented_by_user.values())[-1]
            effective_reviewer = (last_commented.get("user") or {}).get("login", "")
            last_rev_body = last_commented.get("body", "")

    # Identify feedback posted strictly after the latest commit
    after_commit = []

    for rc in review_comments:
        c_date = parse_date(rc.get("created_at"))
        c_user = (rc.get("user") or {}).get("login", "")
        if c_date > last_commit_date and c_user.lower() != author_lower:
            after_commit.append({
                "type": "inline_review_comment",
                "author": c_user,
                "created_at": rc.get("created_at"),
                "body": rc.get("body", "")
            })

    for c in data.get("comments", []):
        c_date = parse_date(c.get("createdAt"))
        c_user = (c.get("author") or {}).get("login", "")
        if c_date > last_commit_date and c_user.lower() != author_lower:
            after_commit.append({
                "type": "issue_comment",
                "author": c_user,
                "created_at": c.get("createdAt"),
                "body": c.get("body", "")
            })

    return {
        "task_id": task_id,
        "repo": repo,
        "short_repo": repo.split("/")[-1],
        "pr_num": pr_num,
        "branch": branch,
        "title": title,
        "url": url,
        "head_oid": head_oid,
        "last_commit_oid": last_commit_oid,
        "last_commit_date": last_commit_date_str or "N/A",
        "reviewer_login": effective_reviewer,
        "rev_state": rev_state,
        "rev_approved_on_head": rev_approved_on_head,
        "last_rev_body": last_rev_body,
        "items_after_commit": after_commit
    }


def main():
    default_org = os.environ.get("PR_STATUS_ORG", "")
    default_reviewer = os.environ.get("PR_STATUS_REVIEWER", "")
    default_author = os.environ.get("PR_STATUS_AUTHOR", "")

    parser = argparse.ArgumentParser(
        description="Audit pull requests across repositories for review feedback and approval readiness."
    )
    parser.add_argument(
        "--author",
        default=default_author,
        help="PR author GitHub username (defaults to current authenticated gh user)"
    )
    parser.add_argument(
        "--owner", "--org",
        default=default_org,
        dest="owner",
        help="GitHub organization or account owner to filter PRs (optional)"
    )
    parser.add_argument(
        "--reviewer",
        default=default_reviewer,
        help="Specific reviewer whose approval is required on HEAD (optional)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of PRs to fetch in searches (default: 100)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as structured JSON"
    )
    args = parser.parse_args()

    author = args.author or get_current_user()
    if not author:
        sys.stderr.write("Error: Unable to identify GitHub user. Please run 'gh auth login' or pass --author <username>.\n")
        sys.exit(1)

    # 1. Search open PRs opened by the author
    search_cmd = [
        "gh", "search", "prs",
        "--author", author,
        "--state", "open",
        "--limit", str(args.limit),
        "--json", "number,repository,title,url"
    ]
    if args.owner:
        search_cmd.extend(["--owner", args.owner])

    stdout, stderr, code = run_cmd_checked(search_cmd)
    if code != 0:
        sys.stderr.write(f"Error querying GitHub CLI: {stderr or stdout}\n")
        sys.exit(code)

    try:
        author_prs = json.loads(stdout) if stdout else []
    except json.JSONDecodeError:
        sys.stderr.write("Error: Failed to parse GitHub CLI response as JSON.\n")
        sys.exit(1)

    if not author_prs:
        if args.json:
            print(json.dumps({}, indent=2))
        else:
            print("No open pull requests found.")
        return

    # 2. Extract task IDs and find sibling PRs
    task_keys = set()
    pr_set = set()
    known_owners = set()

    for item in author_prs:
        repo = item["repository"]["nameWithOwner"]
        num = item["number"]
        pr_set.add((repo, num))
        if "/" in repo:
            known_owners.add(repo.split("/")[0])

        tid = extract_task_id("", item.get("title", ""))
        if tid:
            task_keys.add(tid)

    # Search sibling PRs matching task keys across owners
    search_owners = [args.owner] if args.owner else list(known_owners)
    for tk in task_keys:
        for owner in search_owners:
            sibling_cmd = [
                "gh", "search", "prs", tk,
                "--state", "open",
                "--limit", str(args.limit),
                "--json", "number,repository,title,url"
            ]
            if owner:
                sibling_cmd.extend(["--owner", owner])

            s_out = run_cmd(sibling_cmd)
            if s_out:
                try:
                    siblings = json.loads(s_out)
                    for s in siblings:
                        s_title = s.get("title", "")
                        # Word boundary matching to avoid matching PROJ-1 in PROJ-10
                        if re.search(rf"(?<![A-Za-z0-9]){re.escape(tk)}(?!\d)", s_title, re.IGNORECASE):
                            s_repo = s["repository"]["nameWithOwner"]
                            s_num = s["number"]
                            pr_set.add((s_repo, s_num))
                except json.JSONDecodeError:
                    pass

    # 3. Parallel fetch PR details
    all_pr_details = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_pr_details, repo, num): (repo, num) for repo, num in pr_set}
        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
                if res:
                    all_pr_details.append(res)
            except Exception as e:
                repo_ref, num_ref = futures[fut]
                sys.stderr.write(f"Warning: Failed to fetch {repo_ref}#{num_ref}: {e}\n")

    # 4. Analyze each PR
    analyzed_prs = [analyze_pr(p, author, args.reviewer) for p in all_pr_details]

    # Group by task_id
    tasks = {}
    for p in analyzed_prs:
        tid = p["task_id"]
        tasks.setdefault(tid, []).append(p)

    if args.json:
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
        return

    # 5. Output Markdown Report
    print("### 1. PRs with Comments / Feedback After Latest Commit\n")

    has_feedback = False
    for tid, pr_list in sorted(tasks.items()):
        for p in pr_list:
            items = p["items_after_commit"]
            rev_pending = p["rev_state"] in ("COMMENTED", "CHANGES_REQUESTED")
            if items or rev_pending:
                has_feedback = True
                task_label = f"[{tid}] " if not tid.startswith("NO_TASK_ID") else ""
                print(f"#### 📌 {task_label}{p['short_repo']} [#{p['pr_num']}]({p['url']})")
                print(f"* **Branch:** `{p['branch']}`")
                print(f"* **Title:** {p['title']}")
                print(f"* **Latest Commit:** `{p['head_oid'][:7]}` ({p['last_commit_date']})")

                if rev_pending and p["last_rev_body"]:
                    rev_label = f"@{p['reviewer_login']}" if p["reviewer_login"] else "Reviewer"
                    print(f"* **Review by {rev_label} ({p['rev_state']}):**")
                    body_preview = p["last_rev_body"].strip()
                    if len(body_preview) > 300:
                        body_preview = body_preview[:300].strip() + "..."
                    print(f"  {body_preview}")

                if items:
                    print(f"* **Comments after latest commit ({len(items)}):**")
                    for it in items:
                        author_name = it["author"]
                        body = it["body"].strip().replace("\n", " ")
                        if len(body) > 140:
                            body = body[:140] + "..."
                        print(f"  - `{it['type']}` by @{author_name}: {body}")
                print()

    if not has_feedback:
        print("No open PRs with pending comments or requested changes after the latest commit.\n")

    print("### 2. Task Summary and Approval Readiness\n")
    print("| Task Card | Repository | PR | Branch | PR Status | Overall Task Status |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")

    for tid, pr_list in sorted(tasks.items()):
        all_approved = all(p["rev_approved_on_head"] for p in pr_list)
        any_stale = any(p["rev_state"] == "APPROVED_STALE" for p in pr_list)
        any_changes_requested = any(p["rev_state"] == "CHANGES_REQUESTED" for p in pr_list)

        repos_col = "<br>".join(p["short_repo"] for p in pr_list)
        prs_col = "<br>".join(f"[#{p['pr_num']}]({p['url']})" for p in pr_list)
        branches_col = "<br>".join(f"`{p['branch']}`" for p in pr_list)

        status_pr_list = []
        for p in pr_list:
            reviewer = p["reviewer_login"]
            rev_tag = f" (`@{reviewer}`)" if reviewer else ""
            if p["rev_approved_on_head"]:
                status_pr_list.append(f"✅ **Approved**{rev_tag}")
            elif p["rev_state"] == "APPROVED_STALE":
                status_pr_list.append("⚠️ **Approved on previous commit** (new commit pending review)")
            elif p["rev_state"] == "COMMENTED":
                status_pr_list.append("⏳ **Commented with feedback**")
            elif p["rev_state"] == "CHANGES_REQUESTED":
                status_pr_list.append("❌ **Changes requested**")
            else:
                status_pr_list.append("⏸️ **Awaiting review**")
        status_col = "<br>".join(status_pr_list)

        is_standalone = tid.startswith("NO_TASK_ID")
        display_task_id = f"*(PR #{pr_list[0]['pr_num']})*" if is_standalone else f"**{tid}**"

        if all_approved:
            task_status = "🟢 **ALL APPROVED**<br>*(Ready for QA / Merge)*"
        elif any_changes_requested:
            task_status = "❌ **CHANGES REQUESTED**<br>*(Requires fixes before review)*"
        elif any_stale and all(p["rev_approved_on_head"] or p["rev_state"] == "APPROVED_STALE" for p in pr_list):
            task_status = "🟡 **NEEDS RE-APPROVAL**<br>*(Approved earlier; new commits pending review)*"
        else:
            task_status = "🔴 **PENDING REVIEW**<br>*(Awaiting required reviews)*"

        print(f"| {display_task_id} | {repos_col} | {prs_col} | {branches_col} | {status_col} | {task_status} |")

    print("\n---")


if __name__ == "__main__":
    main()
