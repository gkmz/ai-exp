package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"strings"
	"time"

	openai "github.com/sashabaranov/go-openai"
)

type Weather struct {
	Condition   string
	Temperature string
	Rainy       bool
}

type Hotel struct {
	Name           string
	DistanceToCore float64
	PricePerNight  int
	AvailableRooms int
}

type Attraction struct {
	Name        string
	Indoor      bool
	StayHours   float64
	CrowdLevel  string
	CrowdScore  int
	Description string
}

type ToolCallRecord struct {
	ToolName string
	Input    string
	Output   string
}

type ToolRuntime struct {
	Destination string
	Weather     Weather
	Hotels      []Hotel
	Attractions []Attraction
	Distances   map[string]map[string]float64
}

const (
	defaultDestination = "成都"
	defaultBaseURL     = "http://127.0.0.1:11434/v1"
	defaultModel       = "qwen2.5:7b-instruct"
)

// 景点基础信息（成都热门景点）。不依赖外部 API，全部本地模拟。
var attractionBase = []Attraction{
	{Name: "武侯祠", Indoor: false, StayHours: 2.0, Description: "三国文化地标，适合历史文化参观"},
	{Name: "锦里古街", Indoor: false, StayHours: 1.5, Description: "成都传统商业街，适合美食与夜景"},
	{Name: "宽窄巷子", Indoor: false, StayHours: 2.0, Description: "城市慢生活代表景点，拍照和体验茶馆文化"},
	{Name: "杜甫草堂", Indoor: false, StayHours: 2.0, Description: "诗歌文化景点，环境安静"},
	{Name: "三星堆博物馆", Indoor: true, StayHours: 3.0, Description: "重磅室内博物馆，雨天优先"},
	{Name: "成都博物馆", Indoor: true, StayHours: 2.5, Description: "市区室内展馆，交通便利"},
	{Name: "四川科技馆", Indoor: true, StayHours: 2.0, Description: "互动展项较多，适合全天候"},
	{Name: "熊猫基地", Indoor: false, StayHours: 3.0, Description: "成都必去景点，通常上午更适合"},
}

// 距离矩阵（单位：公里），用于输出更精确的时间规划。
// 重点：这里用常见出行关系做近似模拟，目标是测试 agent 的规划能力。
var distanceKM = map[string]map[string]float64{
	"武侯祠": {
		"锦里古街":   0.4,
		"宽窄巷子":   3.5,
		"杜甫草堂":   4.8,
		"三星堆博物馆": 43.0,
		"成都博物馆":  3.8,
		"四川科技馆":  4.1,
		"熊猫基地":   18.0,
	},
	"锦里古街": {
		"武侯祠":    0.4,
		"宽窄巷子":   3.3,
		"杜甫草堂":   4.6,
		"三星堆博物馆": 42.7,
		"成都博物馆":  3.5,
		"四川科技馆":  3.9,
		"熊猫基地":   17.8,
	},
	"宽窄巷子": {
		"武侯祠":    3.5,
		"锦里古街":   3.3,
		"杜甫草堂":   2.8,
		"三星堆博物馆": 40.5,
		"成都博物馆":  1.6,
		"四川科技馆":  1.9,
		"熊猫基地":   16.2,
	},
	"杜甫草堂": {
		"武侯祠":    4.8,
		"锦里古街":   4.6,
		"宽窄巷子":   2.8,
		"三星堆博物馆": 38.9,
		"成都博物馆":  3.9,
		"四川科技馆":  4.1,
		"熊猫基地":   17.1,
	},
	"三星堆博物馆": {
		"武侯祠":   43.0,
		"锦里古街":  42.7,
		"宽窄巷子":  40.5,
		"杜甫草堂":  38.9,
		"成都博物馆": 40.1,
		"四川科技馆": 40.3,
		"熊猫基地":  27.0,
	},
	"成都博物馆": {
		"武侯祠":    3.8,
		"锦里古街":   3.5,
		"宽窄巷子":   1.6,
		"杜甫草堂":   3.9,
		"三星堆博物馆": 40.1,
		"四川科技馆":  0.9,
		"熊猫基地":   15.5,
	},
	"四川科技馆": {
		"武侯祠":    4.1,
		"锦里古街":   3.9,
		"宽窄巷子":   1.9,
		"杜甫草堂":   4.1,
		"三星堆博物馆": 40.3,
		"成都博物馆":  0.9,
		"熊猫基地":   15.7,
	},
	"熊猫基地": {
		"武侯祠":   18.0,
		"锦里古街":  17.8,
		"宽窄巷子":  16.2,
		"杜甫草堂":  17.1,
		"三星堆博物馆": 27.0,
		"成都博物馆": 15.5,
		"四川科技馆": 15.7,
	},
}

