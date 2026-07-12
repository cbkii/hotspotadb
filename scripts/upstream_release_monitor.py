import argparse
import subprocess
import json
import os
import hashlib
import tempfile
import urllib.parse
from typing import Sequence, Union
from pathlib import Path
import shlex


def run_cmd(
    cmd: Sequence[Union[str, Path]],
    *,
    check: bool = True,
    timeout: float = 120.0,
    capture_output: bool = True,
    cwd: Union[str, Path, None] = None,
    ok_codes: set[int] = None,
    text: bool = True,
) -> subprocess.CompletedProcess:
    if not cmd:
        raise ValueError("Command sequence cannot be empty")

    cmd_str_list = [str(arg) for arg in cmd]
    cmd_str = shlex.join(cmd_str_list)

    if ok_codes is None:
        ok_codes = {0}
    try:
        # sourcery skip: subprocess-run-check
        # Arguments are passed as a list with shell=False, so this is safe.
        result = subprocess.run(  # nosec
            cmd_str_list,
            check=False,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            cwd=cwd,
            shell=False,
        )
        if check and result.returncode not in ok_codes:
            print(f"::error::Command failed: {cmd_str}")
            if capture_output:
                if text:
                    if result.stdout:
                        print(f"stdout:\n{result.stdout[:1000]}")
                    if result.stderr:
                        print(f"stderr:\n{result.stderr[:1000]}")
                else:
                    if result.stdout:
                        print(
                            f"stdout:\n{result.stdout[:1000].decode('utf-8', 'replace')}"
                        )
                    if result.stderr:
                        print(
                            f"stderr:\n{result.stderr[:1000].decode('utf-8', 'replace')}"
                        )
            raise subprocess.CalledProcessError(
                result.returncode, cmd_str_list, result.stdout, result.stderr
            )
        return result
    except subprocess.TimeoutExpired:
        print(f"::error::Command timed out: {cmd_str}")
        raise


import re


def validate_repo_format(repo: str) -> None:
    if not repo or not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo):
        raise ValueError(f"Invalid repository format: {repo}")


def validate_git_ref(ref: str) -> None:
    if not ref or not re.match(r"^[A-Za-z0-9_./-]+$", ref) or ref.startswith("-"):
        raise ValueError(f"Invalid git ref: {ref}")


def normalize_release_payload(raw):
    """
    Normalizes GitHub API release payloads into a flat list of valid release dictionaries.
    Handles:
    - flat REST response list
    - `gh api --paginate --slurp` list-of-lists
    - mixed defensive payloads
    """
    releases = []

    if not isinstance(raw, list):
        return releases

    for item in raw:
        if isinstance(item, list):
            for sub_item in item:
                if isinstance(sub_item, dict) and isinstance(
                    sub_item.get("tag_name"), str
                ):
                    releases.append(sub_item)
        elif isinstance(item, dict) and isinstance(item.get("tag_name"), str):
            releases.append(item)

    return releases


def get_releases_paginated(upstream_repo, include_prerelease=False, max_pages=10):
    eligible_releases = []
    page = 1

    while page <= max_pages:
        cmd = ["gh", "api", f"repos/{upstream_repo}/releases?per_page=100&page={page}"]
        try:
            result = run_cmd(cmd, check=True, timeout=60.0)
        except subprocess.CalledProcessError as e:
            print(f"::error::Failed to fetch releases from GitHub API: {e}")
            raise

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("::error::Failed to decode releases JSON from GitHub API.")
            raise ValueError("Invalid JSON from GitHub API")

        if not raw:
            break

        releases = normalize_release_payload(raw)

        for r in releases:
            if r.get("draft"):
                continue
            if r.get("prerelease") and not include_prerelease:
                continue
            eligible_releases.append(r)

        # Check if there is a next page using headers (gh api doesn't easily expose this, so we just check if we got 100)
        if len(raw) < 100:
            break

        page += 1

    return eligible_releases


