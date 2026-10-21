"""Refresh the live parts of the profile: the "Recently shipped" list and the header.

Sources, all public:
  - merged pull requests authored by the user, anywhere on GitHub
  - recent commits by the user on their own non-fork, non-archived repos

Only PR titles and the first line of commit messages are shown. Branch names
never are, and throwaway messages (merges, "wip", one-word fixes) are dropped.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_header  # noqa: E402

USER = os.environ.get("PROFILE_USER", "rehaanajani")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = Path(__file__).resolve().parent.parent / "README.md"
IST = timezone(timedelta(hours=5, minutes=30))
LIMIT = 5
PER_REPO = 2

SKIP = re.compile(r"^(merge\b|wip\b|fixup!|squash!|update readme\b|initial commit\b|(docs|chore|style|ci|build)(\(.*?\))?:|\.|test$)", re.I)


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-profile"},
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def merged_prs():
    q = urllib.parse.quote(f"author:{USER} is:pr is:merged is:public")
    data = api(f"/search/issues?q={q}&sort=updated&order=desc&per_page=30")
    for it in data.get("items", []):
        merged = (it.get("pull_request") or {}).get("merged_at")
        if not merged:
            continue
        repo = it["repository_url"].split("/repos/", 1)[1]
        yield {"repo": repo, "title": it["title"], "url": it["html_url"], "at": parse_time(merged)}


def own_commits():
    repos = api(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=20")
    for r in repos:
        if r.get("fork") or r.get("archived") or r.get("private") or r["name"] == USER:
            continue
        try:
            commits = api(f"/repos/{r['full_name']}/commits?author={USER}&per_page=5")
        except Exception:
            continue
        for c in commits:
            msg = c["commit"]["message"].split("\n", 1)[0].strip()
            yield {"repo": r["full_name"], "title": msg, "url": c["html_url"], "at": parse_time(c["commit"]["author"]["date"])}


def clean(items):
    seen, out, per_repo = set(), [], {}
    for it in sorted(items, key=lambda x: x["at"], reverse=True):
        if per_repo.get(it["repo"], 0) >= PER_REPO:
            continue
        title = re.sub(r"\s*\(#\d+[^)]*\)\s*$", "", it["title"]).strip()
        title = re.sub(r"^(feat|fix|refactor|perf)(\(.*?\))?!?:\s*", "", title, flags=re.I)
        title = title[:1].upper() + title[1:]
        if len(title) < 12 or SKIP.search(title):
            continue
        key = (it["repo"], title.lower())
        if key in seen:
            continue
        seen.add(key)
        per_repo[it["repo"]] = per_repo.get(it["repo"], 0) + 1
        if len(title) > 90:
            title = title[:87].rsplit(" ", 1)[0] + "…"
        out.append({**it, "title": title})
        if len(out) == LIMIT:
            break
    return out


def ago(dt, now):
    days = (now - dt).days
    if days <= 0:
        hours = max(1, int((now - dt).total_seconds() // 3600))
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    return f"{months} month{'s' if months != 1 else ''} ago"


def replace(text, tag, body):
    pattern = re.compile(rf"(<!-- {tag}:start -->)(.*?)(<!-- {tag}:end -->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main():
    now = datetime.now(timezone.utc)
    items = []
    for source in (merged_prs, own_commits):
        try:
            items.extend(source())
        except Exception as e:  # keep the last good README if an API call fails
            print(f"warning: {source.__name__}: {e}", file=sys.stderr)
    shipped = clean(items)
    if not shipped:
        print("nothing fetched, leaving README as is")
        return

    lines = []
    for it in shipped:
        name = it["repo"].split("/", 1)[1]
        lines.append(f"- [**{name}**](https://github.com/{it['repo']}) · [{it['title']}]({it['url']}) <sub>{ago(it['at'], now)}</sub>")
    stamp = now.astimezone(IST).strftime("%d %b %Y, %H:%M IST")

    text = README.read_text()
    text = replace(text, "shipped", "\n".join(lines))
    text = replace(text, "updated", f"<sub>Pulled from merged pull requests and commits on public repos. Refreshed every six hours · last run {stamp}</sub>")
    README.write_text(text)

    latest = shipped[0]
    repo_name = latest["repo"].split("/", 1)[1].upper()
    gen_header.write(f"LAST SHIPPED  {repo_name[:22]}  ·  {ago(latest['at'], now).upper()}")
    print(f"updated {len(shipped)} items; latest {latest['repo']}")


if __name__ == "__main__":
    main()
