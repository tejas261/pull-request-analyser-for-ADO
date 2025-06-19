## AI PR Validator for Frontend repositories in Azure DevOps

**AI PR Validator** is an team of AI agents designed to streamline Pull Request (PR) reviews in Azure DevOps for Frontend repositories. It leverages [LangChain](https://python.langchain.com/), [OpenAI GPT-4](https://platform.openai.com/), MCP tools offered by [Tiberriver256](https://github.com/Tiberriver256/mcp-server-azure-devops/tree/main) and custom orchestration agents to fetch PR diffs, analyze code changes, and post insightful review comments back to Azure DevOps.

---

### 🔍 Features

- **Automatic Diff Fetching**

  - Retrieves all changed files in a PR, including before-and-after snapshots.

- **LLM-Powered Reviews**

  - Generates best-practice, security, and style feedback using GPT-4.

- **Azure DevOps and Slack Integration**

  - Posts inline review comments directly to the PR via the MCP Server endpoints.

  - Posts the summary, Best Practices that must be followed, Security issues and Suggestions (if any) to the configured slack channel.

- **Modular Architecture**

  - Agents for diff fetching, review generation, and comment posting.
  - Easily extendable by adding new agents or enhancing existing ones.

---

## 🏁 Getting Started

Follow these steps to set up and run the AI PR Validator on your machine.

### 1. Prerequisites

- **Python**: 3.8 or higher
- **Azure DevOps PAT**: Personal Access Token with `Code (Read & Write)` scope
- **OpenAI API Key**: For GPT-4 access
- **Node.js**: Required for MCP server tool (if using)

### 2. Clone the Repository

**Via HTTP**

```bash
https://GoFynd@dev.azure.com/GoFynd/Rattle/_git/ai-pr-validator
cd ai-pr-validator
```

**Via SSH**

```bash
git@ssh.dev.azure.com:v3/GoFynd/Rattle/ai-pr-validator
cd ai-pr-validator
```

### 3. Create & Activate Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate  # Windows
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configuration

Duplicate the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` and set the following variables:

```ini
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/YourOrg
AZURE_DEVOPS_DEFAULT_PROJECT=YourProject
AZURE_DEVOPS_DEFAULT_REPO=YourRepo
AZURE_DEVOPS_PAT=<YOUR_PAT_TOKEN>
AZURE_DEVOPS_AUTH_METHOD=pat
OPENAI_API_KEY=<YOUR_OPENAI_KEY>
PR_ID=<PR_ID_TO_REVIEW>
GPT_MODEL=<GPT model of your choice>
```

### 6. Running the Validator

```bash
python orchestrator.py
```

This will:

1. Fetch the specified PR diffs.
2. Generate review comments via GPT-4.
3. Post comments back to the Azure DevOps PR.

---

## 🏗️ Project Structure

```text
├── agents/
│   ├── diffChecker.py        # Fetches PR diffs and file contents
│   ├── reviewer.py          # Generates review comments using LLM
│   └── commenter.py         # Posts review comments to Azure DevOps
├── config.py                # Loads environment variables and configs
├── orchestrator.py          # Main workflow: diff → review → comment
├── utils.py                 # Helper functions (e.g., diff formatting)
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

---

## 🔧 Customization & Extensibility

- **Add New Agents**: Create a new module in `agents/` following the existing pattern.
- **Extend Reviewer**: Modify `agents/reviewer.py` to add custom policies, security checks, or style guidelines.
- **Utility Functions**: Reuse or extend functions in `utils.py` for diff parsing, formatting, or other tasks.

---

## 🚀 Deployment & CI Integration

1. **CI Pipeline**: Integrate `python orchestrator.py` into your Azure DevOps YAML pipeline to automate PR reviews on each pull request.
2. **Docker Support**: Add a `Dockerfile` to containerize the validator for consistent environments.

---

## ❓ Troubleshooting

- **Authentication Errors**: Verify your `AZURE_DEVOPS_PAT` and `OPENAI_API_KEY` in `.env`.
- **Rate Limits**: Monitor OpenAI rate limits; consider batching or reducing prompt sizes.
- **Network Issues**: Ensure your environment can reach Azure DevOps and OpenAI endpoints.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request for review.

Please follow the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct.

---

## 📖 Further Reading

- [LangChain Documentation](https://python.langchain.com/)
- [Azure DevOps REST API Reference](https://docs.microsoft.com/rest/api/azure/devops/)
- [OpenAI API Reference](https://platform.openai.com/docs)

---
