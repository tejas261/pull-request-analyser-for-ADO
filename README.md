## AI PR Validator — Azure DevOps & GitHub

AI-powered Pull Request reviewer that supports both **Azure DevOps** and **GitHub**. Uses specialised review agents (security, best practices, test coverage, dependency analysis) powered by GPT-4 via LangChain/LangGraph, with optional Slack notifications.

---

### Features

- **Multi-platform** — Azure DevOps and GitHub PR reviews from the same codebase
- **Specialised review agents** — Security, best practices (frontend/backend-aware), test coverage, dependency analysis, PR description validation
- **Severity-graded findings** — Every comment is rated critical/major/minor/nit with confidence scores
- **Smart scaling** — Comment limits scale with PR size; critical findings are always kept
- **Full file coverage** — Reviews new files, edits, renames, and deletions (not just edits)
- **Token-aware chunking** — Large PRs are automatically split into reviewable chunks
- **Test-to-code mapping** — Flags source file changes missing corresponding test updates
- **Inline comments** — Posts findings directly on the PR as inline comments
- **Slack integration** — Sends review summaries with reviewer mentions to Slack
- **Retry with backoff** — Transient HTTP errors are retried automatically

---

### Architecture

```
                    ┌──────────────┐
                    │  PR Platform │
                    │ (ADO/GitHub) │
                    └──────┬───────┘
                           │
              ┌────────────▼─────────────┐
              │      Provider Layer      │
              │  ADOProvider / GitHub-   │
              │  Provider (REST API)     │
              └────────────┬─────────────┘
                           │
              ┌────────────▼─────────────┐
              │     Diff Checker Agent   │
              │  Fetch metadata + files  │
              └────────────┬─────────────┘
                           │
              ┌────────────▼─────────────┐
              │    File Router + Chunker │
              │  Classify & split files  │
              └────────────┬─────────────┘
                           │
         ┌─────────┬───────┼───────┬──────────┐
         ▼         ▼       ▼       ▼          ▼
    ┌─────────┐┌────────┐┌─────┐┌──────┐┌─────────┐
    │Security ││Best    ││Test ││Dep   ││PR Desc  │
    │Reviewer ││Practice││Cov  ││Check ││Validate │
    └────┬────┘└───┬────┘└──┬──┘└──┬───┘└────┬────┘
         └─────────┴────┬───┴─────┴──────────┘
                        ▼
              ┌─────────────────────┐
              │    Synthesizer      │
              │ Dedupe + prioritise │
              └────────┬────────────┘
                       │
              ┌────────▼────────┐
              │   Commenter     │──── Post to PR
              │   Messenger     │──── Post to Slack
              └─────────────────┘
```

---

### Prerequisites

- Python 3.9+
- Node.js (for MCP server tools, if using Slack)
- API keys: OpenAI + platform token (ADO PAT or GitHub token)

### Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your credentials
```

### Configuration

Set `PLATFORM=ado` or `PLATFORM=github` in `.env`, then fill in the corresponding credentials. See `.env.example` for all options.

### Run

```bash
python orchestrator.py
```

### Run Tests

```bash
python -m pytest tests/ -v
```

---

### Project Structure

```
├── orchestrator.py              # Main workflow: diff → review → comment → slack
├── config.py                    # Env vars, platform selection, MCP config
├── retry.py                     # Exponential backoff retry decorator
├── utils.py                     # Diff formatting, comment formatting helpers
├── providers/
│   ├── base.py                  # PRProvider abstract interface
│   ├── ado.py                   # Azure DevOps REST API provider
│   ├── github.py                # GitHub REST API provider
│   └── factory.py               # Provider factory (PLATFORM → provider)
├── agents/
│   ├── diffChecker.py           # Fetch PR diffs and file contents
│   ├── reviewer.py              # Fan-out to specialised reviewers
│   ├── commenter.py             # Post review comments to PR
│   ├── messenger.py             # Send Slack notification
│   ├── types.py                 # ReviewComment, ReviewResult models
│   ├── router.py                # File-type classification & test pairing
│   ├── chunker.py               # Token-aware PR splitting
│   └── reviewers/
│       ├── security.py          # Security vulnerability detection
│       ├── best_practices.py    # Style, performance, patterns (frontend/backend-aware)
│       ├── test_coverage.py     # Test gaps + test-to-code mapping
│       ├── dependency.py        # package.json/requirements.txt analysis
│       ├── pr_description.py    # PR description quality check
│       └── synthesizer.py       # Merge, dedupe, prioritise findings
└── tests/
    ├── test_utils.py
    ├── test_router.py
    ├── test_chunker.py
    ├── test_synthesizer.py
    └── test_providers.py
```

---

### CI Integration

Add to your Azure DevOps pipeline or GitHub Actions:

```yaml
# GitHub Actions example
- name: AI PR Review
  env:
    PLATFORM: github
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GITHUB_OWNER: ${{ github.repository_owner }}
    GITHUB_REPO: ${{ github.event.repository.name }}
    PR_ID: ${{ github.event.pull_request.number }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    pip install -r requirements.txt
    python orchestrator.py
```
