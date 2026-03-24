# hello-mcp

这是一个极简的 Go 版本 MCP（Model Context Protocol）服务示例，仅暴露一个 `hello` 工具。服务通过 HTTP 接收 JSON-RPC，并返回友好的问候文本，展示了如何用最少依赖实现 MCP。

## 启动

```bash
go run main.go --port 8080
```

服务器默认在 `/mcp` 监听 POST 请求；访问 `/` 会提示服务已就绪。

## 支持的交互

- POST `/mcp`：接收 JSON-RPC 2.0 的 `initialize`、`tools/list`、`tools/call` 请求，并返回标准包络。成功响应会携带 `MCP-Session-Id` 头。
- GET `/mcp`：保持 SSE/流式连接；Inspector 会带着 `MCP-Session-Id` 读取这一流，所有 POST 的响应也会通过这条流转发到客户端。
- DELETE `/mcp`：关闭会话并释放流式连接，Inspector 在结束时会发出这个请求。

## 示例 Inspector 流程

1. 使用 POST `/mcp` 发起 `initialize`，记录响应头里的 `MCP-Session-Id`。
2. 用同一个 `MCP-Session-Id` 访问 GET `/mcp`，保持长连接以接收 `event: mcp` 推送。
3. 再次 POST `/mcp` 调用 `tools/list` / `tools/call`（带 `MCP-Session-Id` 头）即可调用 `hello` 工具。
4. 完成后通过 DELETE `/mcp` 关闭连接，服务器会把该会话移除。

## 示例 `tools/call`

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
      "arguments": {"user_name": "MCP 客户端", "greeting": "你好"}
    }
  }'
```

## 预期响应

```json
{
  "jsonrpc": "2.0",
  "id": "hello-call",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "你好, MCP 客户端! Welcome to the MCP hello service."
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

以上 JSON 也会出现在 GET `/mcp` 的 SSE 流里，`event: mcp` 下的 `data` 字段即该响应。
