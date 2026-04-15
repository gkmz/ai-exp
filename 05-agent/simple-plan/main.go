package main

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	openai "github.com/sashabaranov/go-openai"
)

const (
	defaultBaseURL = "http://127.0.0.1:11434/v1"
	defaultModel   = "qwen2.5:14b-instruct"
)

// readRequirementFromInput 负责读取自然语言需求描述。
// 关键流程：
// 1) 用户用自然语言描述今天的工作（可多行）；
// 2) 输入空行结束；
// 3) 保证描述非空后再进入大模型规划。
func readRequirementFromInput() (string, error) {
	scanner := bufio.NewScanner(os.Stdin)
	lines := make([]string, 0)

	fmt.Println("请自然语言描述你的今天工作安排（可多行，空行结束）：")
	fmt.Println("例如：今天有3个任务，A很重要且17:00前完成，B很紧急，C可以放到下午。")
	for {
		fmt.Print("> ")
		if !scanner.Scan() {
			break
		}

		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			break
		}
		lines = append(lines, line)
	}

	if err := scanner.Err(); err != nil {
		return "", fmt.Errorf("读取输入失败: %w", err)
	}
	if len(lines) == 0 {
		return "", fmt.Errorf("请至少输入一段任务描述")
	}

	return strings.Join(lines, "\n"), nil
}

// buildPrompt 将自然语言描述转换为结构化规划提示词。
// 重点代码：强约束模型输出“时间表 + 优先级判断 + 风险应对”，避免泛泛建议。
func buildPrompt(requirement string) string {
	prompt := `
	你是一个专业的时间管理与任务规划 Agent。
	你的任务是：从用户自然语言描述中识别任务、重要性、紧急性、截止时间，并产出今天可执行的详细日程。
	
	【用户描述】
	%s
	
	【输出要求】
	1) 先输出“任务识别结果”：列出识别出的任务清单，并标注重要/紧急/截止时间（若缺失请合理假设并说明）
	2) 给出“今日总目标”（1句话）
	3) 给出“详细时间计划表”：按时间段输出（如 09:00-10:30），每段包含任务、执行动作、预估时长、预期产出
	4) 给出“优先级排序理由”：说明为什么这样排（重要紧急优先）
	5) 给出“风险与缓冲”：至少2项风险和对应缓冲时间建议
	6) 若用户给了明确截止时间，计划必须满足截止约束；若冲突要明确指出并给替代方案
	7) 全程使用中文，表达具体，不要空话
	
	【输出示例】
	任务识别结果：
	- 需求评审：重要，上午完成
	- 登录接口：紧急，17:00前必须提测
	- 接口测试：不紧急，今天下班前想完成
	
	今日总目标：
	上午完成需求评审，下午实现登录接口，晚上完成接口测试
	
	详细时间计划表：
	09:00-10:30：需求评审
	10:30-12:00：登录接口
	12:00-13:30：接口测试
	
	优先级排序理由：
	重要紧急优先
	
	风险与缓冲：
	- 需求变更：1小时缓冲
	- 接口测试覆盖不全：2小时缓冲
	
	替代方案：
	若需求变更，重新评审需求
	若接口测试覆盖不全，增加测试用例
	
	若用户给了明确截止时间，计划必须满足截止约束；若冲突要明确指出并给替代方案	
	`
	return fmt.Sprintf(prompt, requirement)
}

// newClient 创建 OpenAI 兼容客户端（可对接本地 Ollama / vLLM / LM Studio）。
// 关键流程：通过环境变量切换 baseURL 和 model，避免把配置写死在代码里。
func newClient() (*openai.Client, string) {
	config := openai.DefaultConfig(os.Getenv("OLLAMA_API_KEY"))
	config.BaseURL = defaultBaseURL
	return openai.NewClientWithConfig(config), defaultModel
}

// generatePlan 调用大模型生成任务计划。
// 关键流程：
// 1) 构建 ChatCompletion 请求；
// 2) 设置超时避免一直阻塞；
// 3) 提取首个候选回复作为最终计划。
func generatePlan(client *openai.Client, model string, prompt string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()

	req := openai.ChatCompletionRequest{
		Model: model,
		Messages: []openai.ChatCompletionMessage{
			{
				Role:    openai.ChatMessageRoleSystem,
				Content: "你是经验丰富的项目经理，擅长把工作拆解成可执行任务。",
			},
			{
				Role:    openai.ChatMessageRoleUser,
				Content: prompt,
			},
		},
		Temperature: 0.3,
	}

	resp, err := client.CreateChatCompletion(ctx, req)
	if err != nil {
		return "", fmt.Errorf("调用本地大模型失败: %w", err)
	}
	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("模型没有返回结果")
	}

	return strings.TrimSpace(resp.Choices[0].Message.Content), nil
}

func main() {
	// 主流程步骤 1：采集用户自然语言需求。
	requirement, err := readRequirementFromInput()
	if err != nil {
		fmt.Printf("输入错误: %v\n", err)
		os.Exit(1)
	}

	// 主流程步骤 2：初始化本地 LLM 客户端并构建 prompt。
	client, model := newClient()
	prompt := buildPrompt(requirement)

	fmt.Println()
	fmt.Println("正在生成任务计划，请稍候...")
	fmt.Println()
	fmt.Printf("当前模型: %s\n", model)

	// 主流程步骤 3：调用模型并输出最终计划。
	plan, err := generatePlan(client, model, prompt)
	if err != nil {
		fmt.Printf("生成失败: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("\n===== 任务计划 =====")
	fmt.Println(plan)
}
