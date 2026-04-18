package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
)

const anthropicAPI = "https://api.anthropic.com/v1/messages"

// --- 请求体（只声明本示例用到的字段）---

type messageCreateRequest struct {
	Model       string          `json:"model"`
	MaxTokens   int             `json:"max_tokens"`
	Tools       []toolDef       `json:"tools,omitempty"`
	ToolChoice  json.RawMessage `json:"tool_choice,omitempty"`
	Messages    []message       `json:"messages"`
	System      string          `json:"system,omitempty"`
}

type toolDef struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"input_schema"`
}

type message struct {
	Role    string `json:"role"`
	Content any    `json:"content"` // string 或 []contentBlock
}

type contentBlock struct {
	Type string `json:"type"`

	// text
	Text string `json:"text,omitempty"`

	// tool_use
	ID    string         `json:"id,omitempty"`
	Name  string         `json:"name,omitempty"`
	Input map[string]any `json:"input,omitempty"`

	// tool_result
	ToolUseID string `json:"tool_use_id,omitempty"`
	Content   any    `json:"content,omitempty"` // string 或嵌套块
	IsError   bool   `json:"is_error,omitempty"`
}

// --- 响应体（只解析本示例关心的字段）---

type messageResponse struct {
	ID         string          `json:"id"`
	Role       string          `json:"role"`
	Content    []contentBlock  `json:"content"`
	StopReason string          `json:"stop_reason"`
	Usage      json.RawMessage `json:"usage"`
}

func runClaudeToolDemo() {
	apiKey := strings.TrimSpace(os.Getenv("ANTHROPIC_API_KEY"))
	if apiKey == "" {
		log.Fatal("请设置环境变量 ANTHROPIC_API_KEY")
	}

	client := &http.Client{}

	tools := []toolDef{
		{
			Name: "get_weather",
			Description: "根据城市名返回一句模拟天气描述。仅用于演示 Tool Use；" +
				"当用户询问某地天气、气温、是否下雨时使用；不要用于与天气无关的问题。",
			InputSchema: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"location": map[string]any{
						"type":        "string",
						"description": "城市或地区，例如 上海、San Francisco, CA",
					},
					"unit": map[string]any{
						"type": "string",
						"enum": []string{"celsius", "fahrenheit"},
					},
				},
				"required": []string{"location"},
			},
		},
	}

	// 第一轮：让模型决定是否调用工具（auto 可省略，这里写出来便于对照文档）
	toolChoiceAuto, _ := json.Marshal(map[string]any{
		"type": "auto",
	})

	firstUser := message{
		Role: "user",
		Content: []contentBlock{
			{Type: "text", Text: "帮我看看上海明天适合跑步吗？从天气角度简单说说。"},
		},
	}

	firstReq := messageCreateRequest{
		Model:      "claude-sonnet-4-20250514",
		MaxTokens:  1024,
		Tools:      tools,
		ToolChoice: toolChoiceAuto,
		Messages:   []message{firstUser},
	}

	firstResp, err := callMessages(client, apiKey, firstReq)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("第一轮 stop_reason=%s", firstResp.StopReason)

	if firstResp.StopReason != "tool_use" {
		log.Fatalf("预期 stop_reason=tool_use，实际为 %s；请检查提示语或模型行为", firstResp.StopReason)
	}

	// 解析 tool_use 块并执行本地工具
	var toolUses []contentBlock
	for _, b := range firstResp.Content {
		if b.Type == "tool_use" {
			toolUses = append(toolUses, b)
		}
	}
	if len(toolUses) == 0 {
		log.Fatal("响应中未找到 tool_use 块")
	}

	toolResults := make([]contentBlock, 0, len(toolUses))
	for _, tu := range toolUses {
		out, execErr := runTool(tu.Name, tu.Input)
		tb := contentBlock{
			Type:      "tool_result",
			ToolUseID: tu.ID,
		}
		if execErr != nil {
			tb.Content = execErr.Error()
			tb.IsError = true
		} else {
			tb.Content = out
		}
		toolResults = append(toolResults, tb)
	}

	// 第二轮：assistant 原样带回 + user 仅含 tool_result（本示例无额外 user 文本）
	secondReq := messageCreateRequest{
		Model:     "claude-sonnet-4-20250514",
		MaxTokens: 1024,
		Tools:     tools,
		Messages: []message{
			firstUser,
			{
				Role:    "assistant",
				Content: firstResp.Content,
			},
			{
				Role:    "user",
				Content: toolResults,
			},
		},
	}

	secondResp, err := callMessages(client, apiKey, secondReq)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("第二轮 stop_reason=%s", secondResp.StopReason)

	for _, b := range secondResp.Content {
		if b.Type == "text" {
			fmt.Println("--- Claude 最终回复 ---")
			fmt.Println(b.Text)
		}
	}
}

func callMessages(client *http.Client, apiKey string, body messageCreateRequest) (*messageResponse, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest(http.MethodPost, anthropicAPI, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")
	req.Header.Set("content-type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("API %s: %s", resp.Status, string(raw))
	}

	var out messageResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func runTool(name string, input map[string]any) (string, error) {
	switch name {
	case "get_weather":
		loc, _ := input["location"].(string)
		if strings.TrimSpace(loc) == "" {
			return "", fmt.Errorf("缺少 location")
		}
		unit, _ := input["unit"].(string)
		if unit == "" {
			unit = "celsius"
		}
		// 假数据，仅演示协议
		return fmt.Sprintf("【模拟】%s：气温约 22%s，微风，降水概率低，适合户外慢跑。",
			loc, unitLabel(unit)), nil
	default:
		return "", fmt.Errorf("未知工具: %s", name)
	}
}

func unitLabel(unit string) string {
	switch unit {
	case "fahrenheit":
		return "°F"
	default:
		return "°C"
	}
}