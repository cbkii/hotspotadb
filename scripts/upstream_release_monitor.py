import argparse
import subprocess
import json
import sys
import os
import shutil

def run_cmd(cmd, check=True, capture_output=True, text=True):
    result = subprocess.run(cmd, check=check, capture_output=capture_output, text=text)
    return result

def get_releases(upstream_repo, include_prerelease=False):
    cmd = ["gh", "api", f"repos/{upstream_repo}/releases", "--paginate"]
    result = run_cmd(cmd)
    try:
        releases = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Failed to decode releases JSON from GitHub API.")
        sys.exit(1)

    eligible_releases = []
    for r in releases:
        if r.get("draft"):
            continue
        if r.get("prerelease") and not include_prerelease:
            continue
        eligible_releases.append(r)

    return eligible_releases

def resolve_tags(args):
    head_tag = args.head_tag
    base_tag = args.base_tag

    releases = []
    if not head_tag or not base_tag:
        releases = get_releases(args.upstream_repo, args.include_prerelease)

    if not head_tag:
        if not releases:
            print(f"::error::No eligible releases found for {args.upstream_repo}")
            sys.exit(0) # Not an error, just no releases to process.
        head_tag = releases[0]["tag_name"]

    if not base_tag:
        if not releases:
             releases = get_releases(args.upstream_repo, args.include_prerelease)

        found_head = False
        for r in releases:
            if found_head:
                base_tag = r["tag_name"]
                break
            if r["tag_name"] == head_tag:
                found_head = True

        if not base_tag:
            print(f"::warning::Could not find a previous release for {head_tag}. Diff might be incomplete.")

    return head_tag, base_tag

def fetch_upstream(upstream_repo, head_tag, base_tag):
    print("Adding upstream remote...")
    run_cmd(["git", "remote", "add", "upstream", f"https://github.com/{upstream_repo}.git"], check=False)

    print(f"Fetching base tag {base_tag}...")
    if base_tag:
        # Try fetching by tag first
        res = run_cmd(["git", "fetch", "--no-tags", "upstream", f"+refs/tags/{base_tag}:refs/upstream-monitor/base"], check=False)
        if res.returncode != 0:
            print(f"Failed to fetch refs/tags/{base_tag}, trying as branch/commit...")
            # Try fetching it as whatever ref it might be
            res2 = run_cmd(["git", "fetch", "--no-tags", "upstream", f"{base_tag}:refs/upstream-monitor/base"], check=False)
            if res2.returncode != 0:
                 print(f"::warning::Failed to fetch base tag {base_tag}")

    print(f"Fetching head tag {head_tag}...")
    res = run_cmd(["git", "fetch", "--no-tags", "upstream", f"+refs/tags/{head_tag}:refs/upstream-monitor/head"], check=False)
    if res.returncode != 0:
        print(f"Failed to fetch refs/tags/{head_tag}, trying as branch/commit...")
        res2 = run_cmd(["git", "fetch", "--no-tags", "upstream", f"{head_tag}:refs/upstream-monitor/head"], check=False)
        if res2.returncode != 0:
            print(f"::error::Failed to fetch head tag {head_tag}")
            sys.exit(1)

    # Unshallow if needed for full history
    print("Checking if we need to unshallow...")
    res = run_cmd(["git", "rev-parse", "--is-shallow-repository"], check=False)
    if res.stdout.strip() == "true":
         print("Unshallowing...")
         run_cmd(["git", "fetch", "--unshallow", "upstream"], check=False)



