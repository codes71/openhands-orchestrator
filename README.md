# OpenHands Orchestrator

Proactive AI research agent that monitors your projects nightly, reports findings, and implements approved changes as PRs.

## How It Works

1. **Nightly research** (18:00 IST) — analyzes each configured project
2. **Telegram notification** — sends findings summary to your Telegram
3. **You review & reply** — comment on the GitHub Issue with instructions
4. **Auto-implementation** — OpenHands implements your instructions and creates a PR

## Research Modes

| Mode | What it does |
|------|-------------|
| `release-monitor` | Watches upstream repos/docs for new features, breaking changes, deprecations |
| `codebase-analysis` | Analyzes deps, test coverage, security, performance, code quality |

## Setup

### 1. Add secrets to this repo

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `PAT_TOKEN` | GitHub PAT with `repo`, `issues`, `workflow` scopes |

### 2. Configure projects

Edit `projects.yml` to add your repos:

```yaml
projects:
  - repo: owner/repo-name
    mode: release-monitor  # or codebase-analysis
    sources:               # for release-monitor mode only
      - repo: upstream/repo
      - url: https://example.com/changelog
    priority: [deps, tests, security, performance, refactoring]
```

### 3. Set up target repos

Copy `templates/openhands-resolver.yml` to `.github/workflows/openhands-resolver.yml` in each target repo. Add the same `LLM_API_KEY` and `PAT_TOKEN` secrets to each target repo.

### 4. Create issue labels

In this orchestrator repo, create labels for each project name (e.g., `claude-panel`) plus `research`, `implemented`, `release-monitor`, `codebase-analysis`.

## Cost

LLM API costs only. Research runs use Claude Sonnet (~$0.50-2.00 per run). Implementation uses OpenHands with Claude Sonnet (~$1-5 per PR).
