package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
)

// ChatHistoryDemo 封装聊天历史功能
type ChatHistoryDemo struct{}

// Message 请求和响应消息结构
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// chatRequest API 请求结构
type chatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
}

// chatResponse API 响应结构
type chatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

const (
	apiURL     = "https://api.deepseek.com/v1/chat/completions" // 或其他代理地址
	maxHistory = 10                                             // 最大保留历史轮数
)

// Run 运行聊天历史演示
func (d *ChatHistoryDemo) Run() {
	// 1. 初始化对话历史，加入 System Prompt
	history := []Message{
		{Role: "system", Content: "你是一个专业的编程助手，请用简洁明了的语言回答问题。"},
	}

	scanner := bufio.NewScanner(os.Stdin)
	fmt.Println(">>> 欢迎来到 AI 聊天室 (输入 'exit' 退出) <<<")

	for {
		fmt.Print("\nUser: ")
		if !scanner.Scan() {
			break
		}
		input := scanner.Text()

		if strings.ToLower(input) == "exit" {
			break
		}

		// 2. 将用户消息追加到历史中
		history = append(history, Message{Role: "user", Content: input})

		// 3. 控制历史长度：如果超过限制，删除最早的对话（保留 system）
		if len(history) > maxHistory {
			fmt.Println("对话太长了，取最后10轮")
			history = append(history[:1], history[len(history)-maxHistory+1:]...)
		}

		// 4. 发起 API 请求
		respMsg, err := fetchAIResponse(history)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			continue
		}

		// 5. 显示结果并存入历史
		fmt.Printf("\nAI: %s\n", respMsg.Content)
		history = append(history, respMsg)
	}
}

func fetchAIResponse(messages []Message) (Message, error) {
	reqBody := chatRequest{
		Model:    "deepseek-chat",
		Messages: messages,
	}

	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	jsonData, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", apiURL, bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return Message{}, err
	}
	defer resp.Body.Close()

	var result chatResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return Message{}, err
	}

	if len(result.Choices) > 0 {
		return result.Choices[0].Message, nil
	}
	return Message{}, fmt.Errorf("empty response")
}
