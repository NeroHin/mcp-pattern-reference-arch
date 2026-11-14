# MCP Pattern Reference Architecture

[English](README.md) | [繁體中文](README.zh-TW.md)

Building an MCP server from existing APIs or data services? This project helps you decide which tools to expose, how much information to return, and which work belongs on the backend.

It includes a skill for making those decisions and runnable examples that show how different designs behave.

## What's included

| Part | What it does | Start here |
| --- | --- | --- |
| **mcp-architecture skill** | Helps an agent design or review an MCP server, explain its choices, and define inputs, outputs, permissions, and failure handling | [SKILL.md](skills/mcp-architecture/SKILL.md) |
| **Six runnable examples** | Run the same task through five designs and a Flat baseline, using the same synthetic data and backend | [Example code](src/mcp_pattern_demo) |
| **Validation cases** | Check whether the skill can handle new design and review requests outside the original example | [Validation report](evals/results/v0.1.0/report.md) |

## Five patterns, in plain language

| Pattern | What it means | When it helps |
| --- | --- | --- |
| **Scoped Capabilities** | Give the agent the tools it needs for the current job | The task, role, project, or workspace is already known |
| **Progressive Disclosure** | Find the relevant data first, then fetch the details you need | Documents or datasets are large, but most tasks only need part of them |
| **Discover + Execute** | Find an operation, read its parameters, then call it through a fixed entry point | There are many API operations, or the catalog changes often |
| **Semantic Contract** | Use business definitions maintained by the backend | A metric needs one agreed formula, unit, and time range |
| **Domain Delegation** | Hand a complete task to a domain service or workflow | Several agents need to reuse the same domain process |

Start with a few clear, direct tools. Add a pattern when it solves a real problem. Patterns can be combined.

These names are this project's way of grouping design choices, rather than an official MCP classification. The [selection guide](skills/mcp-architecture/references/selection-guide.md) explains the choices and tradeoffs.

## Use the skill

You can use the skill without running the examples or setting up API keys.

In a checkout of this repository, ask your agent:

```text
Read skills/mcp-architecture/SKILL.md and use it to design an MCP server
for my research documents. Documents have stable section IDs and access rules.
The client supports tools only.

Explain the pattern choices, define the tool inputs and outputs,
and give me a validation plan.
```

For an environment that supports Agent Skills, copy the entire `skills/mcp-architecture/` folder to that environment's skill directory. Keep its references, assets, metadata, and license together. Follow the host's installation instructions; automatic discovery varies by host.

After installation, you can invoke `$mcp-architecture` where supported.

Version 0.1.0 focuses on **design and review**. It helps define the architecture and implementation plan; it does not provide an automatic code generator for every SDK. The core skill is self-contained and needs no Notion, Langfuse, model API, or Python packages.

Useful references:

- [Selection guide](skills/mcp-architecture/references/selection-guide.md): choose and combine patterns.
- [Implementation map](skills/mcp-architecture/references/implementation-map.md): find the code, tests, and limits behind each example.
- [Interface contract guide](skills/mcp-architecture/assets/interface-contract-template.md): define parameters, results, permissions, errors, and retries.

## Run the examples

### 1. Install and inspect the tools

Requires Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/NeroHin/mcp-pattern-reference-arch.git
cd mcp-pattern-reference-arch
uv sync --locked
uv run mcp-pattern-demo --list-tools
```

The last command starts the local MCP servers and lists their tools. It does not call a model or require API keys.

### 2. Configure a model and Langfuse

Create a `.env` file in the repository root, or set these environment variables:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
```

[.env.example](.env.example) contains the same empty fields. Set `OPENAI_MODEL` to the model you want to use; the runner does not choose a replacement.

### 3. Run a task

```sh
# Run all six examples once
uv run mcp-pattern-demo --pattern all

# Or run one example
uv run mcp-pattern-demo --pattern discover
```

These commands call the configured model and send the synthetic task, tool inputs and outputs, and model replies to your configured Langfuse project. The current runner requires both model and Langfuse settings.

Each example starts a separate MCP process and a fresh agent conversation. The implementation uses the MCP Python SDK's FastMCP over stdio, OpenAI Agents SDK, and Langfuse. The locked SDK range is `mcp>=1.26,<2`.

## What the examples show

All six examples answer the same question: calculate September 2026 net revenue for the north region, find the order with the largest total refund, and summarize the refund reasons with source IDs.

The expected results for this synthetic dataset are:

- Net revenue: TWD 61,500.
- Largest total refund: TWD 5,000 for order O02.
- Refund reasons: a flickering screen and missing accessories.

| Example | Initial tools | What changes |
| --- | --- | --- |
| Flat | 20 direct tools | The agent sees the full operation catalog |
| Scoped | 4 core tools | The agent sees only the tools selected for this task |
| Progressive | 3 tools | The agent finds records, optionally checks metadata, then reads content |
| Discover | 3 tools | The agent finds operation schemas and calls a fixed dispatcher |
| Semantic | 5 tools | The backend calculates defined metrics; the agent retrieves supporting notes |
| Domain | 1 outer tool | An inner agent uses the 4 Scoped tools to do the investigation |

The backend and data are shared. The differences are in the interface and who does the work. Each server has its own entry point under [servers/](src/mcp_pattern_demo/servers).

The Scoped example uses a static tool set; it does not implement tenant authorization. Discover uses parameter-based dispatch, without running generated code.

## Results and limits

Each run creates `artifacts/<batch_id>/results.json` and `results.md`. They contain answers, automated checks, tool definitions and call order, token usage, timing, and trace links. Domain results include both outer and inner runs.

If trace data has not arrived yet, recheck it without rerunning the model:

```sh
uv run mcp-pattern-demo --verify-batch artifacts/<batch_id>/results.json
```

The CLI returns a nonzero exit code for a failed run, failed automated answer checks, incomplete usage, or incomplete tracking. Refund-reason checks use keywords and source IDs; they still need a separate review against the notes.

Two kinds of validation are documented:

- [Runnable example results](docs/experiment-review-v2.md): six designs, one model run each. These show what happened in those runs; they do not establish a lasting cost or speed advantage.
- [Skill validation](evals/results/v0.1.0/report.md): six new design and review scenarios, answered by agents and reviewed against a rubric. These scenarios were not implemented as six new MCP servers.

A smaller initial tool list does not guarantee lower total token usage. Applying a pattern also does not, by itself, establish production readiness. Check permissions, failures, data limits, and client compatibility for your system.

Private settings, raw traces, and local working notes are excluded from Git. The public reports use synthetic data and omit private trace links.

## Checks

```sh
python3 evals/check_package.py --repo-root .
uv run pytest -q
uv run ruff check src tests evals/check_package.py
uv run ruff format --check src tests evals/check_package.py
```

The package check verifies local skill links and named implementation references. Tests cover the shared calculations, parameter validation, source IDs, independent stdio servers, and usage accounting. They do not call a live model or remote tracking service.

More detail: [design review](docs/pattern-design-review.md), [experiment specification](docs/experiment-plan.md), and [sources](skills/mcp-architecture/references/sources.md).

## License

[Apache-2.0](LICENSE).
