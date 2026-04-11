#!/usr/bin/env python3
"""Research script for codebase-analysis mode (Mode C).

Clones the target repo, runs analysis tools, synthesizes findings via Claude.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import anthropic
import posthog
from posthog.ai.anthropic import Anthropic


def clone_repo(repo: str, token: str | None = None) -> Path:
    """Clone repo to a temp directory and return the path."""
    tmp = Path(tempfile.mkdtemp())
    url = f"https://github.com/{repo}.git"
    if token:
        url = f"https://x-access-token:{token}@github.com/{repo}.git"
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(tmp / "repo")],
        check=True,
        capture_output=True,
    )
    return tmp / "repo"


def run_analysis(repo_path: Path, priority: list[str]) -> dict[str, str]:
    """Run analysis tools and return results keyed by category."""
    results = {}

    has_package_json = (repo_path / "package.json").exists()
    has_requirements = (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists()

    if "deps" in priority:
        dep_output = []
        if has_package_json:
            r = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=repo_path, capture_output=True, text=True,
            )
            dep_output.append(f"npm audit:\n{r.stdout[:3000]}")
            r = subprocess.run(
                ["npm", "outdated", "--json"],
                cwd=repo_path, capture_output=True, text=True,
            )
            dep_output.append(f"npm outdated:\n{r.stdout[:3000]}")
        if has_requirements:
            r = subprocess.run(
                ["pip", "audit", "--format", "json"],
                cwd=repo_path, capture_output=True, text=True,
            )
            dep_output.append(f"pip audit:\n{r.stdout[:3000]}")
        results["deps"] = "\n\n".join(dep_output) if dep_output else "No dependency tools available"

    if "tests" in priority:
        test_output = []
        if has_package_json:
            r = subprocess.run(
                ["npx", "vitest", "run", "--reporter=verbose"],
                cwd=repo_path, capture_output=True, text=True, timeout=120,
            )
            test_output.append(f"vitest:\n{r.stdout[-3000:]}")
        if has_requirements:
            r = subprocess.run(
                ["python", "-m", "pytest", "--tb=short", "-q"],
                cwd=repo_path, capture_output=True, text=True, timeout=120,
            )
            test_output.append(f"pytest:\n{r.stdout[-3000:]}")
        results["tests"] = "\n\n".join(test_output) if test_output else "No test results"

    if "security" in priority:
        r = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.js",
             "-E", r"(eval\(|exec\(|subprocess\.call|innerHTML|dangerouslySetInnerHTML|password.*=|secret.*=|api.?key.*=)",
             str(repo_path)],
            capture_output=True, text=True,
        )
        results["security"] = f"Security pattern scan:\n{r.stdout[:3000]}" if r.stdout else "No obvious security patterns found"

    if "performance" in priority:
        perf_output = []
        if has_package_json and (repo_path / "dist").exists():
            r = subprocess.run(
                ["du", "-sh", str(repo_path / "dist")],
                capture_output=True, text=True,
            )
            perf_output.append(f"Bundle size: {r.stdout.strip()}")
        results["performance"] = "\n".join(perf_output) if perf_output else "No performance data collected"

    if "refactoring" in priority:
        r = subprocess.run(
            ["find", str(repo_path), "-name", "*.py", "-o", "-name", "*.ts", "-o", "-name", "*.js",
             "-not", "-path", "*/node_modules/*", "-not", "-path", "*/.git/*"],
            capture_output=True, text=True,
        )
        files = [f for f in r.stdout.strip().split("\n") if f]
        large_files = []
        for f in files:
            wc = subprocess.run(["wc", "-l", f], capture_output=True, text=True)
            lines = int(wc.stdout.strip().split()[0])
            if lines > 300:
                rel = str(Path(f).relative_to(repo_path))
                large_files.append(f"{rel}: {lines} lines")
        results["refactoring"] = "Large files (>300 lines):\n" + "\n".join(large_files) if large_files else "No large files detected"

    return results


def synthesize_findings(analysis_data: dict[str, str], repo: str) -> str:
    """Send analysis data to Claude for synthesis."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "codebase-analysis.md"
    prompt_template = prompt_path.read_text()

    formatted_data = "\n\n".join(
        f"## {category.upper()}\n{data}" for category, data in analysis_data.items()
    )
    prompt = prompt_template.replace("{analysis_data}", formatted_data)

    # Init PostHog for LLM monitoring
    posthog.api_key = os.environ.get("POSTHOG_API_KEY", "")
    posthog.host = "https://us.i.posthog.com"

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Retry with backoff for rate limits
    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                posthog_distinct_id=f"orchestrator:{repo}",
                posthog_properties={"mode": "codebase-analysis", "repo": repo},
            )
            break
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/5)")
            time.sleep(wait)
    else:
        return "Research failed: rate limit exceeded after 5 attempts. Will retry next run."

    return response.content[0].text


def main():
    target_repo = os.environ["TARGET_REPO"]
    priority = json.loads(os.environ.get("PRIORITY", '["deps","tests","security","performance","refactoring"]'))
    github_token = os.environ.get("GITHUB_TOKEN")

    repo_path = clone_repo(target_repo, github_token)
    analysis = run_analysis(repo_path, priority)
    findings = synthesize_findings(analysis, target_repo)

    output_path = Path(os.environ.get("RESEARCH_OUTPUT", "/tmp/research_output.md"))
    output_path.write_text(findings)
    print(findings)

    posthog.flush()


if __name__ == "__main__":
    main()