def resolve_tags(args):
    head_tag = args.head_tag
    base_tag = args.base_tag

    if head_tag:
        validate_git_ref(head_tag)
    if base_tag:
        validate_git_ref(base_tag)

    # We need to fetch releases if:
    # - head_tag is not provided (we need the latest eligible)
    # - base_tag is not provided AND we intend to find the preceding release automatically
    # Wait, the instruction says: "An invalid explicit base is an error, not a silent downgrade."

    releases = None
    if not head_tag or not base_tag:
        releases = get_releases_paginated(args.upstream_repo, args.include_prerelease)

    if not head_tag:
        if not releases:
            print(f"::error::No eligible releases found for {args.upstream_repo}")
            return None, None
        for r in releases:
            head_tag = r.get("tag_name")
            if head_tag:
                break

    if not base_tag and args.base_tag is None:
        # We need to find the preceding release automatically
        found_head = False
        for r in releases:
            t = r.get("tag_name")
            if not t:
                continue
            if found_head:
                base_tag = t
                break
            if t == head_tag:
                found_head = True

        if not base_tag:
            print(
                f"::warning::Could not find a previous release for {head_tag}. Operating against empty tree."
            )
            # We don't set base_tag here. Later logic will handle empty base.

    if args.base_tag and not base_tag:
        # If an explicit base tag was provided but we failed to find it? No, if it was explicit, it is already base_tag.
        pass

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
    res = run_cmd(
        ["git", "remote", "add", "upstream", f"https://github.com/{upstream_repo}.git"],
        check=False,
    )
    if res.returncode != 0:
        run_cmd(
            [
                "git",
                "remote",
                "set-url",
                "upstream",
                f"https://github.com/{upstream_repo}.git",
            ],
            check=True,
        )

    base_fetched = False
    head_fetched = False

    if base_tag:
        print(f"Fetching base tag {base_tag}...")
        res = run_cmd(
            [
                "git",
                "fetch",
                "--no-tags",
                "upstream",
                f"+refs/tags/{base_tag}:refs/upstream-monitor/base",
            ],
            check=False,
        )
        if res.returncode == 0:
            base_fetched = True
        else:
            print(f"Failed to fetch refs/tags/{base_tag}, trying as branch/commit...")
            res2 = run_cmd(
                [
                    "git",
                    "fetch",
                    "--no-tags",
                    "upstream",
                    f"{base_tag}:refs/upstream-monitor/base",
                ],
                check=False,
            )
            if res2.returncode == 0:
                base_fetched = True
            else:
                print(f"::error::Failed to fetch base tag {base_tag}")
                raise RuntimeError(f"Failed to fetch explicit base tag {base_tag}")

    print(f"Fetching head tag {head_tag}...")
    res = run_cmd(
        [
            "git",
            "fetch",
            "--no-tags",
            "upstream",
            f"+refs/tags/{head_tag}:refs/upstream-monitor/head",
        ],
        check=False,
    )
    if res.returncode == 0:
        head_fetched = True
    else:
        print(f"Failed to fetch refs/tags/{head_tag}, trying as branch/commit...")
        res2 = run_cmd(
            [
                "git",
                "fetch",
                "--no-tags",
                "upstream",
                f"{head_tag}:refs/upstream-monitor/head",
            ],
            check=False,
        )
        if res2.returncode == 0:
            head_fetched = True
        else:
            print(f"::error::Failed to fetch head tag {head_tag}")
            raise RuntimeError(f"Failed to fetch explicit head tag {head_tag}")

    return FetchResult(
        base_fetched,
        head_fetched,
        "refs/upstream-monitor/base" if base_fetched else None,
        "refs/upstream-monitor/head" if head_fetched else None,
    )


def generate_diffs(base_ref, head_ref):
    print("Generating diffs...")
    stat = run_cmd(["git", "diff", "--stat", base_ref, head_ref], check=True)
    patch = run_cmd(
        ["git", "diff", "--patch", "--find-renames", base_ref, head_ref], check=True
    )

    # get changed files using NUL delimited format
    name_status = run_cmd(
        ["git", "diff", "--name-status", "-z", "--find-renames", base_ref, head_ref],
        check=True,
    )
    changed_files = parse_name_status_z(name_status.stdout)

    return stat.stdout, patch.stdout, changed_files


