# Semantic Code Search in Claude Code with LogosDB

This example shows how to wire **[LogosDB](https://github.com/jose-compu/logosdb)** — a fast, local HNSW vector database — into Claude Code via the Model Context Protocol (MCP), giving Claude persistent semantic memory over your codebase.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Node.js ≥ 18
- An OpenAI API key (or a Voyage AI key — set `EMBEDDING_PROVIDER=voyageai`)

## 1. Add the MCP server to your project

Create `.claude/mcp.json` at your project root:

```json
{
  "mcpServers": {
    "logosdb": {
      "command": "npx",
      "args": ["-y", "logosdb-mcp-server"],
      "env": {
        "LOGOSDB_PATH": "./.logosdb",
        "EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "<your-openai-api-key>"
      }
    }
  }
}
```

The server starts automatically when Claude Code launches in that directory.  
The `.logosdb/` folder is local, persistent, and gitignore-able.

## 2. Slash commands (optional convenience)

Claude Code picks up `.claude/commands/` files as `/slash` commands.  
Copy the three files from [logosdb/.claude/commands/](https://github.com/jose-compu/logosdb/tree/main/.claude/commands) into your project:

| Command | What it does |
|---------|-------------|
| `/index <path> [--namespace=<name>]` | Embed a file or directory tree |
| `/search <query> [--namespace=<name>]` | Semantic similarity search |
| `/forget [--id=<id>\|--query=<q>]` | Remove vectors from the store |

## 3. Example session

```
$ cd myproject
$ claude

> /index ./src --namespace=backend
Indexed 42 files into 'backend' collection.

> Find where we handle JWT validation
Searching 'backend' for "JWT validation"…

Found 3 matches:
  1. src/auth/jwt.ts          (score 0.94)
  2. src/middleware/auth.ts   (score 0.87)
  3. src/utils/token.ts       (score 0.72)

> Show me the first result
[Claude reads src/auth/jwt.ts and explains the implementation]

> /search "rate limiting middleware" --namespace=backend
Found 2 matches:
  1. src/middleware/rateLimit.ts  (score 0.91)
  2. src/utils/redis.ts           (score 0.78)

> /forget --query="rate limiting middleware" --namespace=backend
Removed 2 vectors from 'backend'.
```

## How it works

1. `/index` calls the `logosdb_index_file` MCP tool, which walks the directory, splits each file into overlapping text chunks, embeds them via the configured provider, and stores the vectors in the local `.logosdb/` store.
2. `/search` calls `logosdb_search`, embeds the natural-language query with the same model, and performs an HNSW approximate nearest-neighbour search — all locally, in milliseconds.
3. The index survives across Claude Code sessions; re-run `/index` only when files change.

## Available MCP tools

| Tool | Description |
|------|-------------|
| `logosdb_index` | Index a text snippet directly |
| `logosdb_index_file` | Index a file or directory (recursive) |
| `logosdb_search` | Semantic similarity search |
| `logosdb_list` | List all namespaces |
| `logosdb_info` | Count vectors in a namespace |
| `logosdb_delete` | Remove a vector by ID |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGOSDB_PATH` | `./.logosdb` | Directory where the index files are stored |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `voyageai` |
| `OPENAI_API_KEY` | — | Required when provider is `openai` |
| `VOYAGE_API_KEY` | — | Required when provider is `voyageai` |

## Resources

- [logosdb-mcp-server on npm](https://www.npmjs.com/package/logosdb-mcp-server)
- [LogosDB GitHub](https://github.com/jose-compu/logosdb)
- [MCP specification](https://modelcontextprotocol.io)
