package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	openai "github.com/sashabaranov/go-openai"
)

// RequestDemo 封装请求功能
type RequestDemo struct{}

type customChatCompletionResponse struct {
	openai.ChatCompletionResponse
	Choices []struct {
		openai.ChatCompletionChoice
		Message struct {
			openai.ChatCompletionMessage
			ReasoningContent string `json:"reasoning_content"` // 扩展字段
		} `json:"message"`
	} `json:"choices"`
}

// Run 运行请求演示
func (d *RequestDemo) Run() {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		panic("You need an apiKey at first.")
	}
	url := "https://api.deepseek.com/chat/completions"

	body := map[string]any{
		"model": "deepseek-chat",
		"messages": []map[string]string{
			{"role": "user", "content": "用一句话介绍Go语言"},
		},
	}

	jsonBody, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("请求失败:", err)
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	var customChatCompletionResponse customChatCompletionResponse
	if err := json.Unmarshal(respBody, &customChatCompletionResponse); err != nil {
		fmt.Println("解析失败:", err)
		return
	}
	fmt.Println(customChatCompletionResponse.Choices[0].Message.ChatCompletionMessage)
}
