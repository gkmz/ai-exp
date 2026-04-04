package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strings"
)

func main() {
	question := "用三句话解释什么是量子纠缠，要让高中生能听懂。"
	if len(os.Args) > 1 {
		question = strings.Join(os.Args[1:], " ")
	}

	endpoint := "http://localhost:8080/stream?q=" + url.QueryEscape(question)
	resp, err := http.Get(endpoint)
	if err != nil {
		fmt.Fprintf(os.Stderr, "连接服务端失败: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	fmt.Print("AI: ")

	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()

		// SSE 格式：只处理 data: 开头的行，忽略注释和空行
		if !strings.HasPrefix(line, "data: ") {
			continue
		}

		data := strings.TrimPrefix(line, "data: ")

		// sse结束
		if data == "[DONE]" {
			fmt.Println()
			break
		}

		// 服务端推的是 JSON，解析出 content 字段
		var payload struct {
			Content string `json:"content"`
		}
		if err := json.Unmarshal([]byte(data), &payload); err != nil {
			continue
		}

		fmt.Print(payload.Content)
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "\n读取出错: %v\n", err)
	}
}