func main() {
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	destination := defaultDestination

	fmt.Printf("===== Travel Planning Agent Demo（%s）=====\n\n", destination)

	// 关键流程：先构造本地模拟数据源，再把函数“注册为工具”给大模型调用。
	runtime := newToolRuntime(destination, rng)
	toolCalls := make([]ToolCallRecord, 0, 8)

	client, model := newClient()
	finalPlan, err := runAgentWithToolCalling(client, model, runtime, &toolCalls)
	if err != nil {
		// 异常兜底：若本地模型不可用，仍输出可读结果，保证闭环可运行。
		selectedHotel, hotelNote := pickHotel(runtime.Hotels, rng)
		warnings := collectWarnings(runtime.Weather, runtime.Hotels, runtime.Attractions, selectedHotel)
		finalPlan = buildFallbackPlan(destination, runtime.Weather, selectedHotel, hotelNote, runtime.Attractions, warnings)
	}

	printToolCalls(toolCalls)
	printWeather(runtime.Weather)
	selectedHotel, hotelNote := pickHotel(runtime.Hotels, rng)
	printHotelResult(runtime.Hotels, selectedHotel, hotelNote)
	printAttractionSnapshot(runtime.Attractions)
	printWarnings(collectWarnings(runtime.Weather, runtime.Hotels, runtime.Attractions, selectedHotel))
	printLLMPlan(model, finalPlan, err)
}

// newToolRuntime 构造本地模拟数据，供工具函数读取。
func newToolRuntime(destination string, rng *rand.Rand) *ToolRuntime {
	return &ToolRuntime{
		Destination: destination,
		Weather:     mockWeather(rng),
		Hotels:      mockHotels(rng),
		Attractions: mockAttractionsWithCrowd(rng),
		Distances:   distanceKM,
	}
}

// runAgentWithToolCalling 让大模型自主决定是否调用工具及调用顺序。
// 关键流程：
// 1) 注册工具定义（weather/hotel/attraction/distance）；
// 2) 发送用户目标给大模型；
// 3) 若模型返回 tool_calls，则执行本地函数并回填 tool 消息；
// 4) 直到模型返回最终规划文本。
func runAgentWithToolCalling(client *openai.Client, model string, runtime *ToolRuntime, records *[]ToolCallRecord) (string, error) {
	messages := []openai.ChatCompletionMessage{
		{
			Role: openai.ChatMessageRoleSystem,
			Content: "你是旅行规划Agent。你必须先调用工具收集信息，再给出最终规划。" +
				"规划必须具体到上午/下午，包含景点安排、通勤距离、预计通勤时间、异常应对。",
		},
		{
			Role:    openai.ChatMessageRoleUser,
			Content: fmt.Sprintf("请为%s做明日一日游规划。要求：先查询天气，再看酒店，再看景点和距离，最后输出行程。", runtime.Destination),
		},
	}

	for step := 0; step < 6; step++ {
		req := openai.ChatCompletionRequest{
			Model:       model,
			Messages:    messages,
			Tools:       buildToolDefinitions(),
			Temperature: 0.2,
		}
		ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
		resp, err := client.CreateChatCompletion(ctx, req)
		cancel()
		if err != nil {
			return "", fmt.Errorf("调用本地大模型失败: %w", err)
		}
		if len(resp.Choices) == 0 {
			return "", fmt.Errorf("大模型未返回内容")
		}

		msg := resp.Choices[0].Message
		messages = append(messages, msg)

		// 没有工具调用时，认为是最终文本输出。
		if len(msg.ToolCalls) == 0 {
			content := strings.TrimSpace(msg.Content)
			if content == "" {
				return "", fmt.Errorf("大模型未返回最终规划文本")
			}
			return content, nil
		}

		for _, toolCall := range msg.ToolCalls {
			toolOutput, callErr := executeLocalTool(runtime, toolCall.Function.Name, toolCall.Function.Arguments, records)
			if callErr != nil {
				toolOutput = fmt.Sprintf(`{"error":"%s"}`, callErr.Error())
			}
			messages = append(messages, openai.ChatCompletionMessage{
				Role:       openai.ChatMessageRoleTool,
				ToolCallID: toolCall.ID,
				Name:       toolCall.Function.Name,
				Content:    toolOutput,
			})
		}
	}
	return "", fmt.Errorf("工具调用轮次超限，未拿到最终规划")
}