def generate_diffs(base_tag, head_tag):
    print("Generating diffs...")
    stat = run_cmd(["git", "diff", "--stat", "refs/upstream-monitor/base", "refs/upstream-monitor/head"], check=False)
    patch = run_cmd(["git", "diff", "--patch", "--find-renames", "refs/upstream-monitor/base", "refs/upstream-monitor/head"], check=False)

    # get changed files
    name_status = run_cmd(["git", "diff", "--name-status", "--find-renames", "refs/upstream-monitor/base", "refs/upstream-monitor/head"], check=False)

    changed_files = []
    if name_status.returncode == 0 and name_status.stdout.strip():
        for line in name_status.stdout.strip().split('\n'):
            parts = line.split('\t')
            status = parts[0][0] # Added, Modified, Deleted, Renamed
            if status == 'R':
                changed_files.append({"status": "renamed", "old_path": parts[1], "path": parts[2]})
            elif status == 'A':
                changed_files.append({"status": "added", "path": parts[1]})
            elif status == 'D':
                changed_files.append({"status": "deleted", "path": parts[1]})
            else:
                changed_files.append({"status": "modified", "path": parts[1]})

    return stat.stdout, patch.stdout, changed_files

def get_file_map():
    map_path = ".github/upstream-file-map.json"
    if os.path.exists(map_path):
        try:
            with open(map_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"::warning::Failed to parse {map_path}: {e}")
    return {}

def compare_local_files(changed_files, head_tag):
    print("Comparing local files...")
    file_map = get_file_map()

    comparisons = []
    for f in changed_files:
        upstream_path = f["path"]
        # Default equivalent path is same path, or check map
        local_path = file_map.get(upstream_path, upstream_path)

        comp = {
            "upstream_path": upstream_path,
            "local_path": local_path,
            "upstream_status": f["status"]
        }

        if f.get("old_path"):
            comp["old_upstream_path"] = f["old_path"]

        if not os.path.exists(local_path):
            comp["local_status"] = "missing"
            comp["diff"] = ""
        else:
            # Get upstream latest file content
            res = run_cmd(["git", "show", f"refs/upstream-monitor/head:{upstream_path}"], check=False)
            if res.returncode == 0:
                upstream_content = res.stdout
                with open(local_path, "r") as local_f:
                    local_content = local_f.read()

                if upstream_content == local_content:
                    comp["local_status"] = "identical"
                    comp["diff"] = ""
                else:
                    comp["local_status"] = "differs"
                    # Generate a diff between the two
                    with open("/tmp/upstream_file_tmp", "w") as tmp_f:
                        tmp_f.write(upstream_content)

                    diff_res = run_cmd(["git", "diff", "--no-index", "--", "/tmp/upstream_file_tmp", local_path], check=False)
                    # git diff --no-index returns 1 if there's a diff
                    comp["diff"] = diff_res.stdout
            else:
                comp["local_status"] = "upstream_missing" # shouldn't happen unless deleted
                comp["diff"] = ""

        comparisons.append(comp)

    return comparisons


import hashlib

def get_commits_and_prs(upstream_repo, base_tag, head_tag):
    print("Fetching commits and PRs...")
    log_cmd = ["git", "log", "--format=%H%x00%s", f"refs/upstream-monitor/base..refs/upstream-monitor/head"]
    res = run_cmd(log_cmd, check=False)

    commits = []
    prs = []

    if res.returncode == 0 and res.stdout.strip():
        for line in res.stdout.strip().split('\n'):
            if not line: continue
            parts = line.split('\0')
            sha = parts[0]
            msg = parts[1] if len(parts) > 1 else ""
            commits.append({"sha": sha, "msg": msg})

            # Try to fetch PR
            # For simplicity, we just look for PRs via GitHub API
            pr_res = run_cmd(["gh", "api", f"repos/{upstream_repo}/commits/{sha}/pulls"], check=False)
            if pr_res.returncode == 0:
                try:
                    pr_list = json.loads(pr_res.stdout)
                    for pr in pr_list:
                        prs.append({
                            "number": pr["number"],
                            "title": pr["title"],
                            "url": pr["html_url"],
                            "author": pr["user"]["login"],
                            "merged_at": pr.get("merged_at", ""),
                            "body": pr.get("body", "") or ""
                        })
                except Exception as e:
                    pass

    # deduplicate PRs
    unique_prs = {pr["number"]: pr for pr in prs}.values()
    return commits, list(unique_prs)

