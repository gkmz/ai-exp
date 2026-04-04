package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	openai "github.com/sashabaranov/go-openai"
)

func main() {
	streamingWithoutSDK()
	// streamingWithSDK()
}

type StreamChunk struct {
	Choices []struct {
		Delta struct {
			Content string `json:"content"`
		} `json:"delta"`
		FinishReason *string `json:"finish_reason"`
	} `json:"choices"`
}

func streamingWithoutSDK() {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	body := `{
		"model": "deepseek-chat",
		"stream": true,
		"messages": [{"role": "user", "content": "用三句话解释什么是量子纠缠，要让高中生能听懂。"}]
	}`

	req, _ := http.NewRequest("POST",
		"https://api.deepseek.com/v1/chat/completions",
		bytes.NewBufferString(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	fmt.Print("AI: ")

	for scanner.Scan() {
		line := scanner.Text()
		// fmt.Println(line)

		// SSE 格式：每行以 "data: " 开头
		if !strings.HasPrefix(line, "data: ") {
			continue
		}

		data := strings.TrimPrefix(line, "data: ")

		// 流结束标记
		if data == "[DONE]" {
			fmt.Println()
			break
		}

		// 每一次服务端发过来的内容
		var chunk StreamChunk
		if err := json.Unmarshal([]byte(data), &chunk); err != nil {
			continue
		}

		if len(chunk.Choices) > 0 {
			fmt.Print(chunk.Choices[0].Delta.Content)
		}
	}
}

func streamingWithSDK() {
	// DeepSeek 使用 OpenAI 兼容接口，只需要替换 BaseURL
	config := openai.DefaultConfig(os.Getenv("DEEPSEEK_API_KEY"))
	config.BaseURL = "https://api.deepseek.com/v1"

	client := openai.NewClientWithConfig(config)

	req := openai.ChatCompletionRequest{
		Model: "deepseek-chat",
		Messages: []openai.ChatCompletionMessage{
			{
				Role:    openai.ChatMessageRoleUser,
				Content: "用三句话解释什么是量子纠缠，要让高中生能听懂。",
			},
		},
		Stream: true, // 关键：开启流式模式
	}

	// 创建一个额流式输出对象
	stream, err := client.CreateChatCompletionStream(context.Background(), req)
	if err != nil {
		fmt.Printf("创建流失败: %v\n", err)
		return
	}
	defer stream.Close()

	fmt.Print("AI: ")

	for {
		// 接收流式输出消息
		chunk, err := stream.Recv()
		if err == io.EOF {
			// [DONE] 信号，流结束
			// fmt.Println("消息结束")
			break
		}
		if err != nil {
			fmt.Printf("\n接收出错: %v\n", err)
			break
		}

		// 每个 chunk 里可能包含多个 choices，取第一个的 delta 内容
		if len(chunk.Choices) > 0 {
			// fmt.Println("choises:", len(chunk.Choices))
			content := chunk.Choices[0].Delta.Content
			fmt.Print(content) // 不换行，实时打印，打字机效果
		}
	}
}