// buildToolDefinitions 定义给大模型可用的工具清单。
func buildToolDefinitions() []openai.Tool {
	return []openai.Tool{
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "get_weather",
				Description: "查询目的地天气（本地模拟）",
				Parameters: json.RawMessage(`{
					"type":"object",
					"properties":{
						"destination":{"type":"string"},
						"date":{"type":"string"}
					},
					"required":["destination","date"]
				}`),
			},
		},
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "search_hotels",
				Description: "查询酒店库存（本地模拟，含客满）",
				Parameters: json.RawMessage(`{
					"type":"object",
					"properties":{
						"destination":{"type":"string"},
						"checkin":{"type":"string"},
						"nights":{"type":"integer"}
					},
					"required":["destination","checkin","nights"]
				}`),
			},
		},
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "list_attractions",
				Description: "查询热门景点和客流情况（本地模拟）",
				Parameters: json.RawMessage(`{
					"type":"object",
					"properties":{
						"destination":{"type":"string"}
					},
					"required":["destination"]
				}`),
			},
		},
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "get_distance",
				Description: "查询两个景点之间距离（公里，本地模拟）",
				Parameters: json.RawMessage(`{
					"type":"object",
					"properties":{
						"from":{"type":"string"},
						"to":{"type":"string"}
					},
					"required":["from","to"]
				}`),
			},
		},
	}
}

// executeLocalTool 执行本地函数工具，并把结果作为 JSON 字符串返回给大模型。
func executeLocalTool(runtime *ToolRuntime, toolName, rawArgs string, records *[]ToolCallRecord) (string, error) {
	switch toolName {
	case "get_weather":
		var args struct {
			Destination string `json:"destination"`
			Date        string `json:"date"`
		}
		if err := json.Unmarshal([]byte(rawArgs), &args); err != nil {
			return "", fmt.Errorf("解析get_weather参数失败: %w", err)
		}
		result := map[string]interface{}{
			"destination": runtime.Destination,
			"date":        args.Date,
			"condition":   runtime.Weather.Condition,
			"temperature": runtime.Weather.Temperature,
			"rainy":       runtime.Weather.Rainy,
		}
		out, _ := json.Marshal(result)
		*records = append(*records, ToolCallRecord{ToolName: toolName, Input: rawArgs, Output: string(out)})
		return string(out), nil

	case "search_hotels":
		var args struct {
			Destination string `json:"destination"`
			Checkin     string `json:"checkin"`
			Nights      int    `json:"nights"`
		}
		if err := json.Unmarshal([]byte(rawArgs), &args); err != nil {
			return "", fmt.Errorf("解析search_hotels参数失败: %w", err)
		}
		result := map[string]interface{}{
			"destination": runtime.Destination,
			"checkin":     args.Checkin,
			"nights":      args.Nights,
			"hotels":      runtime.Hotels,
		}
		out, _ := json.Marshal(result)
		*records = append(*records, ToolCallRecord{ToolName: toolName, Input: rawArgs, Output: compactJSON(out)})
		return string(out), nil

	case "list_attractions":
		var args struct {
			Destination string `json:"destination"`
		}
		if err := json.Unmarshal([]byte(rawArgs), &args); err != nil {
			return "", fmt.Errorf("解析list_attractions参数失败: %w", err)
		}
		result := map[string]interface{}{
			"destination": runtime.Destination,
			"attractions": runtime.Attractions,
		}
		out, _ := json.Marshal(result)
		*records = append(*records, ToolCallRecord{ToolName: toolName, Input: rawArgs, Output: compactJSON(out)})
		return string(out), nil

	case "get_distance":
		var args struct {
			From string `json:"from"`
			To   string `json:"to"`
		}
		if err := json.Unmarshal([]byte(rawArgs), &args); err != nil {
			return "", fmt.Errorf("解析get_distance参数失败: %w", err)
		}
		d := getDistance(runtime.Distances, args.From, args.To)
		result := map[string]interface{}{
			"from":        args.From,
			"to":          args.To,
			"distance_km": d,
		}
		out, _ := json.Marshal(result)
		*records = append(*records, ToolCallRecord{ToolName: toolName, Input: rawArgs, Output: string(out)})
		return string(out), nil
	default:
		return "", fmt.Errorf("未知工具: %s", toolName)
	}
}