def parse_name_status_z(output: str) -> list[dict]:
    changed_files = []
    if not output or not output.strip("\x00"):
        return changed_files

    parts = output.split("\x00")
    i = 0
    while i < len(parts) - 1:
        status_str = parts[i]
        # Skip empty parts or purely newline parts just in case
        if not status_str or status_str == "\n":
            i += 1
            continue

        if "\n" in status_str:
            status_str = status_str.split("\n")[-1]
            if not status_str:
                i += 1
                continue

        status_char = status_str[0]

        if status_char in ("R", "C"):
            if i + 2 >= len(parts) or not parts[i + 1] or not parts[i + 2]:
                break  # Malformed
            old_path = parts[i + 1]
            new_path = parts[i + 2]
            status_name = "renamed" if status_char == "R" else "copied"
            changed_files.append(
                {"status": status_name, "old_path": old_path, "path": new_path}
            )
            i += 3
        else:
            if i + 1 >= len(parts) or not parts[i + 1]:
                break  # Malformed
            path = parts[i + 1]
            status_name = "modified"
            if status_char == "A":
                status_name = "added"
            elif status_char == "D":
                status_name = "deleted"
            elif status_char == "T":
                status_name = "type-changed"
            elif status_char == "U":
                status_name = "unknown"
            changed_files.append({"status": status_name, "path": path})
            i += 2

    return changed_files


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
            "diff": "",
        }

        if f.get("old_path"):
            comp["old_upstream_path"] = f["old_path"]

        if not os.path.exists(local_path):
            comp["local_status"] = "missing"
        else:
            # Get upstream latest file content as bytes
            res_raw = run_cmd(
                ["git", "show", f"{head_ref}:{upstream_path}"], check=False, text=False
            )
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
                        diff_res = run_cmd(
                            [
                                "git",
                                "diff",
                                "--no-index",
                                "--text",
                                "--",
                                tmp_name,
                                local_path,
                            ],
                            check=False,
                            ok_codes={0, 1},
                        )
                        comp["diff"] = diff_res.stdout
                        if "Binary files" in diff_res.stdout:
                            comp["local_status"] = "binary differs"
                    finally:
                        os.remove(tmp_name)
            else:
                comp["local_status"] = "upstream_missing"

        comparisons.append(comp)

        # write individual comparison file
        path_hash = hashlib.sha256(upstream_path.encode("utf-8")).hexdigest()[:16]
        safe_name = f"{idx}-{path_hash}.diff"
        comp["diff_artifact_name"] = safe_name
        if comp["diff"]:
            with open(
                os.path.join(comp_dir, safe_name), "w", encoding="utf-8"
            ) as out_f:
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
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\x00")
            sha = parts[0]
            msg = parts[1] if len(parts) > 1 else ""
            commits.append({"sha": sha, "msg": msg})

    # Try to fetch PR for first N commits
    for c in commits[:max_pr_lookups]:
        pr_res = run_cmd(
            ["gh", "api", f"repos/{upstream_repo}/commits/{c['sha']}/pulls"],
            check=False,
        )
        if pr_res.returncode == 0:
            try:
                pr_list = json.loads(pr_res.stdout)
                for pr in pr_list:
                    prs.append(
                        {
                            "number": pr["number"],
                            "title": pr["title"],
                            "url": pr["html_url"],
                            "author": pr["user"]["login"],
                            "merged_at": pr.get("merged_at", ""),
                            "body": pr.get("body", "") or "",
                        }
                    )
            except json.JSONDecodeError:
                pass

    unique_prs = {pr["number"]: pr for pr in prs}.values()
    return commits, list(unique_prs)


def generate_fingerprint(
    upstream_repo, base_tag, head_tag, repo, branch, diffstat, comparisons
):
    h = hashlib.sha256()
    h.update(
        f"{upstream_repo}|{base_tag}|{head_tag}|{repo}|{branch}|{diffstat}".encode(
            "utf-8"
        )
    )
    for c in comparisons:
        content_hash = hashlib.sha256(
            c["diff"].encode("utf-8", errors="replace")
        ).hexdigest()
        h.update(
            f"{c['upstream_path']}|{c['local_path']}|{c.get('local_status')}|{content_hash}".encode(
                "utf-8"
            )
        )
    return h.hexdigest()


def truncate_text(text, max_len=1000):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... (truncated)"


