package main

import "testing"

// TestValidateExpectedCalls 验证预期的两个天气调用和一个时间调用能够通过校验。
func TestValidateExpectedCalls(t *testing.T) {
	calls := []ToolCallW{
		newToolCallForTest("weather-shanghai", "get_weather", `{"location":"上海"}`),
		newToolCallForTest("weather-new-york", "get_weather", `{"location":"纽约"}`),
		newToolCallForTest("time-new-york", "get_time", `{"timezone":"America/New_York"}`),
	}

	if err := validateExpectedCalls(calls); err != nil {
		t.Fatalf("预期三张工单通过校验，实际失败: %v", err)
	}
}

// TestValidateExpectedCallsRejectsMergedWeather 验证合并城市或缺少调用时会被拒绝。
func TestValidateExpectedCallsRejectsMergedWeather(t *testing.T) {
	calls := []ToolCallW{
		newToolCallForTest("weather-merged", "get_weather", `{"location":"上海和纽约"}`),
		newToolCallForTest("time-new-york", "get_time", `{"timezone":"America/New_York"}`),
	}

	if err := validateExpectedCalls(calls); err == nil {
		t.Fatal("预期合并天气工单校验失败，实际通过")
	}
}

// newToolCallForTest 构造测试所需的最小工具调用对象。
func newToolCallForTest(id, name, arguments string) ToolCallW {
	call := ToolCallW{ID: id, Type: "function"}
	call.Function.Name = name
	call.Function.Arguments = arguments
	return call
}