func compactJSON(raw []byte) string {
	s := string(raw)
	if len(s) > 180 {
		return s[:180] + "...(truncated)"
	}
	return s
}

// mockWeather 随机模拟天气场景，覆盖正常/异常情况（如强降雨）。
func mockWeather(rng *rand.Rand) Weather {
	weathers := []Weather{
		{Condition: "晴", Temperature: "18~27C", Rainy: false},
		{Condition: "多云", Temperature: "16~24C", Rainy: false},
		{Condition: "小雨", Temperature: "14~21C", Rainy: true},
		{Condition: "中雨", Temperature: "13~19C", Rainy: true},
	}
	return weathers[rng.Intn(len(weathers))]
}

// mockHotels 随机模拟酒店库存，并包含“客满”异常情况。
func mockHotels(rng *rand.Rand) []Hotel {
	hotels := []Hotel{
		{Name: "成都太古里商务酒店", DistanceToCore: 1.8, PricePerNight: 588, AvailableRooms: rng.Intn(4)},
		{Name: "武侯祠地铁口轻居酒店", DistanceToCore: 0.9, PricePerNight: 429, AvailableRooms: rng.Intn(3)},
		{Name: "宽窄巷子雅致酒店", DistanceToCore: 1.1, PricePerNight: 518, AvailableRooms: rng.Intn(2)},
		{Name: "春熙路城市便捷酒店", DistanceToCore: 2.2, PricePerNight: 359, AvailableRooms: rng.Intn(5)},
	}
	return hotels
}

// mockAttractionsWithCrowd 为景点注入随机客流，便于触发“景点人太多”异常分支。
func mockAttractionsWithCrowd(rng *rand.Rand) []Attraction {
	result := make([]Attraction, 0, len(attractionBase))
	crowdLevels := []string{"低", "中", "高"}

	for _, a := range attractionBase {
		crowdScore := rng.Intn(100)
		level := crowdLevels[1]
		if crowdScore < 35 {
			level = crowdLevels[0]
		} else if crowdScore > 75 {
			level = crowdLevels[2]
		}
		a.CrowdScore = crowdScore
		a.CrowdLevel = level
		result = append(result, a)
	}
	return result
}

func pickHotel(hotels []Hotel, rng *rand.Rand) (*Hotel, string) {
	available := make([]Hotel, 0)
	for _, h := range hotels {
		if h.AvailableRooms > 0 {
			available = append(available, h)
		}
	}

	// 异常场景：全部客满，返回 nil 并提示兜底策略。
	if len(available) == 0 {
		return nil, "酒店全部客满，建议切换至双流/高新片区，或调整到明日出行。"
	}

	picked := available[rng.Intn(len(available))]
	return &picked, "已自动选择有房且距离核心景点较近的酒店。"
}

// collectWarnings 汇总异常信息，供 LLM 进行带约束的排程。
func collectWarnings(weather Weather, hotels []Hotel, attractions []Attraction, selectedHotel *Hotel) []string {
	warnings := make([]string, 0)
	if weather.Rainy {
		warnings = append(warnings, "明日可能降雨，户外景点需谨慎安排。")
	}
	if selectedHotel == nil {
		warnings = append(warnings, "核心区域酒店全部客满，需要跨区住宿或改期。")
	}
	for _, a := range attractions {
		if a.CrowdScore >= 88 {
			warnings = append(warnings, fmt.Sprintf("%s 当前客流极高，建议避开高峰。", a.Name))
		}
	}
	if countFullBooked(hotels) >= 2 {
		warnings = append(warnings, "酒店供应偏紧，建议尽快下单并保留备选。")
	}
	return warnings
}

func getDistance(distances map[string]map[string]float64, from, to string) float64 {
	if from == to {
		return 0
	}
	if row, ok := distances[from]; ok {
		if d, ok2 := row[to]; ok2 {
			return d
		}
	}
	return 6.0
}

func countFullBooked(hotels []Hotel) int {
	count := 0
	for _, h := range hotels {
		if h.AvailableRooms == 0 {
			count++
		}
	}
	return count
}

func countCrowded(attractions []Attraction) int {
	count := 0
	for _, a := range attractions {
		if a.CrowdScore >= 76 {
			count++
		}
	}
	return count
}