def build_markdown(
    args,
    upstream_repo,
    base_tag,
    head_tag,
    stat,
    patch,
    changed_files,
    comparisons,
    commits,
    prs,
    fingerprint,
    local_commit,
    branch,
):
    run_url = f"https://github.com/{args.repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"

    # Escape markdown helpers
    def esc_md(text):
        if not text:
            return ""
        text = str(text).replace("|", "\\|")
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        return text

    def clean_fence(text):
        if not text:
            return ""
        return str(text).replace("```", "'''")

    md = [
        "A new upstream release/change range was detected.",
        "",
        "## Summary",
        "",
        f"- Upstream repo: {esc_md(upstream_repo)}",
    ]
    if base_tag:
        md.append(f"- Release range: {base_tag}...{head_tag}")
        md.append(
            f"- Upstream compare URL: https://github.com/{upstream_repo}/compare/{base_tag}...{head_tag}"
        )
    else:
        md.append(f"- Upstream tag: {head_tag}")
        md.append(f"- Upstream URL: https://github.com/{upstream_repo}/tree/{head_tag}")

    md.extend(
        [
            f"- Local branch: {branch}",
            f"- Local commit: {local_commit}",
            f"- Workflow run: {run_url}",
            f"- Force mode: {args.force}",
            f"- Fingerprint: {fingerprint}",
            "",
        ]
    )

    # Release notes
    rel_res = run_cmd(
        ["gh", "api", f"repos/{upstream_repo}/releases/tags/{head_tag}"], check=False
    )
    if rel_res.returncode == 0:
        try:
            rel = json.loads(rel_res.stdout)
            md.extend(
                [
                    "## Release notes",
                    "",
                    f"**{esc_md(rel.get('name', head_tag))}** ({esc_md(rel.get('published_at', ''))})",
                    f"[Release URL]({rel.get('html_url', '')})",
                    "",
                    "```text",
                    clean_fence(truncate_text(rel.get("body", ""), 2000)),
                    "```",
                    "",
                ]
            )
        except json.JSONDecodeError as e:
            print(f"::warning::Failed to decode release notes JSON: {e}")

    md.extend(["## Upstream commit context", ""])
    for c in commits[:20]:
        short_sha = c["sha"][:7]
        url = f"https://github.com/{upstream_repo}/commit/{c['sha']}"
        md.append(f"- [{short_sha}]({url}) {esc_md(c['msg'])}")
    if len(commits) > 20:
        md.append(f"- ... and {len(commits) - 20} more commits.")
    md.append("")

    if prs:
        md.extend(["## Upstream PR context", ""])
        for pr in prs:
            md.append(
                f"- [#{pr['number']}]({pr['url']}) **{esc_md(pr['title'])}** by @{esc_md(pr['author'])}"
            )
            if pr["body"]:
                # Wrap PR text in code blocks to prevent active @mentions
                md.extend(
                    ["```text", clean_fence(truncate_text(pr["body"], 200)), "```"]
                )
        md.append("")

    md.extend(
        [
            "## Changed upstream files",
            "",
            "| Status | Upstream file | Local equivalent | Upstream latest | Upstream previous | Local file |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    for c in comparisons:
        up_path_quoted = urllib.parse.quote(c["upstream_path"], safe="/")
        u_url_head = (
            f"https://github.com/{upstream_repo}/blob/{head_tag}/{up_path_quoted}"
        )

        u_url_base = ""
        if base_tag:
            if c.get("old_upstream_path"):
                old_path_quoted = urllib.parse.quote(c["old_upstream_path"], safe="/")
                u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{old_path_quoted}"
            else:
                u_url_base = f"https://github.com/{upstream_repo}/blob/{base_tag}/{up_path_quoted}"

        local_path_quoted = urllib.parse.quote(c["local_path"], safe="/")
        local_url = (
            f"https://github.com/{args.repo}/blob/{local_commit}/{local_path_quoted}"
        )

        up_prev = (
            f"[link]({u_url_base})"
            if u_url_base and c["upstream_status"] not in ("added", "copied")
            else "N/A"
        )
        up_latest = (
            f"[link]({u_url_head})" if c["upstream_status"] != "deleted" else "N/A"
        )

        md.append(
            f"| {esc_md(c['upstream_status'])} | `{esc_md(c['upstream_path'])}` | `{esc_md(c['local_path'])}` | {up_latest} | {up_prev} | [link]({local_url}) |"
        )

    md.extend(
        [
            "",
            "## Upstream release-to-release diffstat",
            "",
            "```text",
            stat if stat else "No stat available",
            "```",
            "",
        ]
    )

    diff_text = patch if patch else "No diff available"
    if len(diff_text) > 10000:
        diff_text = (
            diff_text[:10000]
            + "\n... (diff truncated, see workflow artifacts or run reproduce commands)"
        )

    md.extend(
        ["## Upstream release-to-release diff", "", "```diff", diff_text, "```", ""]
    )

    md.extend(["## Equivalent-file comparison against local current codebase", ""])

    for c in comparisons:
        md.append(f"### `{esc_md(c['upstream_path'])}`")
        up_path_quoted = urllib.parse.quote(c["upstream_path"], safe="/")
        u_url = f"https://github.com/{upstream_repo}/blob/{head_tag}/{up_path_quoted}"

        local_path_quoted = urllib.parse.quote(c["local_path"], safe="/")
        l_url = (
            f"https://github.com/{args.repo}/blob/{local_commit}/{local_path_quoted}"
        )

        md.append(f"- Upstream latest: [link]({u_url})")
        md.append(f"- Local equivalent: [link]({l_url})")
        md.append(f"- Status: {esc_md(c['local_status'])}")
        md.append("")
        if c["diff"]:
            f_diff = c["diff"]
            if len(f_diff) > 2000:
                f_diff = f_diff[:2000] + "\n... (truncated)"
            md.extend(["```diff", clean_fence(f_diff), "```", ""])

    md.extend(
        [
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
            f"<!-- upstream-monitor:fingerprint:{fingerprint} -->",
        ]
    )

    return "\n".join(md)


def check_resolved_tags(
    upstream_repo,
    head_tag,
    base_tag,
    default_upstream="droserasprout/io.drsr.hotspotadb",
):
    resolved_file = ".github/upstream-release-resolved-tags.txt"
    if not os.path.exists(resolved_file):
        return False

    try:
        with open(resolved_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        is_default = upstream_repo == default_upstream

        # Exact matching grammar
        # 1. <tag>
        if is_default and line == head_tag:
            return True

        # 2. <owner/repo>@<tag>
        if line == f"{upstream_repo}@{head_tag}":
            return True

        if base_tag:
            # 3. <base>..<head>
            if is_default and line == f"{base_tag}..{head_tag}":
                return True
            # 4. <owner/repo>@<base>..<head>
            if line == f"{upstream_repo}@{base_tag}..{head_tag}":
                return True

    return False


def manage_issue(args, title, body, fingerprint, head_tag, base_tag):
    if args.dry_run:
        print("Dry run: skipping issue creation/update.")
        return "dry_run"

    # Use a deterministic machine key
    identity_key = hashlib.sha256(
        f"{args.upstream_repo}|{head_tag}".encode("utf-8")
    ).hexdigest()
    identity_marker = f"<!-- upstream-monitor:identity:{identity_key} -->"

    # We embed this marker into the body so it's always found
    full_body = body + f"\n\n{identity_marker}"

    # Search for any issue containing the identity marker OR the exact title (for migration)
    search_query = f'"{identity_marker}" in:body'

    # gh issue list returns a JSON array.
    # We fetch all matching issues (should be 1 or 0)
    list_res = run_cmd(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            args.repo,
            "--state",
            "all",
            "--search",
            search_query,
            "--json",
            "number,state,title",
            "--limit",
            "10",
        ],
        check=False,
    )

    existing_issue = None
    if list_res.returncode == 0:
        try:
            issues = json.loads(list_res.stdout)
            if issues:
                # prefer exact marker match
                existing_issue = issues[0]
        except json.JSONDecodeError:
            pass

    # Migration path: if not found by marker, check by exact title
    if not existing_issue:
        title_search_query = f'"{title}" in:title'
        title_res = run_cmd(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                args.repo,
                "--state",
                "all",
                "--search",
                title_search_query,
                "--json",
                "number,state,title",
                "--limit",
                "10",
            ],
            check=False,
        )
        if title_res.returncode == 0:
            try:
                issues = json.loads(title_res.stdout)
                for issue in issues:
                    if issue["title"] == title:
                        existing_issue = issue
                        break
            except json.JSONDecodeError:
                pass

    if existing_issue:
        issue_num = existing_issue["number"]
        issue_state = existing_issue["state"]

        # If it is closed, and we're not forced, and it's marked resolved, keep it closed.
        # But wait, earlier logic already checked `check_resolved_tags()`.
        # The instruction says: "A closed canonical tracking issue is resolved and should stay closed during normal scheduled runs. --force may explicitly reopen/update it."
        if issue_state == "CLOSED" and not args.force:
            print(f"Skipping: issue #{issue_num} is closed (treated as resolved).")
            return "skipped_closed"

        view_res = run_cmd(
            [
                "gh",
                "issue",
                "view",
                str(issue_num),
                "--repo",
                args.repo,
                "--json",
                "body",
            ],
            check=False,
        )
        if view_res.returncode == 0:
            import re

            content = json.loads(view_res.stdout).get("body", "")
            match = re.search(
                r"<!-- upstream-monitor:fingerprint:([a-f0-9]{64}) -->", content
            )
            if match and match.group(1) == fingerprint and not args.force:
                print(
                    f"Skipping: issue #{issue_num} is up to date (fingerprint match)."
                )
                return "skipped_duplicate"

        print(f"Updating existing issue #{issue_num}...")

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".md", mode="w", encoding="utf-8"
        ) as body_file:
            body_file.write(full_body)
            body_path = body_file.name

        try:
            # Try to edit canonical body
            edit_res = run_cmd(
                [
                    "gh",
                    "issue",
                    "edit",
                    str(issue_num),
                    "--repo",
                    args.repo,
                    "--body-file",
                    body_path,
                ],
                check=False,
            )
            if edit_res.returncode == 0:
                print("Issue updated.")

                if issue_state == "CLOSED":
                    reopen_res = run_cmd(
                        ["gh", "issue", "reopen", str(issue_num), "--repo", args.repo],
                        check=False,
                    )
                    if reopen_res.returncode == 0:
                        print(f"Reopened issue #{issue_num}.")
                        return "reopened_updated"
                    else:
                        print(f"::error::Failed to reopen issue #{issue_num}.")
                        return "failed"

                return "updated"
            else:
                print(
                    f"::error::Failed to edit canonical issue body for #{issue_num}. Failing the run."
                )
                return "failed"
        except subprocess.CalledProcessError:
            print("::error::Failed to update issue.")
            return "failed"
        finally:
            os.remove(body_path)
    else:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".md", mode="w", encoding="utf-8"
        ) as body_file:
            body_file.write(full_body)
            body_path = body_file.name

        try:
            print("Creating new issue...")
            create_res = run_cmd(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    args.repo,
                    "--title",
                    title,
                    "--body-file",
                    body_path,
                ],
                check=False,
            )
            if create_res.returncode == 0:
                url = create_res.stdout.strip()
                print(f"Created issue: {url}")
                return "created"
            else:
                print(f"::error::Failed to create issue: {create_res.stderr}")
                return "failed"
        except subprocess.CalledProcessError:
            return "failed"
        finally:
            os.remove(body_path)


