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

// 定义请求体结构（适配DeepSeek 2026年最新API规范）
type DeepSeekRequest struct {
	Model            string          `json:"model"`                       // 必选，模型参数值
	Temperature      *float64        `json:"temperature,omitempty"`       // 控制随机性，默认0.6
	MaxTokens        *int            `json:"max_tokens,omitempty"`        // 模型单次回答的最大长度（含思维链输出），默认为 32K，最大为 64K。
	TopP             *float64        `json:"top_p,omitempty"`             // 控制聚焦度，默认0.6
	PresencePenalty  *float64        `json:"presence_penalty,omitempty"`  // 存在惩罚，控制重复率
	FrequencyPenalty *float64        `json:"frequency_penalty,omitempty"` // 频率惩罚，控制重复率
	ResponseFormat   *ResponseFormat `json:"response_format,omitempty"`   // 输出格式
	Messages         []Message       `json:"messages"`
}

type ResponseFormat struct {
	Type string `json:"type"`
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// 定义响应体结构
type DeepSeekResponse struct {
	Id                string   `json:"id"`
	Object            string   `json:"object"`
	Created           int64    `json:"created"`
	Model             string   `json:"model"`
	Choices           []Choice `json:"choices"`
	Usage             Usage    `json:"usage"`
	SystemFingerPrint string   `json:"system_finger_print"`
}

type Choice struct {
	Index   int         `json:"index"`
	Message RespMessage `json:"message"`
}

type RespMessage struct {
	Role         string `json:"role"`
	Content      string `json:"content"`
	LogProbs     any    `json:"logprobs"`
	FinishReason string `json:"finish_reason"`
}

type Usage struct {
	PromptTokens           int                `json:"prompt_tokens"`
	CompletionTokens       int                `json:"completion_tokens"`
	TotalTokens            int                `json:"total_tokens"`
	PromptTokenDetails     PromptTokenDetails `json:"prompt_token_details"`
	PromptCacheHitTokens   int                `json:"prompt_cache_hit_tokens"`
	PrommptCacheMissTokens int                `json:"prompt_cache_miss_tokens"`
}

type PromptTokenDetails struct {
	CachedTokens int `json:"cached_tokens"`
}

func ptr[T ~float64 | ~int | ~string](r T) *T { return &r }

func main() {
	// 1. 配置核心参数（适配deepseek-v3.2模型，2026最新设置）
	requestBody := DeepSeekRequest{
		Model:            "deepseek-chat", // 选择2026年主推模型
		Temperature:      ptr(0.4),        // 技术文档生成，低随机性
		MaxTokens:        ptr(1024),       // 输出长度限制，结合上下文窗口设置
		TopP:             ptr(0.85),       // 聚焦核心内容
		PresencePenalty:  ptr(0.7),        // 避免重复内容
		FrequencyPenalty: ptr(0.9),        // 避免重复句式
		Messages: []Message{
			{Role: "system", Content: ""},
			{Role: "user", Content: "生成一篇Go语言调用DeepSeek大模型的技术文档，重点讲解核心参数配置"},
		},
		// ResponseFormat: ResponseFormat{Type: "json_object"},
	}

	// 2. 转换请求体为JSON格式
	jsonBody, err := json.Marshal(requestBody)
	if err != nil {
		fmt.Printf("请求体转换失败：%v\n", err)
		return
	}

	fmt.Println("request:", string(jsonBody))

	// 3. 发送POST请求（DeepSeek 2026年最新base_url）
	apiKey := os.Getenv("DEEPSEEK_API_KEY")           // 从环境变量获取API Key，避免硬编码
	client := &http.Client{Timeout: 30 * time.Second} // 设置超时时间，避免卡死
	req, err := http.NewRequest("POST", "https://api.deepseek.com/v1/chat/completions", bytes.NewBuffer(jsonBody))
	if err != nil {
		fmt.Printf("请求创建失败：%v\n", err)
		return
	}

	// 4. 设置请求头（适配DeepSeek官方规范）
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", apiKey))

	// 5. 发送请求并解析响应
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("请求发送失败：%v\n", err)
		return
	}
	defer resp.Body.Close()

	bs, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Println(err)
		return
	}
	os.WriteFile("output.json", bs, os.ModePerm)

	// 6. 解析响应结果
	r := bytes.NewReader(bs)
	var response DeepSeekResponse
	if err := json.NewDecoder(r).Decode(&response); err != nil {
		fmt.Printf("响应解析失败：%v\n", err)
		return
	}

	// 7. 处理响应结果
	// 输出结果和Token消耗（结合上一篇Token知识，控制成本）
	fmt.Printf("模型响应：\n%s\n", response.Choices[0].Message.Content)
	fmt.Printf("\nToken消耗：输入%d个，输出%d个，总%d个\n",
		response.Usage.PromptTokens,
		response.Usage.CompletionTokens,
		response.Usage.TotalTokens)
}