// newClient 创建本地 Qwen 客户端。
// 重点：工具数据在本地模拟，但最终决策由本地大模型输出，形成完整闭环。
func newClient() (*openai.Client, string) {
	baseURL := strings.TrimSpace(os.Getenv("LLM_BASE_URL"))
	if baseURL == "" {
		baseURL = defaultBaseURL
	}
	model := strings.TrimSpace(os.Getenv("LLM_MODEL"))
	if model == "" {
		model = defaultModel
	}
	apiKey := strings.TrimSpace(os.Getenv("LLM_API_KEY"))
	if apiKey == "" {
		apiKey = "ollama-local"
	}
	config := openai.DefaultConfig(apiKey)
	config.BaseURL = baseURL
	return openai.NewClientWithConfig(config), model
}

// buildPlanningPrompt 将多工具结果组织为结构化上下文，交由 LLM 生成最终日程。
func buildFallbackPlan(destination string, weather Weather, selectedHotel *Hotel, hotelNote string, attractions []Attraction, warnings []string) string {
	indoor := "成都博物馆"
	outdoor := "武侯祠 + 锦里古街"
	if weather.Rainy {
		outdoor = "宽窄巷子（降雨减弱时机动安排）"
	}
	hotel := "暂无"
	if selectedHotel != nil {
		hotel = selectedHotel.Name
	}
	return fmt.Sprintf("上午（09:00-12:00）：%s，优先稳定完成核心参观。\n下午（13:30-17:30）：%s，避开高峰并减少通勤损耗。\n异常应对：%s\n酒店建议：%s（%s）\n备注：本次为LLM失败兜底规则计划，目的地=%s。",
		indoor, outdoor, strings.Join(warnings, "；"), hotel, hotelNote, destination)
}

func printToolCalls(records []ToolCallRecord) {
	fmt.Println("【0) 工具调用链路（模拟）】")
	if len(records) == 0 {
		fmt.Println("- 本轮未产生工具调用记录。")
		fmt.Println()
		return
	}
	for i, r := range records {
		fmt.Printf("- Step %d: %s\n", i+1, r.ToolName)
		fmt.Printf("  输入: %s\n", r.Input)
		fmt.Printf("  输出摘要: %s\n", r.Output)
	}
	fmt.Println()
}

func printWeather(weather Weather) {
	fmt.Println("【1) 天气查询（模拟）】")
	fmt.Printf("- 成都明日天气：%s，气温 %s\n\n", weather.Condition, weather.Temperature)
}

func printHotelResult(hotels []Hotel, picked *Hotel, note string) {
	fmt.Println("【2) 酒店预订（模拟）】")
	for _, h := range hotels {
		status := "可预订"
		if h.AvailableRooms == 0 {
			status = "客满"
		}
		fmt.Printf("- %s | 距离核心景点 %.1fkm | ￥%d/晚 | 余房:%d | %s\n", h.Name, h.DistanceToCore, h.PricePerNight, h.AvailableRooms, status)
	}
	if picked != nil {
		fmt.Printf("- 推荐预订：%s（余房 %d）\n", picked.Name, picked.AvailableRooms)
	} else {
		fmt.Println("- 推荐预订：暂无可预订酒店")
	}
	fmt.Printf("- 说明：%s\n\n", note)
}

func printAttractionSnapshot(attractions []Attraction) {
	fmt.Println("【3) 景点状态（模拟）】")
	for _, a := range attractions {
		tag := "室外"
		if a.Indoor {
			tag = "室内"
		}
		fmt.Printf("- %s | %s | 客流:%s(%d) | 建议停留 %.1f小时\n", a.Name, tag, a.CrowdLevel, a.CrowdScore, a.StayHours)
	}
	fmt.Println()
}

func printWarnings(warnings []string) {
	fmt.Println("【4) 异常与兜底】")
	if len(warnings) == 0 {
		fmt.Println("- 无明显异常，按计划执行即可。")
		fmt.Println()
		return
	}
	for _, w := range warnings {
		fmt.Printf("- %s\n", strings.TrimSpace(w))
	}
	fmt.Println()
}

func printLLMPlan(model string, plan string, err error) {
	fmt.Println("【5) 大模型最终规划】")
	fmt.Printf("- 模型: %s\n", model)
	if err != nil {
		fmt.Printf("- 状态: 调用失败，已使用兜底规则（%v）\n\n", err)
	} else {
		fmt.Println("- 状态: 调用成功")
		fmt.Println()
	}
	fmt.Println(plan)
}
