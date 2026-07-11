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

// ToolBatchStats 记录单轮工具批次的实际耗时和串行估算耗时。
type ToolBatchStats struct {
	ActualDuration          time.Duration
	SerialEstimatedDuration time.Duration
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
	model := "deepseek-v4-flash"
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
		map[string]any{
			"type": "function",
			"function": map[string]any{
				"name":        "plan_attractions",
				"description": "根据指定城市和已经查询到的天气规划景点。调用前必须先获得该城市的天气结果。",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"location": map[string]any{"type": "string", "description": "城市名"},
						"weather":  map[string]any{"type": "string", "description": "get_weather 返回的天气结果"},
					},
					"required": []string{"location", "weather"},
				},
			},
		},
	}

	// 关键步骤3：在同一任务中同时包含独立调用和依赖调用，让模型自行选择执行顺序。
	messages := []ChatMessage{
		{Role: "system", Content: "你是工具调用助手。没有依赖关系的工具必须在同一轮并行调用；有依赖关系的工具必须等待前置结果，再在后续轮次调用。"},
		{Role: "user", Content: "请查询上海和纽约天气，同时告诉我纽约现在几点；然后根据上海的天气规划适合游览的景点。"},
	}

	// 关键步骤4：持续让模型决策。每一轮中的工具并行执行，依赖后续结果的工具自然进入下一轮。
	const maxTurns = 6
	var workflowActualDuration time.Duration
	var workflowSerialEstimatedDuration time.Duration
	for turn := 1; turn <= maxTurns; turn++ {
		roundStart := time.Now()
		resp, err := createChatCompletion(baseURL, apiKey, chatCompletionReq{
			Model: model, Messages: messages, Tools: tools, ToolChoice: "auto", Temperature: 0.2,
		})
		if err != nil || len(resp.Choices) == 0 {
			mc.IncCounter("final_answer_error_total", nil)
			log.Fatalf("第 %d 轮调用失败: %v", turn, err)
		}
		mc.ObserveHistogram("final_answer_latency_ms", float64(time.Since(roundStart).Milliseconds()), map[string]string{"turn": strconv.Itoa(turn)})

		assistantMsg := resp.Choices[0].Message
		messages = append(messages, ChatMessage{Role: "assistant", Content: assistantMsg.Content, ToolCalls: assistantMsg.ToolCalls})
		log.Printf("turn=%d assistantMsg: %+v\n", turn, assistantMsg)

		// 没有工具调用表示模型已经结合全部工具结果生成了最终回答。
		if len(assistantMsg.ToolCalls) == 0 {
			recordToolWorkflowMetrics(mc, traceID, workflowActualDuration, workflowSerialEstimatedDuration)
			fmt.Println("----- 最终回答 -----")
			fmt.Println(assistantMsg.Content)
			return
		}

		toolMessages, batchStats := runToolsInParallelWithMetrics(assistantMsg.ToolCalls, mc, traceID)
		messages = append(messages, toolMessages...)
		workflowActualDuration += batchStats.ActualDuration
		workflowSerialEstimatedDuration += batchStats.SerialEstimatedDuration
		if shouldDegrade(mc) {
			log.Println("触发降级：切换串行兜底/优先缓存策略")
		}
	}

	log.Fatalf("超过最大轮次 %d，疑似陷入工具调用循环", maxTurns)

	// output:
	// 2026/07/12 00:49:30 turn=1 assistantMsg: {Role:assistant Content:好的！我先并行查询上海和纽约的天气，以及纽约的时间。 ToolCalls:[{ID:call_00_fjDl4j30mtX4t5QmVRyQ9573 Type:function Function on:{Name:get_weather Arguments:{"location": "上海"}}} {ID:call_01_Bo9qXTqYdAE3aGohgxou0000 Type:function Function:{Name:get_weather Arguments:{"location": "纽约"}}} {ID:call_02_zSkAE8Al7
	// Yt3pgx1lFTy4440 Type:function Function:{Name:get_time Arguments:{"timezone": "America/New_York"}}}]}
	// 2026/07/12 00:49:30 trace_id=1783788568030215000 tool_call_id=call_02_zSkAE8Al7Yt3pgx1lFTy4440 tool=get_time retry=0 timeout=false spent=0.10 success=true
	// 2026/07/12 00:49:30 trace_id=1783788568030215000 tool_call_id=call_01_Bo9qXTqYdAE3aGohgxou0000 tool=get_weather retry=0 timeout=false spent=0.30 success=true
	// 2026/07/12 00:49:30 trace_id=1783788568030215000 tool_call_id=call_00_fjDl4j30mtX4t5QmVRyQ9573 tool=get_weather retry=0 timeout=false spent=0.30 success=true
	// 2026/07/12 00:49:30 trace_id=1783788568030215000 tool_count=3 batch_ms=301 serial_estimated_ms=702 saved_ms=401 speedup=2.33x
	// 2026/07/12 00:49:32 turn=2 assistantMsg: {Role:assistant Content:好的！现在根据上海的天气来规划适合游览的景点。 ToolCalls:[{ID:call_00_EVUWhchjhjJFvRazXiB59424 Type:function Function:{Na
	// me:plan_attractions Arguments:{"location": "上海", "weather": "22°C，多云"}}}]}
	// 2026/07/12 00:49:33 trace_id=1783788568030215000 tool_call_id=call_00_EVUWhchjhjJFvRazXiB59424 tool=plan_attractions retry=0 timeout=false spent=0.20 success=true
	// 2026/07/12 00:49:33 trace_id=1783788568030215000 tool_count=1 batch_ms=201 serial_estimated_ms=201 saved_ms=0 speedup=1.00x
	// 2026/07/12 00:49:35 turn=3 assistantMsg: {Role:assistant Content:以下是所有查询结果和规划建议：
	//
	// ---
	//
	// ### 🌤️ 天气情况
	// | 城市 | 天气 |
	// |------|------|
	// | **上海** | **22°C，多云** |
	// | **纽约** | **16°C，晴** |
	//
	// ### 🕐 纽约当前时间
	// **08:35 AM**（美国东部时间）
	//
	// ### 🏯 上海景点推荐（基于多云天气）
	// 根据当前上海 **22°C、多云** 的天气，推荐游览：
	// 1. **上海博物馆** — 室内参观，不受天气影响
	// 2. **豫园** — 古典园林，多云天气漫步非常舒适
	// 3. **外滩** — 多云天气适合沿江散步，欣赏万国建筑
	// > ⚠️ 建议携带雨具，以防多云转雨
	//
	// 有任何其他需要帮忙的吗？😊 ToolCalls:[]}
	// 2026/07/12 00:49:35 trace_id=1783788568030215000 workflow_actual_ms=502 workflow_serial_estimated_ms=903 workflow_saved_ms=401 workflow_speedup=1.80x
	// ----- 最终回答 -----
	// 以下是所有查询结果和规划建议：
	//
	// ---
	//
	// ### 🌤️ 天气情况
	// | 城市 | 天气 |
	// |------|------|
	// | **上海** | **22°C，多云** |
	// | **纽约** | **16°C，晴** |
	//
	// ### 🕐 纽约当前时间
	// **08:35 AM**（美国东部时间）
	//
	// ### 🏯 上海景点推荐（基于多云天气）
	// 根据当前上海 **22°C、多云** 的天气，推荐游览：
	// 1. **上海博物馆** — 室内参观，不受天气影响
	// 2. **豫园** — 古典园林，多云天气漫步非常舒适
	// 3. **外滩** — 多云天气适合沿江散步，欣赏万国建筑
	// > ⚠️ 建议携带雨具，以防多云转雨
	//
	// 有任何其他需要帮忙的吗？😊
}

