# hello-mcp

A Go implementation of a Model Context Protocol (MCP) service that exposes the `hello` tool plus the minimal streaming HTTP transport required by Inspector. The service handles the `initialize`/`tools/list` lifecycle, returns structured greetings, and exposes SSE-style `/mcp` streaming for the Inspector proxy.

## Run

```bash
go run main.go --port 8080
```

The server listens on `/mcp`. The root `/` path still returns a simple readiness message.

## Transport behavior

- **POST /mcp** accepts JSON-RPC 2.0 requests such as `initialize`, `tools/list`, and `tools/call`.
- **GET /mcp** keeps a server-sent-events-style stream open so Inspector and other MCP clients can observe responses; this stream requires `MCP-Session-Id` (returned by `initialize`).
- **DELETE /mcp** tears down the session mapped to `MCP-Session-Id`. Inspector will call this when closing the streaming transport.
- All POST responses (success or error) include `MCP-Session-Id` and are also forwarded to the open GET stream so Inspector can surface them.

## Sample Inspector flow

1. POST `initialize` (JSON-RPC 2.0) to `/mcp`. The response contains `MCP-Session-Id`.
2. Open `GET /mcp` with the same session ID to start the SSE/streamable transport.
3. Call `tools/list` and `tools/call` with header `MCP-Session-Id` to interact with the `hello` tool.
4. When done, call `DELETE /mcp` with the session ID to release the stream.

## Example `tools/call`

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Session-Id: <session-id>" \
  -d '{
    "jsonrpc": "2.0",
    "id": "hello-call",
    "method": "tools/call",
    "params": {
      "name": "hello",
      "arguments": {"user_name": "MCP Client", "greeting": "Hiya"}
    }
  }'
```

### Expected response

```json
{
  "jsonrpc": "2.0",
  "id": "hello-call",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Hiya, MCP Client! Welcome to the MCP hello service."
      }
    ],
    "metadata": {
      "tool": "hello",
      "version": "1.0",
      "note": "Minimal sample tool"
    }
  }
}
```

The same JSON appears as the `data` payload on the SSE stream opened via GET `/mcp`.
