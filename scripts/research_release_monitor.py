#!/usr/bin/env python3
"""Research script for release-monitor mode (Mode D).

Fetches upstream releases and changelog, analyzes relevance to target project,
outputs structured findings as markdown.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
import requests


def fetch_github_releases(repo: str, token: str | None = None) -> list[dict]:
    """Fetch recent releases from a GitHub repo."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/releases",
        headers=headers,
        params={"per_page": 5},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_url_content(url: str) -> str:
    """Fetch text content from a URL."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text[:15000]


def fetch_target_readme(repo: str, token: str | None = None) -> str:
    """Fetch the README of the target project."""
    headers = {"Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/readme",
        headers=headers,
    )
    if resp.status_code == 200:
        return resp.text[:10000]
    return "(README not available)"


def load_last_checked(repo: str) -> str | None:
    """Load the last checked release tag for a repo."""
    state_file = Path(__file__).parent.parent / ".state" / f"{repo.replace('/', '_')}.json"
    if state_file.exists():
        data = json.loads(state_file.read_text())
        return data.get("last_release_tag")
    return None


def save_last_checked(repo: str, tag: str) -> None:
    """Save the last checked release tag for a repo."""
    state_dir = Path(__file__).parent.parent / ".state"
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / f"{repo.replace('/', '_')}.json"
    state_file.write_text(json.dumps({"last_release_tag": tag}))


def run_research(
    target_repo: str,
    sources: list[dict],
    github_token: str | None = None,
) -> str:
    """Run release monitor research and return findings markdown."""
    upstream_parts = []
    latest_tag = None

    for source in sources:
        if "repo" in source:
            releases = fetch_github_releases(source["repo"], github_token)
            last_checked = load_last_checked(source["repo"])

            new_releases = []
            for r in releases:
                if last_checked and r.get("tag_name") == last_checked:
                    break
                new_releases.append(r)

            if not new_releases:
                upstream_parts.append(f"### {source['repo']}\nNo new releases since last check.")
                continue

            latest_tag = new_releases[0].get("tag_name")
            for r in new_releases:
                upstream_parts.append(
                    f"### {source['repo']} — {r.get('tag_name', 'unknown')}\n"
                    f"Published: {r.get('published_at', 'unknown')}\n\n"
                    f"{r.get('body', '(no release notes)')[:5000]}"
                )

        elif "url" in source:
            content = fetch_url_content(source["url"])
            upstream_parts.append(f"### Content from {source['url']}\n\n{content}")

    upstream_content = "\n\n---\n\n".join(upstream_parts)
    if not upstream_content.strip():
        return "No upstream changes detected."

    target_readme = fetch_target_readme(target_repo, github_token)

    prompt_path = Path(__file__).parent.parent / "prompts" / "release-monitor.md"
    prompt_template = prompt_path.read_text()
    prompt = prompt_template.replace("{upstream_content}", upstream_content)
    prompt = prompt.replace("{target_readme}", target_readme)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    findings = response.content[0].text

    if latest_tag:
        for source in sources:
            if "repo" in source:
                save_last_checked(source["repo"], latest_tag)

    return findings


def main():
    target_repo = os.environ["TARGET_REPO"]
    sources = json.loads(os.environ["SOURCES"])
    github_token = os.environ.get("GITHUB_TOKEN")

    findings = run_research(target_repo, sources, github_token)

    output_path = Path(os.environ.get("RESEARCH_OUTPUT", "/tmp/research_output.md"))
    output_path.write_text(findings)
    print(findings)


if __name__ == "__main__":
    main()