def generate_fingerprint(upstream_repo, base_tag, head_tag, repo, branch, diffstat, comparisons):
    h = hashlib.sha256()
    h.update(f"{upstream_repo}|{base_tag}|{head_tag}|{repo}|{branch}|{diffstat}".encode('utf-8'))
    # add local comparisons hash
    for c in comparisons:
        h.update(f"{c['upstream_path']}|{c['local_path']}|{c.get('local_status')}".encode('utf-8'))
    return h.hexdigest()

def truncate_text(text, max_len=1000):
    if not text: return ""
    if len(text) <= max_len: return text
    return text[:max_len] + "\n... (truncated)"

def build_markdown(args, upstream_repo, base_tag, head_tag, stat, patch, changed_files, comparisons, commits, prs, fingerprint):
    branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)

    branch = os.environ.get("GITHUB_REF_NAME")
    if not branch:
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"

    commit_res = run_cmd(["git", "rev-parse", "HEAD"], check=False)
    local_commit = commit_res.stdout.strip() if commit_res.returncode == 0 else "unknown"

    run_url = f"https://github.com/{args.repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"

    md = [
        "A new upstream release/change range was detected.",
        "",
        "## Summary",
        "",
        f"- Upstream repo: {upstream_repo}",
        f"- Release range: {base_tag}...{head_tag}" if base_tag else f"- Upstream tag: {head_tag}",
        f"- Upstream compare URL: https://github.com/{upstream_repo}/compare/{base_tag}...{head_tag}" if base_tag else f"- Upstream URL: https://github.com/{upstream_repo}/tree/{head_tag}",
        f"- Local branch: {branch}",
        f"- Local commit: {local_commit}",
        f"- Workflow run: {run_url}",
        f"- Force mode: {args.force}",
        f"- Fingerprint: {fingerprint}",
        "",
    ]


    # Release notes
    rel_res = None
    try:
        rel_res = run_cmd(["gh", "api", f"repos/{upstream_repo}/releases/tags/{head_tag}"], check=False)
    except FileNotFoundError:
        pass

    if rel_res and rel_res.returncode == 0:

        try:
            rel = json.loads(rel_res.stdout)
            md.extend([
                "## Release notes",
                "",
                f"**{rel.get('name', head_tag)}** ({rel.get('published_at', '')})",
                f"[Release URL]({rel.get('html_url', '')})",
                "",
                truncate_text(rel.get('body', ''), 2000),
                ""
            ])
        except Exception: pass

    md.extend([
        "## Upstream commit context",
        ""
    ])
    for c in commits[:20]: # Limit to 20 for brevity in table
        short_sha = c["sha"][:7]
        url = f"https://github.com/{upstream_repo}/commit/{c['sha']}"
        md.append(f"- [{short_sha}]({url}) {c['msg']}")
    if len(commits) > 20:
        md.append(f"- ... and {len(commits) - 20} more commits.")
    md.append("")

    if prs:
        md.extend([
            "## Upstream PR context",
            ""
        ])
        for pr in prs:
            md.append(f"- [#{pr['number']}]({pr['url']}) **{pr['title']}** by @{pr['author']}")
        md.append("")

    md.extend([
        "## Changed upstream files",
        "",
        "| Status | Upstream file | Local equivalent | Upstream latest | Upstream previous | Local file |",
        "| --- | --- | --- | --- | --- | --- |"
    ])

    for c in comparisons:
        u_url_head = f"https://github.com/{upstream_repo}/blob/{head_tag}/{c['upstream_path']}"
        u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{c['upstream_path']}" if base_tag else ""

        # Link to old path if renamed
        if c.get("old_upstream_path") and base_tag:
            u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{c['old_upstream_path']}"

        local_url = f"https://github.com/{args.repo}/blob/{branch}/{c['local_path']}"

        up_prev = f"[link]({u_url_base})" if u_url_base and c['upstream_status'] != 'added' else "N/A"
        up_latest = f"[link]({u_url_head})" if c['upstream_status'] != 'deleted' else "N/A"

        md.append(f"| {c['upstream_status']} | `{c['upstream_path']}` | `{c['local_path']}` | {up_latest} | {up_prev} | [link]({local_url}) |")

    md.extend([
        "",
        "## Upstream release-to-release diffstat",
        "",
        "```text",
        stat if stat else "No stat available",
        "```",
        ""
    ])

    diff_text = patch if patch else "No diff available"
    if len(diff_text) > 10000:
        diff_text = diff_text[:10000] + "\n... (diff truncated, see workflow artifacts or run reproduce commands)"

    md.extend([
        "## Upstream release-to-release diff",
        "",
        "```diff",
        diff_text,
        "```",
        ""
    ])

    md.extend([
        "## Equivalent-file comparison against local current codebase",
        ""
    ])

    for c in comparisons:
        md.append(f"### `{c['upstream_path']}`")
        u_url = f"https://github.com/{upstream_repo}/blob/{head_tag}/{c['upstream_path']}"
        l_url = f"https://github.com/{args.repo}/blob/{branch}/{c['local_path']}"
        md.append(f"- Upstream latest: [link]({u_url})")
        md.append(f"- Local equivalent: [link]({l_url})")
        md.append(f"- Status: {c['local_status']}")
        md.append("")
        if c['diff']:
            f_diff = c['diff']
            if len(f_diff) > 2000:
                f_diff = f_diff[:2000] + "\n... (truncated)"
            md.extend([
                "```diff",
                f_diff,
                "```",
                ""
            ])

    md.extend([
        "## Reproduce locally",
        "",
        "```bash",
        f"git clone https://github.com/{args.repo}.git",
        f"cd {args.repo.split('/')[-1]}",
        f"git remote add upstream https://github.com/{upstream_repo}.git",
        "git fetch upstream --tags",
        f"git diff {base_tag} {head_tag}" if base_tag else f"git show {head_tag}",
        "```",
        "",
        "## Checklist",
        "",
        "- [ ] Review release notes",
        "- [ ] Inspect changed upstream files",
        "- [ ] Compare equivalent local files",
        "- [ ] Decide which changes to port",
        "- [ ] Add resolved tag/range to `.github/upstream-release-resolved-tags.txt`",
        "- [ ] Close this issue when triage is complete",
        "",
        f"<!-- upstream-monitor:fingerprint:{fingerprint} -->"
    ])

    return "\n".join(md)


