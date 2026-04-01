package main

import (
	"fmt"
	"regexp"
)

// 计算Token数量（适配DeepSeek切割规则）
func countTokens(text string) int {
	if text == "" {
		return 0
	}

	// 1. 处理中文：单个汉字、中文标点算1个Token
	chineseRegex := regexp.MustCompile(`[\p{Han}，。！？；：""''（）【】《》、·…—]`)
	chineseCount := len(chineseRegex.FindAllString(text, -1))

	// 2. 处理英文：按单词/子单词切割，英文标点、空格单独算1个Token
	// 先提取英文单词（含字母、数字、下划线、连字符）
	englishWordRegex := regexp.MustCompile(`[a-zA-Z0-9_]+(?:-[a-zA-Z0-9_]+)*`)
	englishWords := englishWordRegex.FindAllString(text, -1)
	englishWordCount := len(englishWords)

	// 3. 处理英文标点和空格（排除已统计的中文标点）
	// 匹配英文标点和空格，排除中文标点
	punctuationSpaceRegex := regexp.MustCompile(`[!"#$%&'()*+,-./:;<=>?@\[\]^_` + "`" + `{|}~\\\s]`)
	punctuationSpaceCount := len(punctuationSpaceRegex.FindAllString(text, -1))

	// 总Token数 = 中文数 + 英文单词数 + 英文标点/空格数
	totalTokens := chineseCount + englishWordCount + punctuationSpaceCount
	return totalTokens
}

// 估算DeepSeek API调用成本（单位：元）
// model: 模型名称（deepseek-coder-v2 / deepseek-chat）
// inputTokens: 输入Token数
// outputTokens: 预估输出Token数
func calculateCost(model string, inputTokens, outputTokens int) float64 {
	var inputPrice, outputPrice float64

	// 按DeepSeek官方定价设置单价（元/1000个Token）
	switch model {
	case "deepseek-coder-v2":
		inputPrice = 0.001
		outputPrice = 0.002
	case "deepseek-chat":
		inputPrice = 0.0005
		outputPrice = 0.001
	default:
		fmt.Println("模型不支持，默认使用deepseek-chat定价")
		inputPrice = 0.0005
		outputPrice = 0.001
	}

	// 计算总成本
	inputCost := float64(inputTokens) * inputPrice / 1000
	outputCost := float64(outputTokens) * outputPrice / 1000
	totalCost := inputCost + outputCost
	return totalCost
}

func main() {
	// 实操测试：输入一段文本，计算Token数并估算成本
	testText := "开发者使用DeepSeek API生成Go语言HTTP请求代码，要求简洁可运行。"
	tokens := countTokens(testText)
	fmt.Printf("输入文本：%s\n", testText)
	fmt.Printf("DeepSeek Token数：%d\n", tokens)

	// 估算调用成本（以deepseek-coder-v2为例，预估输出Token数为100）
	cost := calculateCost("deepseek-coder-v2", tokens, 100)
	fmt.Printf("预估API调用成本：%.6f元\n", cost)
}
