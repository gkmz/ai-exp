package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

type RequestBootstrapDemo struct{}

type DeepSeekMessage struct {
	Role             string `json:"role"`
	Content          string `json:"content,omitempty"`
	ReasoningContent string `json:"reasoning_content,omitempty"`
}

type DeepSeekResponse struct {
	Choices []struct {
		Message      DeepSeekMessage `json:"message"`
		FinishReason string          `json:"finish_reason"`
	} `json:"choices"`
	Usage struct {
		PromptTokens         int `json:"prompt_tokens"`
		CompletionTokens     int `json:"completion_tokens"`
		PromptCacheHitTokens int `json:"prompt_cache_hit_tokens"`
	} `json:"usage"`
}

func (d *RequestBootstrapDemo) Run() {
	// 1. 获取API Key
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		panic("You need an apiKey at first.")
	}
	url := "https://api.deepseek.com/chat/completions"

	// 2. 给 HTTP 客户端设置超时，避免调用悬挂
	client := &http.Client{Timeout: 300 * time.Second}

	reqBody := map[string]any{
		"model":  "deepseek-reasoner",
		"messages": []map[string]string{
			{"role": "system", "content": "你是资深 Go 架构师"},
			{"role": "user", "content": "给我一个接口限流方案"},
		},
	}

	// 3. 将请求体转换为JSON格式
	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		fmt.Printf("Error marshaling request body: %v\n", err)
		return
	}
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonBody))
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	// 4. 发送请求
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("请求失败:", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		fmt.Println("请求失败:", resp.Status)
		return
	}

	// 5. 读取响应体
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("读取响应体失败:", err)
		return
	}

	fmt.Println("响应体:", string(respBody))

	var deepseekResponse DeepSeekResponse
	if err := json.Unmarshal(respBody, &deepseekResponse); err != nil {
		fmt.Println("解析失败:", err)
		return
	}
	fmt.Println(deepseekResponse.Choices[0].Message.Content)
}
