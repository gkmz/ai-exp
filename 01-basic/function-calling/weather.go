package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	openai "github.com/sashabaranov/go-openai"
)

type WeatherArgs struct {
	City string `json:"city"`
	Date string `json:"date"`
}

func getWeather(city, date string) string {
	// 演示用：真实项目里这里可以改成调用天气 API
	if city == "上海" && date == "明天" {
		return `{"city":"上海","date":"明天","weather":"多云转小雨","temp":"18~24C"}`
	}
	return fmt.Sprintf(`{"city":"%s","date":"%s","weather":"晴","temp":"20~28C"}`, city, date)
}

func runWeatherDemo() {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	baseURL := "https://api.deepseek.com/v1"
	if apiKey == "" {
		log.Fatal("请先设置 DEEPSEEK_API_KEY")
	}

	cfg := openai.DefaultConfig(apiKey)
	cfg.BaseURL = baseURL
	client := openai.NewClientWithConfig(cfg)

	// 定义工具函数
	tools := []openai.Tool{
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "get_weather",
				Description: "查询城市某天的天气",
				Parameters: json.RawMessage(`{
					"type":"object",
					"properties":{
						"city":{"type":"string","description":"城市名"},
						"date":{"type":"string","description":"日期，如今天/明天"}
					},
					"required":["city","date"]
				}`),
			},
		},
	}

	msgs := []openai.ChatCompletionMessage{
		{Role: openai.ChatMessageRoleSystem, Content: "你是一个天气助手，需要时必须调用工具。"},
		{Role: openai.ChatMessageRoleUser, Content: "帮我查一下上海明天的天气，然后给出穿衣建议。"},
	}

	// 第一次调用，模型会根据工具函数生成 tool_calls 消息
	firstResp, err := client.CreateChatCompletion(context.Background(), openai.ChatCompletionRequest{
		Model:      "deepseek-chat",
		Messages:   msgs,
		Tools:      tools, // 传入工具函数
		ToolChoice: "auto",
	})
	if err != nil {
		log.Fatalf("first completion error: %v", err)
	}

	if len(firstResp.Choices) == 0 {
		log.Fatal("模型没有返回 choices")
	}

	fmt.Printf("firstResp: %+v\n", firstResp.Choices[0].Message)

	assistantMsg := firstResp.Choices[0].Message
	msgs = append(msgs, assistantMsg) // 关键：把模型的 tool_calls 消息放回上下文

	// 处理工具函数调用
	for _, tc := range assistantMsg.ToolCalls {
		if tc.Function.Name != "get_weather" {
			continue
		}

		var args WeatherArgs
		if err := json.Unmarshal([]byte(tc.Function.Arguments), &args); err != nil {
			log.Fatalf("arguments parse error: %v", err)
		}

		// 关键步骤：服务端二次校验（示例里最少要校验非空）
		if args.City == "" || args.Date == "" {
			log.Fatal("工具参数缺失：city/date 不能为空")
		}

		// 调用工具函数获取天气信息
		fmt.Printf("调用工具函数获取天气信息: %+v\n", args)
		toolResult := getWeather(args.City, args.Date)
		msgs = append(msgs, openai.ChatCompletionMessage{
			Role:       openai.ChatMessageRoleTool,
			ToolCallID: tc.ID, // 关键：必须回填对应的 tool_call_id
			Name:       tc.Function.Name,
			Content:    toolResult,
		})
	}

	// 第二次调用，带上工具调用的结果
	finalResp, err := client.CreateChatCompletion(context.Background(), openai.ChatCompletionRequest{
		Model:    "deepseek-chat",
		Messages: msgs,
	})
	if err != nil {
		log.Fatalf("final completion error: %v", err)
	}

	fmt.Println("最终回答：")
	fmt.Println(finalResp.Choices[0].Message.Content)
}