def metadata_safe_comparisons(comparisons):
    safe = []
    for c in comparisons:
        entry = dict(c)
        if "diff" in entry:
            entry["diff_excerpt"] = truncate_text(entry["diff"], 500)
            entry["diff_omitted"] = True
            del entry["diff"]
        safe.append(entry)
    return safe


def write_run_summary(args, summary: dict, error_message: str | None = None):
    # Make a copy so we don't mutate the memory struct
    metadata_summary = dict(summary)

    # Strip full diff bodies from comparisons before writing to metadata
    if "comparisons" in metadata_summary:
        metadata_summary["comparisons"] = metadata_safe_comparisons(
            metadata_summary["comparisons"]
        )

    # Atomically write metadata.json
    meta_path = os.path.join(args.out_dir, "metadata.json")
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=args.out_dir
    ) as f:
        json.dump(metadata_summary, f, indent=2)
        tmp_meta = f.name
    os.replace(tmp_meta, meta_path)

    # write upstream-monitor-report.md if not exists (or update with error)
    report_file = os.path.join(args.out_dir, "upstream-monitor-report.md")
    if not os.path.exists(report_file) or error_message:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=args.out_dir
        ) as f:
            if error_message:
                f.write(f"## Upstream Release Monitor Failed\n\n{error_message}\n")
            else:
                f.write(
                    f"## Upstream Release Monitor\n\nSkipped: {summary.get('skip_reason', 'unknown reason')}\n"
                )
            tmp_rep = f.name
        os.replace(tmp_rep, report_file)

    # write warnings.txt if needed
    if summary.get("warnings"):
        with open(
            os.path.join(args.out_dir, "warnings.txt"), "w", encoding="utf-8"
        ) as f:
            f.write("\n".join(summary["warnings"]) + "\n")

    # Write GITHUB_STEP_SUMMARY
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as ss:
            ss.write("## Upstream monitor summary\n\n")
            for key in (
                "result",
                "exit_code",
                "upstream_repo",
                "base_tag",
                "head_tag",
                "changed_files_count",
                "issue_action",
                "skip_reason",
            ):
                ss.write(f"- {key}: {summary.get(key)}\n")

            if summary.get("warnings"):
                ss.write("\n### Warnings\n")
                for item in summary["warnings"][:10]:
                    ss.write(f"- {item}\n")

            if summary.get("errors"):
                ss.write("\n### Errors\n")
                for item in summary["errors"][:10]:
                    ss.write(f"- {item}\n")


