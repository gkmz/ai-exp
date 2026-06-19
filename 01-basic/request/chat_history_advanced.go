package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"time"

	tiktoken "github.com/pkoukk/tiktoken-go"
)

// ============================================================
// 进阶版多轮对话：Token 级滑动窗口 + reasoning_content 过滤 + 摘要压缩 + Session 隔离
// 配合教程 09 篇使用
// ============================================================

// AdvancedMessage 扩展消息结构，支持 reasoning_content
type AdvancedMessage struct {
	Role             string `json:"role"`
	Content          string `json:"content"`
	ReasoningContent string `json:"reasoning_content,omitempty"`
}

// ChatHistoryAdvancedDemo 进阶多轮对话演示
type ChatHistoryAdvancedDemo struct{}

const (
	advancedAPIURL     = "https://api.deepseek.com/chat/completions"
	tokenBudget        = 4000  // 留给历史消息的 token 预算（生产环境按需调整）
	compressThreshold  = 3000  // 超过此 token 数触发摘要压缩
	encodingNameAdvanced = "cl100k_base"
)

// --- 1. Token 级滑动窗口 ---

// countMessageTokens 计算单条消息的 token 数
func countMessageTokens(msg AdvancedMessage) int {
	enc, err := tiktoken.GetEncoding(encodingNameAdvanced)
	if err != nil {
		return len(msg.Content) / 4 // fallback 粗估
	}
	// 每条消息有 role + content，加上格式 overhead 约 4 tokens
	tokens := len(enc.Encode(msg.Content, nil, nil)) + 4
	return tokens
}

// countAllTokens 计算整个历史的 token 数
func countAllTokens(history []AdvancedMessage) int {
	total := 0
	for _, msg := range history {
		total += countMessageTokens(msg)
	}
	return total
}

// trimByTokenBudget 按 token 预算从头删除旧消息（保留 system prompt）
func trimByTokenBudget(history []AdvancedMessage, budget int) []AdvancedMessage {
	total := countAllTokens(history)
	if total <= budget {
		return history
	}

	// history[0] 是 system prompt，从 history[1] 开始删
	trimmed := []AdvancedMessage{history[0]}
	// 从最新的消息往前加，直到塞不下
	remaining := budget - countMessageTokens(history[0])
	start := len(history) - 1
	for i := start; i >= 1; i-- {
		msgTokens := countMessageTokens(history[i])
		if remaining-msgTokens < 0 {
			break
		}
		remaining -= msgTokens
		start = i
	}
	trimmed = append(trimmed, history[start:]...)

	fmt.Printf("[滑动窗口] 历史从 %d 条截断到 %d 条，token 从 %d 降到 %d\n",
		len(history), len(trimmed), total, countAllTokens(trimmed))
	return trimmed
}

// --- 2. reasoning_content 过滤 ---

// storeAssistantMessage 存储 assistant 回复时过滤 reasoning_content
// 多轮对话只应把 content 放进 history，reasoning_content 不回灌（否则 400 错误）
func storeAssistantMessage(history []AdvancedMessage, content, reasoningContent string) []AdvancedMessage {
	// reasoning_content 可以单独记录到日志/调试系统，但不进 messages 数组
	if reasoningContent != "" {
		fmt.Printf("[推理过程] %s...\n", truncate(reasoningContent, 100))
	}
	return append(history, AdvancedMessage{
		Role:    "assistant",
		Content: content,
		// 注意：这里故意不设置 ReasoningContent，避免回灌
	})
}

func truncate(s string, maxRunes int) string {
	runes := []rune(s)
	if len(runes) <= maxRunes {
		return s
	}
	return string(runes[:maxRunes]) + "..."
}

// --- 3. 摘要压缩 ---

// compressHistory 当历史过长时，用 AI 对早期对话做摘要
func compressHistory(ctx context.Context, history []AdvancedMessage) ([]AdvancedMessage, error) {
	total := countAllTokens(history)
	if total <= compressThreshold {
		return history, nil
	}

	// 保留 system prompt (history[0]) 和最近 4 条消息
	keepRecent := 4
	if len(history) <= keepRecent+1 {
		return history, nil // 不够压缩
	}

	// 要压缩的部分：history[1] 到 history[len-keepRecent]
	oldMessages := history[1 : len(history)-keepRecent]
	recentMessages := history[len(history)-keepRecent:]

	// 把旧消息格式化成文本
	var buf bytes.Buffer
	for _, msg := range oldMessages {
		fmt.Fprintf(&buf, "%s: %s\n", msg.Role, msg.Content)
	}

	// 调用 AI 做摘要
	summaryPrompt := []AdvancedMessage{
		{Role: "system", Content: "你是一个对话摘要助手。请用 2-3 句话概括以下对话的核心内容，保留关键事实和结论，去掉寒暄和重复。只输出摘要，不要解释。"},
		{Role: "user", Content: buf.String()},
	}

	resp, err := callDeepSeekAdvanced(ctx, "deepseek-v4-flash", summaryPrompt)
	if err != nil {
		return history, fmt.Errorf("摘要压缩失败: %w", err) // 压缩失败不致命，返回原历史
	}

	summary := resp.Choices[0].Message.Content

	// 构建压缩后的历史
	compressed := []AdvancedMessage{
		history[0], // system prompt
		{Role: "system", Content: fmt.Sprintf("以下是之前对话的摘要：%s", summary)},
	}
	compressed = append(compressed, recentMessages...)

	fmt.Printf("[摘要压缩] %d 条旧消息压缩为 1 条摘要，token 从 %d 降到 %d\n",
		len(oldMessages), total, countAllTokens(compressed))
	return compressed, nil
}

