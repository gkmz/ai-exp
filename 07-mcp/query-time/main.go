package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	// 创建 MCP 服务器并声明基本信息/能力，用于客户端初始化握手。
	s := server.NewMCPServer(
		"Query Time MCP",
		"0.1.0",
		// 提供tool能力
		server.WithToolCapabilities(true),
		server.WithRecovery(), // panic时恢复，避免崩溃
		server.WithInstructions("Provide the current date and time for the requested timezone."),
	)

	// 定义一个当前时间工具，暴露可选的时区参数。
	nowTool := mcp.NewTool("current_time",
		mcp.WithDescription("Report the current date and time."),
		mcp.WithString("timezone",
			mcp.Description("Optional IANA timezone (e.g., America/New_York). Defaults to the host zone."),
		),
	)

	// 注册工具及对应的处理函数。
	s.AddTool(nowTool, currentTimeHandler)

	log.Println("Starting query-time MCP server over STDIO")
	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "MCP server failed: %v\n", err)
		os.Exit(1)
	}
}

func currentTimeHandler(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// 从请求中读取时区参数，没有时使用默认值。
	requested := req.GetString("timezone", "")
	now := time.Now()
	zoneLabel := "local timezone"

	// 如果指定了时区，尝试加载并按该时区格式化时间。
	if requested != "" {
		loc, err := time.LoadLocation(requested)
		if err != nil {
			// 无效的时区参数直接返回错误结果。
			return mcp.NewToolResultErrorf("invalid timezone %q: %v", requested, err), nil
		}
		now = now.In(loc)
		zoneLabel = requested
	}

	// 返回包含当前时间的描述文本。
	text := fmt.Sprintf("Current date and time (%s): %s", zoneLabel, now.Format(time.RFC3339))
	return mcp.NewToolResultText(text), nil
}
