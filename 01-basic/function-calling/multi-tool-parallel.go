package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ====== 协议结构定义 ======
type ChatMessage struct {
	Role       string      `json:"role"`
	Content    any         `json:"content,omitempty"`
	ToolCallID string      `json:"tool_call_id,omitempty"`
	ToolCalls  []ToolCallW `json:"tool_calls,omitempty"`
}

type ToolCallW struct {
	ID       string `json:"id"`
	Type     string `json:"type"`
	Function struct {
		Name      string `json:"name"`
		Arguments string `json:"arguments"`
	} `json:"function"`
}

type chatCompletionReq struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Tools       []any         `json:"tools,omitempty"`
	ToolChoice  string        `json:"tool_choice,omitempty"`
	Temperature float64       `json:"temperature,omitempty"`
}

type chatCompletionResp struct {
	Choices []struct {
		Message struct {
			Role      string      `json:"role"`
			Content   string      `json:"content"`
			ToolCalls []ToolCallW `json:"tool_calls"`
		} `json:"message"`
	} `json:"choices"`
}

// ====== 指标采集定义 ======
type MetricsCollector interface {
	// 工具调用指标计数
	IncCounter(name string, labels map[string]string)
	// 工具调用指标观察
	ObserveHistogram(name string, value float64, labels map[string]string)
}

// InMemoryMetrics 用于示例演示；生产环境建议接 Prometheus / OTel
type InMemoryMetrics struct {
	mu       sync.Mutex           // 互斥锁，用于保护计数器和直方图的并发访问
	counters map[string]float64   // 计数器，用于记录指标的计数
	histos   map[string][]float64 // 直方图，用于记录指标的直方图
}

func NewInMemoryMetrics() *InMemoryMetrics {
	return &InMemoryMetrics{
		counters: map[string]float64{},
		histos:   map[string][]float64{},
	}
}

func (m *InMemoryMetrics) IncCounter(name string, labels map[string]string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.counters[metricKey(name, labels)]++
}

func (m *InMemoryMetrics) ObserveHistogram(name string, value float64, labels map[string]string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	key := metricKey(name, labels)
	m.histos[key] = append(m.histos[key], value)
}

func metricKey(name string, labels map[string]string) string {
	if len(labels) == 0 {
		return name
	}
	keys := make([]string, 0, len(labels))
	for k := range labels {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString(name)
	for _, k := range keys {
		b.WriteString("|")
		b.WriteString(k)
		b.WriteString("=")
		b.WriteString(labels[k])
	}
	return b.String()
}

func runMultiToolParallellyDemo() {
	// 关键步骤1：读取配置
	apiKey := strings.TrimSpace(os.Getenv("DEEPSEEK_API_KEY"))
	if apiKey == "" {
		log.Fatal("请先设置 DEEPSEEK_API_KEY")
	}
	baseURL := "https://api.deepseek.com/v1"
	model := "deepseek-chat"
	traceID := strconv.FormatInt(time.Now().UnixNano(), 10)
	mc := NewInMemoryMetrics()

	// 关键步骤2：定义工具（工具边界越清晰，越容易触发正确并行）
	tools := []any{
		map[string]any{
			"type": "function",
			"function": map[string]any{
				"name":        "get_weather",
				"description": "查询指定城市天气。",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"location": map[string]any{"type": "string", "description": "城市名，如 上海 或 纽约"},
					},
					"required": []string{"location"},
				},
			},
		},
		map[string]any{
			"type": "function",
			"function": map[string]any{
				"name":        "get_time",
				"description": "查询指定时区时间。",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"timezone": map[string]any{"type": "string", "description": "IANA 时区，如 America/New_York"},
					},
					"required": []string{"timezone"},
				},
			},
		},
	}

	// 关键步骤3：第一轮请求（模型可能返回多个 tool_calls）
	messages := []ChatMessage{
		{Role: "system", Content: "你是工具调用助手。独立任务优先并行；有依赖任务必须串行。"},
		{Role: "user", Content: "请同时查询上海和纽约天气，并告诉我纽约现在几点。"},
	}
	first, err := createChatCompletion(baseURL, apiKey, chatCompletionReq{
		Model:       model,
		Messages:    messages,
		Tools:       tools,
		ToolChoice:  "auto",
		Temperature: 0.2,
	})
	if err != nil || len(first.Choices) == 0 {
		log.Fatalf("首轮调用失败: %v", err)
	}
	assistantMsg := first.Choices[0].Message

	log.Printf("assistantMsg: %+v\n", assistantMsg)

	if len(assistantMsg.ToolCalls) == 0 {
		log.Fatal("未触发工具调用，请优化提示词或工具描述")
	}

	// 关键步骤4：并发执行工具 + 记录指标
	messages = append(messages, ChatMessage{
		Role:      "assistant",
		Content:   assistantMsg.Content,
		ToolCalls: assistantMsg.ToolCalls,
	})
	toolMsgs := runToolsInParallelWithMetrics(assistantMsg.ToolCalls, mc, traceID)
	messages = append(messages, toolMsgs...)

	// 关键步骤5：降级判定（示例阈值）
	if shouldDegrade(mc) {
		log.Println("触发降级：切换串行兜底/优先缓存策略")
	}

	// 关键步骤6：第二轮请求，拿最终自然语言答案
	roundStart := time.Now()
	second, err := createChatCompletion(baseURL, apiKey, chatCompletionReq{
		Model:       model,
		Messages:    messages,
		Temperature: 0.2,
	})
	if err != nil || len(second.Choices) == 0 {
		mc.IncCounter("final_answer_error_total", nil)
		log.Fatalf("二轮调用失败: %v", err)
	}
	mc.ObserveHistogram("final_answer_latency_ms", float64(time.Since(roundStart).Milliseconds()), nil)

	fmt.Println("----- 最终回答 -----")
	fmt.Println(second.Choices[0].Message.Content)
}

