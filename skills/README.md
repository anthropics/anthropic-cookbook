# Claude Skills Cookbook 🚀

A comprehensive guide to using Claude's Skills feature for document generation, data analysis, and business automation. This cookbook demonstrates how to leverage Claude's built-in skills for Excel, PowerPoint, and PDF creation, as well as how to build custom skills for specialized workflows.

> **🎯 See Skills in Action:** Check out **[Claude Creates Files](https://www.anthropic.com/news/create-files)** to see how these Skills power Claude's ability to create and edit documents directly in Claude.ai and the desktop app!

## What are Skills?

Skills are organized packages of instructions, executable code, and resources that give Claude specialized capabilities for specific tasks. Think of them as "expertise packages" that Claude can discover and load dynamically to:

- Create professional documents (Excel, PowerPoint, PDF, Word)
- Perform complex data analysis and visualization
- Apply company-specific workflows and branding
- Automate business processes with domain expertise

📖 Read our engineering blog post on [Equipping agents for the real world with Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

## Key Features

- ✨ **Progressive Disclosure Architecture** - Skills load only when needed, optimizing token usage
- 📊 **Financial Focus** - Real-world examples for finance and business analytics
- 🔧 **Custom Skills Development** - Learn to build and deploy your own skills
- 🎯 **Production-Ready Examples** - Code you can adapt for immediate use

## Cookbook Structure

### 📚 [Notebook 1: Introduction to Skills](notebooks/01_skills_introduction.ipynb)

Learn the fundamentals of Claude's Skills feature with quick-start examples.

- Understanding Skills architecture
- Setting up the API with beta headers
- Creating your first Excel spreadsheet
- Generating PowerPoint presentations
- Exporting to PDF format

### 💼 [Notebook 2: Financial Applications](notebooks/02_skills_financial_applications.ipynb)

Explore powerful business use cases with real financial data.

- Building financial dashboards with charts and pivot tables
- Portfolio analysis and investment reporting
- Cross-format workflows: CSV → Excel → PowerPoint → PDF
- Token optimization strategies

### 🔧 [Notebook 3: Custom Skills Development](notebooks/03_skills_custom_development.ipynb)

Master the art of creating your own specialized skills.

- Building a financial ratio calculator
- Creating company brand guidelines skill
- Advanced: Financial modeling suite
- [Best practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices) and security considerations

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Jupyter Notebook or JupyterLab

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/anthropics/claude-cookbooks.git
cd claude-cookbooks/skills
```

2. **Create virtual environment** (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure API key**

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

5. **Launch Jupyter**

```bash
jupyter notebook
```

6. **Start with Notebook 1**
   Open `notebooks/01_skills_introduction.ipynb` and follow along!

## Sample Data

The cookbook includes realistic financial datasets in `sample_data/`:

- 📊 **financial_statements.csv** - Quarterly P&L, balance sheet, and cash flow data
- 💰 **portfolio_holdings.json** - Investment portfolio with performance metrics
- 📋 **budget_template.csv** - Department budget with variance analysis
- 📈 **quarterly_metrics.json** - KPIs and operational metrics

## Project Structure

```
skills/
├── notebooks/                    # Jupyter notebooks
│   ├── 01_skills_introduction.ipynb
│   ├── 02_skills_financial_applications.ipynb
│   └── 03_skills_custom_development.ipynb
├── sample_data/                  # Financial datasets
│   ├── financial_statements.csv
│   ├── portfolio_holdings.json
│   ├── budget_template.csv
│   └── quarterly_metrics.json
├── custom_skills/                # Your custom skills
│   ├── financial_analyzer/
│   ├── brand_guidelines/
│   └── report_generator/
├── outputs/                      # Generated files
├── docs/                         # Documentation
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
└── README.md                    # This file
```

## API Configuration

Skills require specific beta headers. The notebooks handle this automatically, but here's what's happening behind the scenes:

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="your-api-key",
    default_headers={
        "anthropic-beta": "code-execution-2025-08-25,files-api-2025-04-14,skills-2025-10-02"
    }
)
```

**Required Beta Headers:**

- `code-execution-2025-08-25` - Enables code execution for Skills
- `files-api-2025-04-14` - Required for downloading generated files
- `skills-2025-10-02` - Enables Skills feature

## Working with Generated Files

When Skills create documents (Excel, PowerPoint, PDF, etc.), they return `file_id` attributes in the response. You must use the **Files API** to download these files.

### How It Works

1. **Skills create files** during code execution
2. **Response includes file_ids** for each created file
3. **Use Files API** to download the actual file content
4. **Save locally** or process as needed

### Example: Creating and Downloading an Excel File

```python
from anthropic import Anthropic

client = Anthropic(api_key="your-api-key")

# Step 1: Use a skill to create a file
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    container={
        "skills": [
            {"type": "anthropic", "skill_id": "xlsx", "version": "latest"}
        ]
    },
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
    messages=[{
        "role": "user",
        "content": "Create an Excel file with a simple budget spreadsheet"
    }]
)

# Step 2: Extract file_id from the response
file_id = None
for block in response.content:
    if block.type == "tool_result" and hasattr(block, 'output'):
        # Look for file_id in the tool output
        if 'file_id' in str(block.output):
            file_id = extract_file_id(block.output)  # Parse the file_id
            break

# Step 3: Download the file using Files API
if file_id:
    file_content = client.beta.files.download(file_id=file_id)

    # Step 4: Save to disk
    with open("outputs/budget.xlsx", "wb") as f:
        f.write(file_content.read())

    print(f"✅ File downloaded: budget.xlsx")
```

### Files API Methods

```python
# Download file content (binary)
content = client.beta.files.download(file_id="file_abc123...")
with open("output.xlsx", "wb") as f:
    f.write(content.read())  # Use .read() not .content

# Get file metadata
info = client.beta.files.retrieve_metadata(file_id="file_abc123...")
print(f"Filename: {info.filename}, Size: {info.size_bytes} bytes")  # Use size_bytes not size

# List all files
files = client.beta.files.list()
for file in files.data:
    print(f"{file.filename} - {file.created_at}")

# Delete a file
client.beta.files.delete(file_id="file_abc123...")
```

**Important Notes:**

- Files are stored temporarily on Anthropic's servers
- Downloaded files should be saved to your local `outputs/` directory
- The Files API uses the same API key as the Messages API
- All notebooks include helper functions for file download
- **Files are overwritten by default** - rerunning cells will replace existing files (you'll see `[overwritten]` in the output)

See the [Files API documentation](https://docs.claude.com/en/api/files-content) for complete details.

## Built-in Skills Reference

Claude comes with these pre-built skills:

| Skill      | ID     | Description                                                                 |
| ---------- | ------ | --------------------------------------------------------------------------- |
| Excel      | `xlsx` | Create and manipulate Excel workbooks with formulas, charts, and formatting |
| PowerPoint | `pptx` | Generate professional presentations with slides, charts, and transitions    |
| PDF        | `pdf`  | Create formatted PDF documents with text, tables, and images                |
| Word       | `docx` | Generate Word documents with rich formatting and structure                  |

## Creating Custom Skills

Custom skills follow this structure:

```
my_skill/
├── SKILL.md           # Required: Instructions for Claude
├── scripts/           # Optional: Python/JS code
│   └── processor.py
└── resources/         # Optional: Templates, data
    └── template.xlsx
```

Learn more in [Notebook 3](notebooks/03_skills_custom_development.ipynb).

## Common Use Cases

### Financial Reporting

- Automated quarterly reports
- Budget variance analysis
- Investment performance dashboards

### Data Analysis

- Excel-based analytics with complex formulas
- Pivot table generation
- Statistical analysis and visualization

### Document Automation

- Branded presentation generation
- Report compilation from multiple sources
- Cross-format document conversion

## Performance Tips

1. **Use Progressive Disclosure**: Skills load in stages to minimize token usage
2. **Batch Operations**: Process multiple files in a single conversation
3. **Skill Composition**: Combine multiple skills for complex workflows
4. **Cache Reuse**: Use container IDs to reuse loaded skills

## Troubleshooting

### Common Issues

**API Key Not Found**

```
ValueError: ANTHROPIC_API_KEY not found
```

→ Make sure you've copied `.env.example` to `.env` and added your key

**Skills Beta Header Missing**

```
Error: Skills feature requires beta header
```

→ Ensure you're using the correct beta headers as shown in the notebooks

**Token Limit Exceeded**

```
Error: Request exceeds token limit
```

→ Break large operations into smaller chunks or use progressive disclosure

## Resources

### Documentation

- 📖 [Claude API Documentation](https://docs.anthropic.com/en/api/messages)
- 🔧 [Skills Documentation](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)

### Support Articles

- 📚 [Teach Claude your way of working using Skills](https://support.claude.com/en/articles/12580051-teach-claude-your-way-of-working-using-skills) - User guide for working with Skills
- 🛠️ [How to create a skill with Claude through conversation](https://support.claude.com/en/articles/12599426-how-to-create-a-skill-with-claude-through-conversation) - Interactive skill creation guide

### Community & Support

- 💬 [Claude Support](https://support.claude.com)
- 🐙 [GitHub Issues](https://github.com/anthropics/claude-cookbooks/issues)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

This cookbook is provided under the MIT License. See [LICENSE](../LICENSE) for details.

## Acknowledgments

Special thanks to the Anthropic team for developing the Skills feature and providing the SDK.

---

**Questions?** Check [GitHub Issues](https://github.com/anthropics/claude-cookbooks/issues) or open an issue.

**Ready to start?** Open [Notebook 1](notebooks/01_skills_introduction.ipynb) and let's build something amazing! 🎉