// --- 4. Session 隔离 ---

// SessionStore 线程安全的多会话管理
type SessionStore struct {
	mu       sync.RWMutex
	sessions map[string][]AdvancedMessage
}

func NewSessionStore() *SessionStore {
	return &SessionStore{
		sessions: make(map[string][]AdvancedMessage),
	}
}

// GetOrCreate 获取已有会话，或创建新会话
func (s *SessionStore) GetOrCreate(sessionID, systemPrompt string) []AdvancedMessage {
	s.mu.Lock()
	defer s.mu.Unlock()
	if history, ok := s.sessions[sessionID]; ok {
		return history
	}
	history := []AdvancedMessage{
		{Role: "system", Content: systemPrompt},
	}
	s.sessions[sessionID] = history
	return history
}

// Update 更新会话历史
func (s *SessionStore) Update(sessionID string, history []AdvancedMessage) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.sessions[sessionID] = history
}

// Delete 删除会话（用于 TTL 过期或用户主动清除）
func (s *SessionStore) Delete(sessionID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.sessions, sessionID)
}

// --- API 调用 ---

type advancedChatRequest struct {
	Model    string            `json:"model"`
	Messages []AdvancedMessage `json:"messages"`
}

type advancedChatResponse struct {
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
		PromptCacheHitTokens  int `json:"prompt_cache_hit_tokens"`
		PromptCacheMissTokens int `json:"prompt_cache_miss_tokens"`
	} `json:"usage"`
}

func callDeepSeekAdvanced(ctx context.Context, model string, messages []AdvancedMessage) (*advancedChatResponse, error) {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("DEEPSEEK_API_KEY is empty")
	}

	body, err := json.Marshal(advancedChatRequest{Model: model, Messages: messages})
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, advancedAPIURL, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API status=%d body=%s", resp.StatusCode, string(b))
	}

	var result advancedChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	if len(result.Choices) == 0 {
		return nil, fmt.Errorf("empty choices")
	}
	return &result, nil
}

// --- 演示入口 ---

func (d *ChatHistoryAdvancedDemo) Run() {
	ctx := context.Background()
	store := NewSessionStore()
	sessionID := "demo-session-001"
	systemPrompt := "你是一个专业的 Go 语言助手，回答要简洁。"

	// 模拟多轮对话
	questions := []string{
		"Go 的 goroutine 和线程有什么区别？",
		"那 channel 是什么？",
		"给我一个 worker pool 的例子",
		"刚才说的 goroutine 调度器是 G-M-P 模型吗？",
		"总结一下我们聊了什么",
	}

	for i, q := range questions {
		fmt.Printf("\n=== 第 %d 轮 ===\n", i+1)
		fmt.Printf("User: %s\n", q)

		// 获取会话历史
		history := store.GetOrCreate(sessionID, systemPrompt)

		// 追加用户消息
		history = append(history, AdvancedMessage{Role: "user", Content: q})

		// Token 级滑动窗口
		history = trimByTokenBudget(history, tokenBudget)

		// 摘要压缩（超过阈值时触发）
		history, _ = compressHistory(ctx, history)

		// 调用 API
		resp, err := callDeepSeekAdvanced(ctx, "deepseek-v4-flash", history)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			continue
		}

		choice := resp.Choices[0]

		// 存储 assistant 回复（过滤 reasoning_content）
		history = storeAssistantMessage(history, choice.Message.Content, choice.Message.ReasoningContent)

		// 打印缓存命中率
		fmt.Printf("AI: %s\n", truncate(choice.Message.Content, 200))
		fmt.Printf("[usage] prompt=%d completion=%d cache_hit=%d cache_miss=%d\n",
			resp.Usage.PromptTokens, resp.Usage.CompletionTokens,
			resp.Usage.PromptCacheHitTokens, resp.Usage.PromptCacheMissTokens)

		// 更新会话
		store.Update(sessionID, history)
	}
}