def check_resolved_tags(upstream_repo, head_tag):
    resolved_file = ".github/upstream-release-resolved-tags.txt"
    if not os.path.exists(resolved_file):
        return False

    try:
        with open(resolved_file, "r") as f:
            lines = f.readlines()
    except Exception:
        return False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Accept exact tag, v<tag>, <tag>
        # Accept tuple format owner/repo@tag
        if line == head_tag or line == f"v{head_tag}" or f"v{line}" == head_tag:
            return True

        if line == f"{upstream_repo}@{head_tag}":
            return True

        # Range format owner/repo@base..head (basic support)
        if ".." in line and line.endswith(head_tag):
            return True

    return False

def manage_issue(args, title, body, fingerprint):
    if args.dry_run:
        print("Dry run: skipping issue creation/update.")
        return

    if not args.force and check_resolved_tags(args.upstream_repo, args.head_tag):
        print(f"Skipping: {args.head_tag} is marked as resolved in .github/upstream-release-resolved-tags.txt")
        return

    # Check for existing issue (open or closed)

    search_query = f"{title} in:title"

    open_res = run_cmd(["gh", "issue", "list", "--repo", args.repo, "--state", "open", "--search", search_query, "--json", "number", "--jq", ".[0].number // \"\""], check=False)
    closed_res = run_cmd(["gh", "issue", "list", "--repo", args.repo, "--state", "closed", "--search", search_query, "--json", "number", "--jq", ".[0].number // \"\""], check=False)

    open_num = open_res.stdout.strip() if open_res.returncode == 0 else ""
    closed_num = closed_res.stdout.strip() if closed_res.returncode == 0 else ""

    if closed_num and not args.force:
        print(f"Skipping: issue #{closed_num} is closed (use --force to override).")
        return

    if open_num:
        # Check fingerprint
        view_res = run_cmd(["gh", "issue", "view", open_num, "--repo", args.repo, "--comments", "--json", "comments,body"], check=False)
        if view_res.returncode == 0:
            import re
            content = view_res.stdout
            match = re.search(r"<!-- upstream-monitor:fingerprint:([a-f0-9]{64}) -->", content)
            if match and match.group(1) == fingerprint and not args.force:
                print(f"Skipping: issue #{open_num} is up to date (fingerprint match).")
                return

        print(f"Updating existing issue #{open_num}...")
        # Write body to file
        body_file = "/tmp/upstream_issue_body.md"
        with open(body_file, "w") as f:
            f.write(body)
        run_cmd(["gh", "issue", "comment", open_num, "--repo", args.repo, "--body-file", body_file], check=False)
    else:
        print("Creating new issue...")
        body_file = "/tmp/upstream_issue_body.md"
        with open(body_file, "w") as f:
            f.write(body)

        # Valid pattern as requested: NO --json --jq on `gh issue create`
        create_res = run_cmd(["gh", "issue", "create", "--repo", args.repo, "--title", title, "--body-file", body_file], check=False)
        if create_res.returncode == 0:
            url = create_res.stdout.strip()
            print(f"Created issue: {url}")
        else:
            print(f"::error::Failed to create issue: {create_res.stderr}")
