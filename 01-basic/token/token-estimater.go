package main

import (
	"fmt"
	"log"

	tiktoken "github.com/pkoukk/tiktoken-go"
)

type TokenEstimater struct{}

// DeepSeek 使用与 cl100k_base 接近的词表
const encodingName = "cl100k_base"

// DeepSeek API 定价（美元 / 1M tokens，缓存未命中，2026-04）
type ModelPricing struct {
	InputPerM  float64
	OutputPerM float64
}

// 模型价格定义
var pricing = map[string]ModelPricing{
	"deepseek-chat":     {InputPerM: 0.27, OutputPerM: 1.10},
	"deepseek-reasoner": {InputPerM: 0.55, OutputPerM: 2.19},
}

// CountTokens 返回文本的精准 token 数
func (te *TokenEstimater) CountTokens(text string) (int, error) {
	enc, err := tiktoken.GetEncoding(encodingName)
	if err != nil {
		return 0, fmt.Errorf("加载 tokenizer 失败: %w", err)
	}
	return len(enc.Encode(text, nil, nil)), nil
}

// EstimateCost 估算 API 调用成本（美元）
func (te *TokenEstimater) EstimateCost(model string, inputTokens, outputTokens int) (float64, error) {
	p, ok := pricing[model]
	if !ok {
		return 0, fmt.Errorf("未知模型: %s", model)
	}
	cost := float64(inputTokens)/1_000_000*p.InputPerM +
		float64(outputTokens)/1_000_000*p.OutputPerM
	return cost, nil
}

// CheckContextLimit 检查是否超出窗口限制
func (te *TokenEstimater) CheckContextLimit(inputTokens int, maxInput int) (ok bool, overBy int) {
	if inputTokens > maxInput {
		return false, inputTokens - maxInput
	}
	return true, 0
}

func (te *TokenEstimater) run(text string) {
	enc, err := tiktoken.GetEncoding(encodingName)
	if err != nil {
		log.Fatal(err)
	}

	tokens := enc.Encode(text, nil, nil)
	fmt.Printf("文本: %q\n", text)
	fmt.Printf("Token 数: %d | Token 列表: %v\n\n", len(tokens), tokens)
}

func (te *TokenEstimater) runCostDemo() {
	// 成本估算示例
	fmt.Println("成本估算（deepseek-chat，缓存未命中）:")
	inputTokens := 500
	outputTokens := 800
	cost, _ := te.EstimateCost("deepseek-chat", inputTokens, outputTokens)
	fmt.Printf("输入 %d tokens + 输出 %d tokens\n", inputTokens, outputTokens)
	fmt.Printf("单次成本：$%.6f（约 %.4f 元）\n", cost, cost*7.2)
	fmt.Printf("日调用 10,000 次：约 %.1f 元\n", cost*7.2*10000)

	// 窗口检查
	fmt.Println("上下文窗口检查:")
	const deepseekChatMaxInput = 64000
	testInputs := []int{30000, 64001, 50000}
	for _, n := range testInputs {
		ok, over := te.CheckContextLimit(n, deepseekChatMaxInput)
		if ok {
			fmt.Printf("输入 %d tokens：✅ 在窗口内，可用输出空间约 %d tokens\n",
				n, te.calcMaxTokens(n))
		} else {
			fmt.Printf("输入 %d tokens：❌ 超出限制 %d tokens，需要截断\n", n, over)
		}
	}
}

func (te *TokenEstimater) calcMaxTokens(inputTokens int) int {
	const (
		maxInput  = 64000
		maxOutput = 8000
	)
	remaining := int(float64(maxInput)*0.7) - inputTokens
	if remaining <= 0 {
		return 0
	}
	if remaining > maxOutput {
		return maxOutput
	}
	return remaining
}
