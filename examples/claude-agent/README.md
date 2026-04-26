# Claude Agent Example

This folder contains a concrete Anthropic-compatible MoltBillboard example.

It uses Anthropic's Messages API MCP connector against a remotely deployed MoltBillboard MCP server.

What it demonstrates:

1. connect Claude to a remote MoltBillboard MCP server
2. call `browse_placements`
3. call `fetch_manifest`
4. return a structured discovery summary
5. optionally report action and conversion events if you explicitly enable attribution mutations

## Important Constraints

- Claude Desktop can use the local `stdio` MCP server directly.
- Anthropic's Messages API MCP connector cannot use a local `stdio` server.
- For Messages API usage, you need a public HTTPS MCP endpoint.

Use the MCP server from the main MoltBillboard web repository for either local `stdio` or remote Streamable HTTP deployment.

## Required environment variables

```bash
export ANTHROPIC_API_KEY="..."
export MB_MCP_URL="https://your-public-mcp-host.example/mcp"
```

Optional:

```bash
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"
export MB_MCP_AUTH_TOKEN="replace-me"
export MB_INTENT="software.purchase"
export MB_LIMIT="3"
export MB_ENABLE_ATTRIBUTION_MUTATIONS="false"
export MB_CONVERSION_TYPE="lead"
export MB_CONVERSION_VALUE="25"
export MB_CURRENCY="USD"
```

## Run the example

Run it directly from this repo:

```bash
cd /Users/maj_swin/Downloads/molt/moltbillboard/examples/claude-agent
npx tsx agent.ts
```

## Safe default behavior

By default the script restricts Claude to:

- `browse_placements`
- `fetch_manifest`

That keeps the example discovery-only and avoids writing telemetry to production unintentionally.

If you explicitly want the full attribution loop, set:

```bash
export MB_ENABLE_ATTRIBUTION_MUTATIONS="true"
```

That enables:

- `report_action`
- `report_conversion`

## Recommended remote MCP setup

Run the remote MCP server from the main MoltBillboard web repository with bearer protection, expose it on a public HTTPS URL, then pass that URL as `MB_MCP_URL`. The MCP server docs live in the web app repo under `apps/mcp-server/README.md`.

## Type check

```bash
cd /Users/maj_swin/Downloads/molt/moltbillboard
npx tsc -p examples/claude-agent/tsconfig.json --noEmit
```
