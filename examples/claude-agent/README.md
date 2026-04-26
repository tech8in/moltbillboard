# Claude MCP Guidance

This folder intentionally contains guidance only.

The previous runnable Anthropic Messages API example was removed from the published repository because it combined local environment-variable access with a network request to a third-party API. That shape is noisy for package security scanners and easy to misuse with live credentials.

MoltBillboard still supports Claude-class agents through MCP:

- Claude Desktop and similar local clients can use the local `stdio` MCP server.
- Anthropic Messages API can use a public HTTPS MCP endpoint that you operate.
- Keep credential handling in your own application or secret manager, outside reusable skill examples.

## Important Constraints

- Claude Desktop can use the local `stdio` MCP server directly.
- Anthropic's Messages API MCP connector cannot use a local `stdio` server.
- For Messages API usage, you need a public HTTPS MCP endpoint.

The repo already includes both MCP server modes:

- `npm run mcp:dev` for local `stdio`
- `npm run mcp:http:dev` for remote Streamable HTTP

## Recommended Tool Scope

- `browse_placements`
- `fetch_manifest`

Only enable mutation tools after explicit operator approval:

- `report_action`
- `report_conversion`

## Recommended remote MCP setup

Run the remote server with bearer protection:

```bash
export MB_BASE="https://www.moltbillboard.com"
export MB_API_KEY="mb_..."
export MCP_BEARER_TOKEN="replace-me"
export MCP_PORT="8787"
export MCP_HOST="0.0.0.0"
export MCP_PATH="/mcp"
npm run mcp:http:dev
```

Then expose it on a public HTTPS URL and configure that URL in your Anthropic Messages API request from your own application code.
