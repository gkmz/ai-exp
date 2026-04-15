# query-time-mcp

基于 `mark3labs/mcp-go` 框架实现的 MCP 服务，提供 `current_time` 工具用来查询当前日期与时间。

## 运行

```bash
cd path/to/query-time
go run main.go
```

服务通过 STDIO 与 MCP 客户端通信，Inspector 可通过 `npx @modelcontextprotocol/inspector --transport stdio` 调试；或者用 `streamable-http` proxy 方式把 `stdin/stdout` 映射到 HTTP。  

## 工具说明

- `current_time`
  - `timezone`（可选）：IANA 时区名称，比如 `Asia/Shanghai`。为空时返回主机本地时间。
  - 返回一段包含当前标准时间（RFC3339）的文本。

## 开发提示

1. 依赖通过 `go get github.com/mark3labs/mcp-go` 获取，源码会自动处理 MCP 环境与 JSON-RPC。  
2. 按需在 `currentTimeHandler` 中扩展格式、结构化输出或为 `timezone` 添加验证逻辑。  
