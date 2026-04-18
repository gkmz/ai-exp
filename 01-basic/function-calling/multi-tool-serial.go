package main

import (
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

// runMultiToolSeriallyDemo 演示串行工具编排：
// 每一轮只根据当前上下文让模型决策下一步，拿到工具结果后再进入下一轮。
func runMultiToolSeriallyDemo() {
	// 关键步骤1：读取配置并初始化指标
	apiKey := strings.TrimSpace(os.Getenv("DEEPSEEK_API_KEY"))
	if apiKey == "" {
		log.Fatal("请先设置 DEEPSEEK_API_KEY")
	}
	baseURL := "https://api.deepseek.com/v1"
	model := "deepseek-chat"
	traceID := strconv.FormatInt(time.Now().UnixNano(), 10)
	mc := NewInMemoryMetrics()

	// 关键步骤2：沿用并行示例中的工具定义，不重复声明协议对象和公共方法
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

	messages := []ChatMessage{
		{Role: "system", Content: "你是工具调用助手。对于有依赖关系的任务，必须串行决策与执行。"},
		{Role: "user", Content: "先查上海天气，再根据结果决定是否还要查纽约天气，最后告诉我纽约现在几点。"},
	}

	// 关键步骤3：串行循环。每拿到一次工具结果，都回填给模型再做下一步决策。
	const maxTurns = 8
	for turn := 1; turn <= maxTurns; turn++ {
		roundStart := time.Now()
		resp, err := createChatCompletion(baseURL, apiKey, chatCompletionReq{
			Model:       model,
			Messages:    messages,
			Tools:       tools,
			ToolChoice:  "auto",
			Temperature: 0.2,
		})
		if err != nil || len(resp.Choices) == 0 {
			mc.IncCounter("final_answer_error_total", nil)
			log.Fatalf("第 %d 轮调用失败: %v", turn, err)
		}
		mc.ObserveHistogram("final_answer_latency_ms", float64(time.Since(roundStart).Milliseconds()), map[string]string{"turn": strconv.Itoa(turn)})

		assistantMsg := resp.Choices[0].Message
		messages = append(messages, ChatMessage{
			Role:      "assistant",
			Content:   assistantMsg.Content,
			ToolCalls: assistantMsg.ToolCalls,
		})

		log.Printf("turn=%d assistantMsg: %+v\n", turn, assistantMsg)

		// 关键步骤4：没有工具调用则说明模型给出了最终答案，串行流程结束。
		if len(assistantMsg.ToolCalls) == 0 {
			fmt.Println("----- 最终回答 -----")
			fmt.Println(assistantMsg.Content)
			return
		}

		// 关键步骤5：同一轮内按顺序逐个执行工具，不并发；执行结果按顺序回填消息。
		mc.ObserveHistogram("tool_calls_per_turn", float64(len(assistantMsg.ToolCalls)), map[string]string{"turn": strconv.Itoa(turn)})
		for _, call := range assistantMsg.ToolCalls {
			start := time.Now()
			output, retryN, isTimeout, ok := dispatchToolWithRetry(call.Function.Name, call.Function.Arguments)
			recordToolMetrics(mc, call.Function.Name, start, retryN, isTimeout, ok)

			log.Printf("trace_id=%s turn=%d tool_call_id=%s tool=%s retry=%d timeout=%t spent=%.2f success=%t",
				traceID, turn, call.ID, call.Function.Name, retryN, isTimeout, time.Since(start).Seconds(), ok)

			messages = append(messages, ChatMessage{Role: "tool", ToolCallID: call.ID, Content: output})
		}

		if shouldDegrade(mc) {
			log.Println("触发降级：保持串行并优先走缓存/短路策略")
		}
	}

	log.Fatalf("超过最大轮次 %d，疑似陷入循环", maxTurns)
}
