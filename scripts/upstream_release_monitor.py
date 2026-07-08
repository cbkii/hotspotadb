import argparse
import subprocess
import json
import os
import shutil
import hashlib
import tempfile
import urllib.parse
from typing import Sequence, Union
from pathlib import Path

def run_cmd(
    cmd: Sequence[str],
    *,
    check: bool = True,
    timeout: float = 120.0,
    capture_output: bool = True,
    cwd: Union[str, Path, None] = None,
    ok_codes: set[int] = None,
) -> subprocess.CompletedProcess:
    if ok_codes is None:
        ok_codes = {0}
    try:
        result = subprocess.run(
            cmd,
            check=False,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            shell=False
        )
        if check and result.returncode not in ok_codes:
            cmd_str = " ".join(cmd)
            print(f"::error::Command failed: {cmd_str}")
            if result.stdout:
                print(f"stdout:\n{result.stdout[:1000]}")
            if result.stderr:
                print(f"stderr:\n{result.stderr[:1000]}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result
    except subprocess.TimeoutExpired as e:
        cmd_str = " ".join(cmd)
        print(f"::error::Command timed out: {cmd_str}")
        raise

def get_releases(upstream_repo, include_prerelease=False):
    cmd = ["gh", "api", f"repos/{upstream_repo}/releases", "--paginate", "--slurp"]
    result = run_cmd(cmd, check=True)
    try:
        releases = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Failed to decode releases JSON from GitHub API.")
        return []

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
            return None, None
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

class FetchResult:
    def __init__(self, base_fetched, head_fetched, base_ref, head_ref):
        self.base_fetched = base_fetched
        self.head_fetched = head_fetched
        self.base_ref = base_ref
        self.head_ref = head_ref

def fetch_upstream(upstream_repo, head_tag, base_tag) -> FetchResult:
    print("Adding upstream remote...")
    # use set-url or add to ensure deterministic remote
    res = run_cmd(["git", "remote", "add", "upstream", f"https://github.com/{upstream_repo}.git"], check=False)
    if res.returncode != 0:
        run_cmd(["git", "remote", "set-url", "upstream", f"https://github.com/{upstream_repo}.git"], check=True)

    base_fetched = False
    head_fetched = False

    if base_tag:
        print(f"Fetching base tag {base_tag}...")
        res = run_cmd(["git", "fetch", "--no-tags", "upstream", f"+refs/tags/{base_tag}:refs/upstream-monitor/base"], check=False)
        if res.returncode == 0:
            base_fetched = True
        else:
            print(f"Failed to fetch refs/tags/{base_tag}, trying as branch/commit...")
            res2 = run_cmd(["git", "fetch", "--no-tags", "upstream", f"{base_tag}:refs/upstream-monitor/base"], check=False)
            if res2.returncode == 0:
                base_fetched = True
            else:
                print(f"::warning::Failed to fetch base tag {base_tag}")

    print(f"Fetching head tag {head_tag}...")
    res = run_cmd(["git", "fetch", "--no-tags", "upstream", f"+refs/tags/{head_tag}:refs/upstream-monitor/head"], check=False)
    if res.returncode == 0:
        head_fetched = True
    else:
        print(f"Failed to fetch refs/tags/{head_tag}, trying as branch/commit...")
        res2 = run_cmd(["git", "fetch", "--no-tags", "upstream", f"{head_tag}:refs/upstream-monitor/head"], check=False)
        if res2.returncode == 0:
            head_fetched = True
        else:
            print(f"::error::Failed to fetch head tag {head_tag}")

    if head_fetched:
        print("Checking if we need to unshallow...")
        res = run_cmd(["git", "rev-parse", "--is-shallow-repository"], check=False)
        if res.stdout.strip() == "true":
             print("Unshallowing...")
             run_cmd(["git", "fetch", "--unshallow", "upstream"], check=False)

    return FetchResult(base_fetched, head_fetched, "refs/upstream-monitor/base" if base_fetched else None, "refs/upstream-monitor/head" if head_fetched else None)

def generate_diffs(base_ref, head_ref):
    print("Generating diffs...")
    stat = run_cmd(["git", "diff", "--stat", base_ref, head_ref], check=True)
    patch = run_cmd(["git", "diff", "--patch", "--find-renames", base_ref, head_ref], check=True)

    # get changed files using NUL delimited format
    name_status = run_cmd(["git", "diff", "--name-status", "-z", "--find-renames", base_ref, head_ref], check=True)

    changed_files = []
    if name_status.stdout.strip():
        parts = name_status.stdout.split('\x00')
        i = 0
        while i < len(parts) - 1:
            status_str = parts[i]
            status_char = status_str[0] if status_str else 'U'

            if status_char == 'R' or status_char == 'C':
                old_path = parts[i+1]
                new_path = parts[i+2]
                status_name = "renamed" if status_char == 'R' else "copied"
                changed_files.append({"status": status_name, "old_path": old_path, "path": new_path})
                i += 3
            else:
                path = parts[i+1]
                status_name = "modified"
                if status_char == 'A': status_name = "added"
                elif status_char == 'D': status_name = "deleted"
                elif status_char == 'T': status_name = "type-changed"
                elif status_char == 'U': status_name = "unknown"
                changed_files.append({"status": status_name, "path": path})
                i += 2

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

def compare_local_files(changed_files, head_ref, out_dir):
    print("Comparing local files...")
    file_map = get_file_map()

    comparisons = []
    comp_dir = os.path.join(out_dir, "equivalent-file-comparisons")
    os.makedirs(comp_dir, exist_ok=True)

    for idx, f in enumerate(changed_files):
        upstream_path = f["path"]
        local_path = file_map.get(upstream_path, upstream_path)

        comp = {
            "upstream_path": upstream_path,
            "local_path": local_path,
            "upstream_status": f["status"],
            "local_status": "unknown",
            "diff": ""
        }

        if f.get("old_path"):
            comp["old_upstream_path"] = f["old_path"]

        if not os.path.exists(local_path):
            comp["local_status"] = "missing"
        else:
            # Get upstream latest file content as bytes
            res_raw = subprocess.run(["git", "show", f"{head_ref}:{upstream_path}"], capture_output=True, shell=False, check=False)
            if res_raw.returncode == 0:
                upstream_content = res_raw.stdout
                with open(local_path, "rb") as local_f:
                    local_content = local_f.read()

                if upstream_content == local_content:
                    comp["local_status"] = "identical"
                else:
                    comp["local_status"] = "differs"
                    # Generate a diff between the two using temp file
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
                        tmp_f.write(upstream_content)
                        tmp_name = tmp_f.name

                    try:
                        # use text diff with replacement
                        diff_res = run_cmd(["git", "diff", "--no-index", "--text", "--", tmp_name, local_path], check=False, ok_codes={0, 1})
                        comp["diff"] = diff_res.stdout
                        if "Binary files" in diff_res.stdout:
                            comp["local_status"] = "binary differs"
                    finally:
                        os.remove(tmp_name)
            else:
                comp["local_status"] = "upstream_missing"

        comparisons.append(comp)

        # write individual comparison file
        safe_name = f"{idx}_{upstream_path.replace('/', '_')}.diff"
        if comp["diff"]:
            with open(os.path.join(comp_dir, safe_name), "w", encoding="utf-8") as out_f:
                out_f.write(comp["diff"])

    return comparisons

def get_commits_and_prs(upstream_repo, base_ref, head_ref, max_pr_lookups):
    print("Fetching commits and PRs...")
    if base_ref:
        log_cmd = ["git", "log", "--format=%H%x00%s", f"{base_ref}..{head_ref}"]
    else:
        log_cmd = ["git", "log", "-1", "--format=%H%x00%s", head_ref]

    res = run_cmd(log_cmd, check=True)

    commits = []
    prs = []

    if res.stdout.strip():
        for line in res.stdout.strip().split('\n'):
            if not line: continue
            parts = line.split('\x00')
            sha = parts[0]
            msg = parts[1] if len(parts) > 1 else ""
            commits.append({"sha": sha, "msg": msg})

    # Try to fetch PR for first N commits
    for c in commits[:max_pr_lookups]:
        pr_res = run_cmd(["gh", "api", f"repos/{upstream_repo}/commits/{c['sha']}/pulls"], check=False)
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
            except Exception:
                pass

    unique_prs = {pr["number"]: pr for pr in prs}.values()
    return commits, list(unique_prs)

def generate_fingerprint(upstream_repo, base_tag, head_tag, repo, branch, diffstat, comparisons):
    h = hashlib.sha256()
    h.update(f"{upstream_repo}|{base_tag}|{head_tag}|{repo}|{branch}|{diffstat}".encode('utf-8'))
    for c in comparisons:
        content_hash = hashlib.sha256(c['diff'].encode('utf-8', errors='replace')).hexdigest()
        h.update(f"{c['upstream_path']}|{c['local_path']}|{c.get('local_status')}|{content_hash}".encode('utf-8'))
    return h.hexdigest()

def truncate_text(text, max_len=1000):
    if not text: return ""
    if len(text) <= max_len: return text
    return text[:max_len] + "\n... (truncated)"

def build_markdown(args, upstream_repo, base_tag, head_tag, stat, patch, changed_files, comparisons, commits, prs, fingerprint, local_commit, branch):
    run_url = f"https://github.com/{args.repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"

    md = [
        "A new upstream release/change range was detected.",
        "",
        "## Summary",
        "",
        f"- Upstream repo: {upstream_repo}",
    ]
    if base_tag:
        md.append(f"- Release range: {base_tag}...{head_tag}")
        md.append(f"- Upstream compare URL: https://github.com/{upstream_repo}/compare/{base_tag}...{head_tag}")
    else:
        md.append(f"- Upstream tag: {head_tag}")
        md.append(f"- Upstream URL: https://github.com/{upstream_repo}/tree/{head_tag}")

    md.extend([
        f"- Local branch: {branch}",
        f"- Local commit: {local_commit}",
        f"- Workflow run: {run_url}",
        f"- Force mode: {args.force}",
        f"- Fingerprint: {fingerprint}",
        "",
    ])

    # Release notes
    try:
        rel_res = run_cmd(["gh", "api", f"repos/{upstream_repo}/releases/tags/{head_tag}"], check=False)
        if rel_res.returncode == 0:
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
    for c in commits[:20]:
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
            if pr['body']:
                md.append(f"  > {truncate_text(pr['body'], 200).replace(chr(10), ' ')}")
        md.append("")

    md.extend([
        "## Changed upstream files",
        "",
        "| Status | Upstream file | Local equivalent | Upstream latest | Upstream previous | Local file |",
        "| --- | --- | --- | --- | --- | --- |"
    ])

    for c in comparisons:
        up_path_quoted = urllib.parse.quote(c['upstream_path'], safe="/")
        u_url_head = f"https://github.com/{upstream_repo}/blob/{head_tag}/{up_path_quoted}"

        u_url_base = ""
        if base_tag:
            if c.get("old_upstream_path"):
                old_path_quoted = urllib.parse.quote(c['old_upstream_path'], safe="/")
                u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{old_path_quoted}"
            else:
                u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{up_path_quoted}"

        local_path_quoted = urllib.parse.quote(c['local_path'], safe="/")
        local_url = f"https://github.com/{args.repo}/blob/{local_commit}/{local_path_quoted}"

        up_prev = f"[link]({u_url_base})" if u_url_base and c['upstream_status'] not in ('added', 'copied') else "N/A"
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
        up_path_quoted = urllib.parse.quote(c['upstream_path'], safe="/")
        u_url = f"https://github.com/{upstream_repo}/blob/{head_tag}/{up_path_quoted}"

        local_path_quoted = urllib.parse.quote(c['local_path'], safe="/")
        l_url = f"https://github.com/{args.repo}/blob/{local_commit}/{local_path_quoted}"

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

def check_resolved_tags(upstream_repo, head_tag, base_tag):
    resolved_file = ".github/upstream-release-resolved-tags.txt"
    if not os.path.exists(resolved_file):
        return False

    try:
        with open(resolved_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line == head_tag or line == f"v{head_tag}" or f"v{line}" == head_tag:
            return True

        if line == f"{upstream_repo}@{head_tag}":
            return True

        if base_tag:
            if line == f"{upstream_repo}@{base_tag}..{head_tag}":
                return True
            if line == f"{base_tag}..{head_tag}":
                return True

    return False

def manage_issue(args, title, body, fingerprint, head_tag, base_tag):
    if args.dry_run:
        print("Dry run: skipping issue creation/update.")
        return

    if not args.force and check_resolved_tags(args.upstream_repo, head_tag, base_tag):
        print(f"Skipping: {head_tag} is marked as resolved in .github/upstream-release-resolved-tags.txt")
        return

    search_query = f"{title} in:title"

    open_res = run_cmd(["gh", "issue", "list", "--repo", args.repo, "--state", "open", "--search", search_query, "--json", "number", "--jq", ".[0].number // \"\""], check=False)
    open_num = open_res.stdout.strip() if open_res.returncode == 0 else ""

    if open_num:
        view_res = run_cmd(["gh", "issue", "view", open_num, "--repo", args.repo, "--comments", "--json", "comments,body"], check=False)
        if view_res.returncode == 0:
            import re
            content = view_res.stdout
            match = re.search(r"<!-- upstream-monitor:fingerprint:([a-f0-9]{64}) -->", content)
            if match and match.group(1) == fingerprint and not args.force:
                print(f"Skipping: issue #{open_num} is up to date (fingerprint match).")
                return

        print(f"Updating existing issue #{open_num}...")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w", encoding="utf-8") as body_file:
            body_file.write(body)
            body_path = body_file.name

        try:
            # Try to edit body
            edit_res = run_cmd(["gh", "issue", "edit", open_num, "--repo", args.repo, "--body-file", body_path], check=False)
            if edit_res.returncode == 0:
                 print("Issue updated.")
            else:
                 # fallback to comment
                 run_cmd(["gh", "issue", "comment", open_num, "--repo", args.repo, "--body-file", body_path], check=True)
        finally:
            os.remove(body_path)
    else:
        # Before creating, optionally check closed issues, but if it's not resolved in tags, we recreate it deterministically
        closed_res = run_cmd(["gh", "issue", "list", "--repo", args.repo, "--state", "closed", "--search", search_query, "--json", "number", "--jq", ".[0].number // \"\""], check=False)
        closed_num = closed_res.stdout.strip() if closed_res.returncode == 0 else ""
        if closed_num and not args.force:
            print(f"Skipping: issue #{closed_num} is closed but not marked resolved in tags file. Use --force to override.")
            return

        print("Creating new issue...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w", encoding="utf-8") as body_file:
            body_file.write(body)
            body_path = body_file.name

        try:
            create_res = run_cmd(["gh", "issue", "create", "--repo", args.repo, "--title", title, "--body-file", body_path], check=False)
            if create_res.returncode == 0:
                url = create_res.stdout.strip()
                print(f"Created issue: {url}")
            else:
                print(f"::error::Failed to create issue: {create_res.stderr}")
        finally:
            os.remove(body_path)

def main() -> int:
    parser = argparse.ArgumentParser(description="Upstream Release Monitor")
    parser.add_argument("--repo", required=True, help="Local repo (owner/name)")
    parser.add_argument("--upstream-repo", required=True, help="Upstream repo (owner/name)")
    parser.add_argument("--head-tag", help="Optional exact upstream latest tag/ref")
    parser.add_argument("--base-tag", help="Optional upstream base tag/ref")
    parser.add_argument("--include-prerelease", action="store_true", help="Consider prereleases")
    parser.add_argument("--force", action="store_true", help="Bypass suppression")
    parser.add_argument("--dry-run", action="store_true", help="Do not create/update issue")
    parser.add_argument("--out-dir", default="artifacts", help="Directory to store output files")
    parser.add_argument("--max-pr-lookups", type=int, default=20, help="Max PRs to lookup")

    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    head_tag, base_tag = resolve_tags(args)
    if not head_tag:
        return 1

    print(f"Resolved head_tag: {head_tag}, base_tag: {base_tag}")

    fetch_res = fetch_upstream(args.upstream_repo, head_tag, base_tag)
    if not fetch_res.head_fetched:
        print("::error::Failed to fetch head ref.")
        return 1

    stat, patch, changed_files, comparisons = "", "", [], []

    # Check if we should fallback to single tag mode
    if base_tag and fetch_res.base_fetched:
        stat, patch, changed_files = generate_diffs(fetch_res.base_ref, fetch_res.head_ref)
    else:
        print("Base tag not fetched, operating in single-tag mode.")
        # Single tag mode diff generation
        stat_res = run_cmd(["git", "show", "--stat", fetch_res.head_ref], check=True)
        stat = stat_res.stdout

        name_status = run_cmd(["git", "show", "--name-status", "-z", "--find-renames", fetch_res.head_ref], check=True)
        if name_status.stdout.strip():
            parts = name_status.stdout.split('\x00')
            i = 0
            while i < len(parts) - 1:
                # git show output starts with commit headers, skip till we find the status
                status_str = parts[i]
                if '\n' in status_str: # commit header chunk
                     # find the last part which should be the status
                     status_str = status_str.split('\n')[-1]

                status_char = status_str[0] if status_str else 'U'

                if status_char == 'R' or status_char == 'C':
                    old_path = parts[i+1]
                    new_path = parts[i+2]
                    status_name = "renamed" if status_char == 'R' else "copied"
                    changed_files.append({"status": status_name, "old_path": old_path, "path": new_path})
                    i += 3
                else:
                    path = parts[i+1]
                    status_name = "modified"
                    if status_char == 'A': status_name = "added"
                    elif status_char == 'D': status_name = "deleted"
                    changed_files.append({"status": status_name, "path": path})
                    i += 2

    comparisons = compare_local_files(changed_files, fetch_res.head_ref, args.out_dir)

    with open(os.path.join(args.out_dir, "upstream-release.diff"), "w", encoding="utf-8") as f:
        f.write(patch)

    commits, prs = get_commits_and_prs(args.upstream_repo, fetch_res.base_ref, fetch_res.head_ref, args.max_pr_lookups)

    with open(os.path.join(args.out_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "head_tag": head_tag,
            "base_tag": base_tag,
            "changed_files": changed_files,
            "comparisons": comparisons
        }, f, indent=2)

    branch = os.environ.get("GITHUB_REF_NAME")
    if not branch:
        branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"

    commit_res = run_cmd(["git", "rev-parse", "HEAD"], check=False)
    local_commit = commit_res.stdout.strip() if commit_res.returncode == 0 else "unknown"

    fingerprint = generate_fingerprint(args.upstream_repo, base_tag, head_tag, args.repo, branch, stat, comparisons)

    md_report = build_markdown(args, args.upstream_repo, base_tag, head_tag, stat, patch, changed_files, comparisons, commits, prs, fingerprint, local_commit, branch)

    report_file = os.path.join(args.out_dir, "upstream-monitor-report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_report)

    title = f"Upstream release monitor: {args.upstream_repo} {base_tag}...{head_tag}" if base_tag else f"Upstream release monitor: {args.upstream_repo} {head_tag}"
    manage_issue(args, title, md_report, fingerprint, head_tag, base_tag)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
