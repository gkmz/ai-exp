package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const deepseekAPI = "https://api.deepseek.com/chat/completions"

type Thinking struct {
	Type string `json:"type"` // "enabled" 或 "disabled"
}

type ResponseFormat struct {
	Type string `json:"type"` // "text" 或 "json_object"
}

type MockCS struct {
}

type ChatRequest struct {
	Model          string          `json:"model"`
	Messages       []Message       `json:"messages"`
	Thinking       *Thinking       `json:"thinking,omitempty"`
	MaxTokens      int             `json:"max_tokens,omitempty"`
	Temperature    *float64        `json:"temperature,omitempty"`
	TopP           *float64        `json:"top_p,omitempty"`
	ResponseFormat *ResponseFormat `json:"response_format,omitempty"`
	Stop           []string        `json:"stop,omitempty"`
	Stream         bool            `json:"stream,omitempty"`
}

type ChatResponse struct {
	Choices []struct {
		Message struct {
			Content          string `json:"content"`
			ReasoningContent string `json:"reasoning_content"`
		} `json:"message"`
		FinishReason string `json:"finish_reason"`
	} `json:"choices"`
	Usage struct {
		PromptTokens          int `json:"prompt_tokens"`
		CompletionTokens      int `json:"completion_tokens"`
		TotalTokens           int `json:"total_tokens"`
		PromptCacheHitTokens  int `json:"prompt_cache_hit_tokens"`
		PromptCacheMissTokens int `json:"prompt_cache_miss_tokens"`
		CompletionDetails     struct {
			ReasoningTokens int `json:"reasoning_tokens"`
		} `json:"completion_tokens_details"`
	} `json:"usage"`
}

type TicketSummary struct {
	Summary    string `json:"summary"`
	Category   string `json:"category"`
	RiskLevel  string `json:"risk_level"`
	NextAction string `json:"next_action"`
}

func float64Ptr(v float64) *float64 { return &v }

func (m *MockCS) callDeepSeek(ctx context.Context, req ChatRequest) (*ChatResponse, error) {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("DEEPSEEK_API_KEY is empty")
	}

	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, deepseekAPI, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("call deepseek: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("deepseek api status=%d body=%s", resp.StatusCode, string(b))
	}

	var result ChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	if len(result.Choices) == 0 {
		return nil, fmt.Errorf("empty choices")
	}

	return &result, nil
}

func (m *MockCS) validateSummary(s TicketSummary) error {
	if s.Summary == "" || s.Category == "" || s.RiskLevel == "" || s.NextAction == "" {
		return fmt.Errorf("missing required field: %+v", s)
	}

	allowedRisk := map[string]bool{
		"low": true, "medium": true, "high": true,
	}
	if !allowedRisk[s.RiskLevel] {
		return fmt.Errorf("invalid risk_level: %s", s.RiskLevel)
	}

	return nil
}

func (m *MockCS) summarizeTicket(ctx context.Context, dialogue string) (TicketSummary, error) {
	req := ChatRequest{
		Model:       "deepseek-v4-flash",
		Thinking:    &Thinking{Type: "disabled"},
		Temperature: float64Ptr(0.2),
		MaxTokens:   512,
		ResponseFormat: &ResponseFormat{
			Type: "json_object",
		},
		Messages: []Message{
			{
				Role: "system",
				Content: `你是客服工单分析助手。只输出 JSON，不要输出 Markdown，不要解释。
字段必须包含：
- summary: 一句话总结用户问题和客服答复
- category: refund/payment/account/logistics/other 之一
- risk_level: low/medium/high 之一
- next_action: 下一步处理动作`,
			},
			{
				Role:    "user",
				Content: "请分析这段客服对话：\n" + dialogue,
			},
		},
	}

	resp, err := m.callDeepSeek(ctx, req)
	if err != nil {
		return TicketSummary{}, err
	}

	choice := resp.Choices[0]
	if choice.FinishReason == "length" {
		return TicketSummary{}, fmt.Errorf("model output truncated by max_tokens")
	}
	if choice.FinishReason != "stop" {
		return TicketSummary{}, fmt.Errorf("unexpected finish_reason: %s", choice.FinishReason)
	}

	var summary TicketSummary
	if err := json.Unmarshal([]byte(choice.Message.Content), &summary); err != nil {
		return TicketSummary{}, fmt.Errorf("invalid json output: %w, raw=%s", err, choice.Message.Content)
	}
	if err := m.validateSummary(summary); err != nil {
		return TicketSummary{}, err
	}

	fmt.Printf(
		"usage prompt=%d completion=%d total=%d cache_hit=%d cache_miss=%d reasoning=%d\n",
		resp.Usage.PromptTokens,
		resp.Usage.CompletionTokens,
		resp.Usage.TotalTokens,
		resp.Usage.PromptCacheHitTokens,
		resp.Usage.PromptCacheMissTokens,
		resp.Usage.CompletionDetails.ReasoningTokens,
	)

	return summary, nil
}

func (m *MockCS) Run() {
	ctx := context.Background()
	dialogue := `用户：我上周申请退款了，怎么还没到账？
客服：您好，退款一般 3-5 个工作日到账。您这笔订单是周五提交的，预计本周三前到账。
用户：那我再等等。`

	summary, err := m.summarizeTicket(ctx, dialogue)
	if err != nil {
		fmt.Println("error:", err)
		return
	}
	fmt.Printf("%+v\n", summary)
}