package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"

	openai "github.com/sashabaranov/go-openai"
)

func main() {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		log.Fatal("DEEPSEEK_API_KEY 未设置")
	}

	// 静态文件（index.html）
	http.Handle("/", http.FileServer(http.Dir("./static")))

	// SSE 端点：接收 query 参数作为用户提问
	http.HandleFunc("/stream", func(w http.ResponseWriter, r *http.Request) {
		// 设置 SSE 必要响应头
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		// 允许跨域，方便本地开发时前端直接访问
		w.Header().Set("Access-Control-Allow-Origin", "*")

		question := r.URL.Query().Get("q")
		fmt.Println("收到请求: ", question)
		if question == "" {
			question = "用一句话介绍 Go 语言"
		}

		// 初始化 DeepSeek 客户端
		config := openai.DefaultConfig(apiKey)
		config.BaseURL = "https://api.deepseek.com/v1"
		client := openai.NewClientWithConfig(config)

		req := openai.ChatCompletionRequest{
			Model: "deepseek-chat",
			Messages: []openai.ChatCompletionMessage{
				{Role: openai.ChatMessageRoleUser, Content: question},
			},
			Stream: true,
		}

		stream, err := client.CreateChatCompletionStream(r.Context(), req)
		if err != nil {
			// 用 SSE 格式把错误推给客户端
			fmt.Fprintf(w, "event: error\ndata: %s\n\n", err.Error())
			return
		}
		defer stream.Close()

		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "服务器不支持流式响应", http.StatusInternalServerError)
			return
		}

		for {
			chunk, err := stream.Recv()
			if err == io.EOF {
				// 通知客户端流结束
				fmt.Fprintf(w, "data: [DONE]\n\n")
				flusher.Flush()
				break
			}
			if err != nil {
				fmt.Fprintf(w, "event: error\ndata: %s\n\n", err.Error())
				flusher.Flush()
				break
			}

			if len(chunk.Choices) > 0 {
				content := chunk.Choices[0].Delta.Content
				if content == "" {
					continue
				}
				// 把 content 包成 JSON 推送，客户端解析更方便
				payload, _ := json.Marshal(map[string]string{"content": content})
				fmt.Fprintf(w, "data: %s\n\n", payload)
				// 每次写完必须 Flush，否则数据积在缓冲区，流式效果消失
				flusher.Flush()
			}
		}
	})

	log.Println("服务启动：http://localhost:8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