func runToolsInParallelWithMetrics(calls []ToolCallW, mc MetricsCollector, traceID string) ([]ChatMessage, ToolBatchStats) {
	results := make([]ChatMessage, len(calls))
	durations := make([]time.Duration, len(calls))
	mc.ObserveHistogram("tool_calls_per_turn", float64(len(calls)), nil)
	var wg sync.WaitGroup
	batchStart := time.Now()

	for i, call := range calls {
		wg.Add(1)
		go func(idx int, c ToolCallW) {
			defer wg.Done()
			start := time.Now()

			output, retryN, isTimeout, ok := dispatchToolWithRetry(c.Function.Name, c.Function.Arguments)
			durations[idx] = time.Since(start)
			recordToolMetrics(mc, c.Function.Name, start, retryN, isTimeout, ok)

			log.Printf("trace_id=%s tool_call_id=%s tool=%s retry=%d timeout=%t spent=%.2f success=%t",
				traceID, c.ID, c.Function.Name, retryN, isTimeout, time.Since(start).Seconds(), ok)

			results[idx] = ChatMessage{Role: "tool", ToolCallID: c.ID, Content: output}
		}(i, call)
	}
	wg.Wait()

	// 批次墙钟耗时代表真实等待时间，各工具耗时之和代表串行执行时的估算耗时。
	batchDuration := time.Since(batchStart)
	var serialEstimatedDuration time.Duration
	for _, duration := range durations {
		serialEstimatedDuration += duration
	}
	parallelSavedDuration := serialEstimatedDuration - batchDuration
	if parallelSavedDuration < 0 {
		parallelSavedDuration = 0
	}
	speedup := 1.0
	if batchDuration > 0 {
		speedup = float64(serialEstimatedDuration) / float64(batchDuration)
	}
	mc.ObserveHistogram("tool_batch_latency_ms", float64(batchDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_serial_estimated_latency_ms", float64(serialEstimatedDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_parallel_saved_ms", float64(parallelSavedDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_parallel_speedup_ratio", speedup, nil)
	log.Printf("trace_id=%s tool_count=%d batch_ms=%d serial_estimated_ms=%d saved_ms=%d speedup=%.2fx",
		traceID, len(calls), batchDuration.Milliseconds(), serialEstimatedDuration.Milliseconds(), parallelSavedDuration.Milliseconds(), speedup)
	return results, ToolBatchStats{
		ActualDuration:          batchDuration,
		SerialEstimatedDuration: serialEstimatedDuration,
	}
}

// recordToolWorkflowMetrics 汇总所有轮次，量化混合并行与串行编排相对全串行执行的收益。
func recordToolWorkflowMetrics(mc MetricsCollector, traceID string, actualDuration, serialEstimatedDuration time.Duration) {
	savedDuration := serialEstimatedDuration - actualDuration
	if savedDuration < 0 {
		savedDuration = 0
	}
	speedup := 1.0
	if actualDuration > 0 {
		speedup = float64(serialEstimatedDuration) / float64(actualDuration)
	}
	mc.ObserveHistogram("tool_workflow_total_latency_ms", float64(actualDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_workflow_serial_estimated_latency_ms", float64(serialEstimatedDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_workflow_saved_ms", float64(savedDuration.Milliseconds()), nil)
	mc.ObserveHistogram("tool_workflow_speedup_ratio", speedup, nil)
	log.Printf("trace_id=%s workflow_actual_ms=%d workflow_serial_estimated_ms=%d workflow_saved_ms=%d workflow_speedup=%.2fx",
		traceID, actualDuration.Milliseconds(), serialEstimatedDuration.Milliseconds(), savedDuration.Milliseconds(), speedup)
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
	case "plan_attractions":
		var in struct {
			Location string `json:"location"`
			Weather  string `json:"weather"`
		}
		if err := json.Unmarshal([]byte(args), &in); err != nil || strings.TrimSpace(in.Location) == "" || strings.TrimSpace(in.Weather) == "" {
			return "景点规划参数错误：缺少 location 或 weather", false, false
		}
		time.Sleep(200 * time.Millisecond)
		return "上海多云天气适合游览：上海博物馆、豫园、外滩；建议携带雨具。", false, true
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
