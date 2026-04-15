package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strconv" // 用于解析参数输入
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	openai "github.com/sashabaranov/go-openai" // 导入 go-openai 包
)

// Model 是 TUI 应用的主模型
type Model struct {
	textInput  string // 用户输入的提示
	llmOutput  string // LLM 的输出结果
	parameters LLMParameters // LLM 调用参数
	quitting   bool // 是否正在退出

	client *openai.Client // DeepSeek API 客户端
}

// LLMParameters 存储 LLM 的调用参数
type LLMParameters struct {
	Temperature float32
	TopP        float32
	MaxTokens   int
}

// Msg 消息类型用于在 goroutine 中传递 API 响应
type errMsg error
type llmResponseMsg string

// Init 实现 bubbletea.Model 接口的 Init 方法
func (m *Model) Init() tea.Cmd {
	// 初始化 DeepSeek API 客户端
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		return tea.Tick(0, func(t time.Time) tea.Msg {
			return errMsg(fmt.Errorf("请设置 DEEPSEEK_API_KEY 环境变量"))
		})
	}
	config := openai.DefaultConfig(apiKey);
	config.BaseURL = "https://api.deepseek.com/v1"
	m.client = openai.NewClientWithConfig(config) // DeepSeek API Base URL
	return nil
}

// makeDeepSeekRequest 执行 DeepSeek API 调用
func (m *Model) makeDeepSeekRequest(prompt string) tea.Cmd {
	return func() tea.Msg {
		if m.client == nil {
			return errMsg(fmt.Errorf("API 客户端未初始化"))
		}

			reqBody := openai.ChatCompletionRequest{
				Model:       "deepseek-chat", // 使用 DeepSeek 的聊天模型
				Temperature: m.parameters.Temperature,
				TopP:        m.parameters.TopP,
				MaxTokens:   m.parameters.MaxTokens,
				Messages: []openai.ChatCompletionMessage{
					{
						Role:    openai.ChatMessageRoleUser,
						Content: prompt,
					},
				},
			}

		fmt.Printf("DeepSeek API Request: %+v\n", reqBody)

		resp, err := m.client.CreateChatCompletion(
			context.Background(),
			reqBody,
		)
		if err != nil {
			return errMsg(err)
		}

		if len(resp.Choices) > 0 {
			return llmResponseMsg(resp.Choices[0].Message.Content)
		}
		return errMsg(fmt.Errorf("未收到 LLM 响应"))
	}
}

// Update 实现 bubbletea.Model 接口的 Update 方法
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			m.quitting = true
			return m, tea.Quit
		case "enter":
			if m.textInput == "" {
				m.llmOutput = "请输入提示！"
				return m, nil
			}
			m.llmOutput = "正在生成响应..."
			return m, m.makeDeepSeekRequest(m.textInput)
		case "up": // 调整 Temperature
			m.parameters.Temperature += 0.1
			if m.parameters.Temperature > 2.0 {
				m.parameters.Temperature = 2.0
			}
		case "down": // 调整 Temperature
			m.parameters.Temperature -= 0.1
			if m.parameters.Temperature < 0.0 {
				m.parameters.Temperature = 0.0
			}
		case "left": // 调整 TopP
			m.parameters.TopP -= 0.1
			if m.parameters.TopP < 0.0 {
				m.parameters.TopP = 0.0
			}
		case "right": // 调整 TopP
			m.parameters.TopP += 0.1
			if m.parameters.TopP > 1.0 {
				m.parameters.TopP = 1.0
			}
		case "p": // 增加 MaxTokens
			m.parameters.MaxTokens += 10
		case "o": // 减少 MaxTokens
			if m.parameters.MaxTokens > 10 {
				m.parameters.MaxTokens -= 10
			}
		case "backspace":
			if len(m.textInput) > 0 {
				m.textInput = m.textInput[:len(m.textInput)-1]
			}
		default:
			// 尝试解析数字输入来设置 MaxTokens，这里仅作简单示例，实际应用需要更健壮的解析
			if _, err := strconv.Atoi(msg.String()); err == nil {
				m.textInput += msg.String() // 继续允许数字输入到文本框
			} else if msg.Type == tea.KeyRunes {
				m.textInput += msg.String()
			}
		}

	case llmResponseMsg:
		m.llmOutput = string(msg)
	case errMsg:
		m.llmOutput = fmt.Sprintf("错误: %v", msg)
	}
	return m, nil
}

// View 实现 bubbletea.Model 接口的 View 方法
func (m *Model) View() string {
	s := "输入您的提示 (按 Enter 发送, Ctrl+C 或 q 退出):\n" +
		"  (↑/↓ 调整温度, ←/→ 调整 TopP, p/o 调整 MaxTokens)\n\n" +
		lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(1).Render(m.textInput) + "\n\n" +
		"LLM 参数:\n" +
		fmt.Sprintf("  温度: %.1f\n", m.parameters.Temperature) +
		fmt.Sprintf("  Top P: %.1f\n", m.parameters.TopP) +
		fmt.Sprintf("  最大令牌: %d\n\n", m.parameters.MaxTokens) +
		"LLM 输出:\n" +
		lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(1).Width(80).Height(10).Render(m.llmOutput)

	if m.quitting {
		s += "\n再见！\n"
	}
	return s
}

func main() {
	m := &Model{
		parameters: LLMParameters{
			Temperature: 0.7,
			TopP:        0.9,
			MaxTokens:   500,
		},
	}
	m.Init()
	p := tea.NewProgram(m)
	if _, err := p.Run(); err != nil {
		log.Fatal(err)
	}
}
