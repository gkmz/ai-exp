package main

import "fmt"

func main() {
	texts := []string{
		"Developer uses DeepSeek API to generate code.",
		"开发者使用 DeepSeek API 生成代码。",
		"func main() {\n\tfmt.Println(\"Hello, World!\")\n}",
	}
	bte := BadTokenEstimater{}
	te := TokenEstimater{}
	for _, text := range texts {
		fmt.Println("=== 初略估算 ===")
		bte.run(text)

		fmt.Println("=== 精确计算 ===")
		te.run(text)
	}

	fmt.Println("=== 估算成本 ===")
	te.runCostDemo()
}
