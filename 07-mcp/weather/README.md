# Minimal Go MCP Server

这是一个使用 Go MCP SDK（`github.com/mark3labs/mcp-go`）实现的最小 MCP Server 示例。

## 功能

- 传输方式：`stdio`
- 工具：`hello_world`
- 入参：`name` (string, required)
- 返回：`Hello, <name>!`

## 本地运行

```bash
go run .
```

## 快速自测（JSON-RPC）

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"demo-client","version":"0.1.0"}}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hello_world","arguments":{"name":"MCP"}}}' \
| go run .
```

预期会看到 `Hello, MCP!`。

## 配置为 MCP Server

先构建二进制（推荐）：

```bash
go build -o mcp-demo .
```

假设你的项目绝对路径是：
`/Users/hank/workspace/mine/ai/ai-exp/mcp`

### Claude Desktop 示例

在 Claude Desktop 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "minimal-go-mcp": {
      "command": "/Users/hank/workspace/mine/ai/ai-exp/mcp/mcp-demo",
      "args": []
    }
  }
}
```

### Cursor 示例

在 Cursor MCP 配置中添加：

```json
{
  "mcpServers": {
    "minimal-go-mcp": {
      "command": "/Users/hank/workspace/mine/ai/ai-exp/mcp/mcp-demo",
      "args": []
    }
  }
}
```

## 文件

- `main.go`: 最小 MCP server 实现
- `go.mod` / `go.sum`: Go 依赖