func runToolsInParallelWithMetrics(calls []ToolCallW, mc MetricsCollector, traceID string) []ChatMessage {
	results := make([]ChatMessage, len(calls))
	mc.ObserveHistogram("tool_calls_per_turn", float64(len(calls)), nil)
	var wg sync.WaitGroup

	for i, call := range calls {
		wg.Add(1)
		go func(idx int, c ToolCallW) {
			defer wg.Done()
			start := time.Now()

			output, retryN, isTimeout, ok := dispatchToolWithRetry(c.Function.Name, c.Function.Arguments)
			recordToolMetrics(mc, c.Function.Name, start, retryN, isTimeout, ok)

			log.Printf("trace_id=%s tool_call_id=%s tool=%s retry=%d timeout=%t spent=%.2f success=%t",
				traceID, c.ID, c.Function.Name, retryN, isTimeout, time.Since(start).Seconds(), ok)

			results[idx] = ChatMessage{Role: "tool", ToolCallID: c.ID, Content: output}
		}(i, call)
	}
	wg.Wait()
	return results
}

func recordToolMetrics(mc MetricsCollector, toolName string, start time.Time, retryN int, isTimeout, ok bool) {
	mc.ObserveHistogram("tool_exec_latency_ms", float64(time.Since(start).Milliseconds()), map[string]string{"tool_name": toolName})
	if ok {
		mc.IncCounter("tool_call_success_total", map[string]string{"tool_name": toolName})
	} else {
		mc.IncCounter("tool_call_error_total", map[string]string{"tool_name": toolName})
	}
	if isTimeout {
		mc.IncCounter("tool_call_timeout_total", map[string]string{"tool_name": toolName})
	}
	if retryN > 0 {
		mc.IncCounter("tool_retry_total", map[string]string{"tool_name": toolName})
	}
}

func dispatchToolWithRetry(name, args string) (output string, retryN int, isTimeout, ok bool) {
	const maxRetry = 1
	for i := 0; i <= maxRetry; i++ {
		retryN = i
		output, isTimeout, ok = dispatchToolOnce(name, args)
		if ok || !isTimeout {
			return
		}
	}
	return
}

func dispatchToolOnce(name, args string) (string, bool, bool) {
	switch name {
	case "get_weather":
		var in struct {
			Location string `json:"location"`
		}
		if err := json.Unmarshal([]byte(args), &in); err != nil || strings.TrimSpace(in.Location) == "" {
			return "weather 参数错误：缺少 location", false, false
		}
		time.Sleep(300 * time.Millisecond)
		return "上海：22°C，多云；纽约：16°C，晴", false, true
	case "get_time":
		var in struct {
			Timezone string `json:"timezone"`
		}
		if err := json.Unmarshal([]byte(args), &in); err != nil || strings.TrimSpace(in.Timezone) == "" {
			return "time 参数错误：缺少 timezone", false, false
		}
		time.Sleep(100 * time.Millisecond)
		return "纽约当前时间：08:35 AM", false, true
	default:
		return "未知工具：" + name, false, false
	}
}

func shouldDegrade(mc *InMemoryMetrics) bool {
	// 示例逻辑：若本轮发生 timeout，就触发降级
	mc.mu.Lock()
	defer mc.mu.Unlock()
	for k, v := range mc.counters {
		if strings.HasPrefix(k, "tool_call_timeout_total") && v > 0 {
			return true
		}
	}
	return false
}

func createChatCompletion(baseURL, apiKey string, reqBody chatCompletionReq) (*chatCompletionResp, error) {
	body, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, strings.TrimRight(baseURL, "/")+"/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("llm 请求失败：status=%d body=%s", resp.StatusCode, string(data))
	}
	var out chatCompletionResp
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func getenv(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