def execute_monitor(args) -> dict:
    validate_repo_format(args.repo)
    validate_repo_format(args.upstream_repo)

    summary = {
        "result": "unknown",
        "exit_code": 1,
        "upstream_repo": args.upstream_repo,
        "head_tag": args.head_tag,
        "base_tag": args.base_tag,
        "head_ref": None,
        "base_ref": None,
        "local_commit": None,
        "changed_files_count": 0,
        "issue_action": None,
        "warnings": [],
        "errors": [],
        "skip_reason": None,
    }

    try:
        head_tag, base_tag = resolve_tags(args)
    except Exception as e:
        summary["result"] = "failed"
        summary["errors"].append(f"Failed to resolve tags: {e}")
        return summary

    summary["head_tag"] = head_tag
    summary["base_tag"] = base_tag

    if not head_tag:
        summary["result"] = "skipped_no_releases"
        summary["skip_reason"] = "no_eligible_releases_found"
        summary["exit_code"] = 0
        return summary

    print(f"Resolved head_tag: {head_tag}, base_tag: {base_tag}")

    fetch_res = fetch_upstream(args.upstream_repo, head_tag, base_tag)
    summary["head_ref"] = fetch_res.head_ref
    summary["base_ref"] = fetch_res.base_ref

    if not fetch_res.head_fetched:
        print("::error::Failed to fetch head ref.")
        summary["result"] = "failed"
        summary["errors"].append(
            f"Failed to fetch head tag `{head_tag}` from upstream."
        )
        return summary

    stat, patch, changed_files, comparisons = "", "", [], []

    # Early suppression check before expensive operations (if not dry run)
    if not args.dry_run and not args.force:
        if check_resolved_tags(args.upstream_repo, head_tag, base_tag):
            summary["result"] = "skipped_resolved"
            summary["skip_reason"] = "resolved_in_file"
            summary["exit_code"] = 0
            return summary

    if base_tag and fetch_res.base_fetched:
        stat, patch, changed_files = generate_diffs(
            fetch_res.base_ref, fetch_res.head_ref
        )
    else:
        # Operating against empty tree (4b825dc642cb6eb9a060e54bf8d69288fbee4904)
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        fetch_res.base_ref = empty_tree

        stat, patch, changed_files = generate_diffs(empty_tree, fetch_res.head_ref)

    if not changed_files:
        summary["result"] = "skipped_no_changes"
        summary["skip_reason"] = "empty_upstream_delta"
        summary["exit_code"] = 0
        return summary

    summary["changed_files_count"] = len(changed_files)
    comparisons = compare_local_files(changed_files, fetch_res.head_ref, args.out_dir)
    summary["comparisons"] = comparisons

    # Check for integrated suppression
    if not args.force and not args.dry_run:
        all_integrated = True
        for c in comparisons:
            if c["upstream_status"] == "deleted":
                if c["local_status"] != "missing":
                    all_integrated = False
                    break
            else:
                if c["local_status"] != "identical":
                    all_integrated = False
                    break

        if all_integrated:
            summary["result"] = "skipped_integrated"
            summary["skip_reason"] = "all_files_integrated"
            summary["exit_code"] = 0
            return summary

    with open(
        os.path.join(args.out_dir, "upstream-release.diff"), "w", encoding="utf-8"
    ) as f:
        f.write(patch)

    commits, prs = get_commits_and_prs(
        args.upstream_repo, fetch_res.base_ref, fetch_res.head_ref, args.max_pr_lookups
    )

    branch = os.environ.get("GITHUB_REF_NAME")
    if not branch:
        branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"

    commit_res = run_cmd(["git", "rev-parse", "HEAD"], check=False)
    local_commit = (
        commit_res.stdout.strip() if commit_res.returncode == 0 else "unknown"
    )
    summary["local_commit"] = local_commit

    fingerprint = generate_fingerprint(
        args.upstream_repo, base_tag, head_tag, args.repo, branch, stat, comparisons
    )
    summary["fingerprint"] = fingerprint

    md_report = build_markdown(
        args,
        args.upstream_repo,
        base_tag,
        head_tag,
        stat,
        patch,
        changed_files,
        comparisons,
        commits,
        prs,
        fingerprint,
        local_commit,
        branch,
    )

    report_file = os.path.join(args.out_dir, "upstream-monitor-report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_report)

    title = (
        f"Upstream release monitor: {args.upstream_repo} {base_tag}...{head_tag}"
        if base_tag
        else f"Upstream release monitor: {args.upstream_repo} {head_tag}"
    )
    issue_action = manage_issue(args, title, md_report, fingerprint, head_tag, base_tag)

    summary["issue_action"] = issue_action

    if issue_action in ("failed",):
        summary["result"] = "failed"
        summary["errors"].append("Failed to manage issue.")
    elif issue_action in ("skipped_resolved",):
        summary["result"] = "skipped_resolved"
        summary["exit_code"] = 0
    elif issue_action in ("skipped_duplicate",):
        summary["result"] = "skipped_duplicate"
        summary["exit_code"] = 0
    else:
        summary["result"] = (
            "success_with_warnings" if summary["warnings"] else "success"
        )
        summary["exit_code"] = 0

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstream Release Monitor")
    parser.add_argument("--repo", required=True, help="Local repo (owner/name)")
    parser.add_argument(
        "--upstream-repo", required=True, help="Upstream repo (owner/name)"
    )
    parser.add_argument("--head-tag", help="Optional exact upstream latest tag/ref")
    parser.add_argument("--base-tag", help="Optional upstream base tag/ref")
    parser.add_argument(
        "--include-prerelease", action="store_true", help="Consider prereleases"
    )
    parser.add_argument("--force", action="store_true", help="Bypass suppression")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not create/update issue"
    )
    parser.add_argument(
        "--out-dir", default="artifacts", help="Directory to store output files"
    )
    parser.add_argument(
        "--max-pr-lookups", type=int, default=20, help="Max PRs to lookup"
    )

    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    try:
        summary = execute_monitor(args)
    except Exception as e:
        print(f"::error::Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        summary = {
            "result": "failed",
            "exit_code": 1,
            "upstream_repo": args.upstream_repo,
            "head_tag": args.head_tag,
            "base_tag": args.base_tag,
            "head_ref": None,
            "base_ref": None,
            "local_commit": None,
            "changed_files_count": 0,
            "issue_action": None,
            "warnings": [],
            "errors": [f"Unexpected error: {e}"],
            "skip_reason": None,
        }

    error_msg = "\n".join(summary.get("errors", [])) if summary.get("errors") else None
    write_run_summary(args, summary, error_message=error_msg)

    return summary.get("exit_code", 1)


if __name__ == "__main__":
    raise SystemExit(main())