def main():
    import os

    parser = argparse.ArgumentParser(description="Upstream Release Monitor")
    parser.add_argument("--repo", required=True, help="Local repo (owner/name)")
    parser.add_argument("--upstream-repo", required=True, help="Upstream repo (owner/name)")
    parser.add_argument("--head-tag", help="Optional exact upstream latest tag/ref")
    parser.add_argument("--base-tag", help="Optional upstream base tag/ref")
    parser.add_argument("--include-prerelease", action="store_true", help="Consider prereleases")
    parser.add_argument("--force", action="store_true", help="Bypass suppression")
    parser.add_argument("--dry-run", action="store_true", help="Do not create/update issue")
    parser.add_argument("--out-dir", default="artifacts", help="Directory to store output files")

    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    head_tag, base_tag = resolve_tags(args)
    print(f"Resolved head_tag: {head_tag}, base_tag: {base_tag}")



    fetch_upstream(args.upstream_repo, head_tag, base_tag)

    stat, patch, changed_files, comparisons = "", "", [], []
    if base_tag:
        stat, patch, changed_files = generate_diffs(base_tag, head_tag)
        comparisons = compare_local_files(changed_files, head_tag)

        with open(os.path.join(args.out_dir, "upstream-release.diff"), "w") as f:
            f.write(patch)

    commits, prs = get_commits_and_prs(args.upstream_repo, base_tag, head_tag)

    with open(os.path.join(args.out_dir, "metadata.json"), "w") as f:
        json.dump({
            "head_tag": head_tag,
            "base_tag": base_tag,
            "changed_files": changed_files,
            "comparisons": comparisons
        }, f, indent=2)

    branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)

    branch = os.environ.get("GITHUB_REF_NAME")
    if not branch:
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"


    fingerprint = generate_fingerprint(args.upstream_repo, base_tag, head_tag, args.repo, branch, stat, comparisons)

    md_report = build_markdown(args, args.upstream_repo, base_tag, head_tag, stat, patch, changed_files, comparisons, commits, prs, fingerprint)

    report_file = os.path.join(args.out_dir, "upstream-monitor-report.md")
    with open(report_file, "w") as f:
        f.write(md_report)

    title = f"Upstream release monitor: {args.upstream_repo} {base_tag}...{head_tag}" if base_tag else f"Upstream release monitor: {args.upstream_repo} {head_tag}"
    manage_issue(args, title, md_report, fingerprint)
