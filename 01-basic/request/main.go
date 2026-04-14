package main

// Demo 接口定义了运行演示的方法
type Demo interface {
	Run()
}

func main() {
	var d Demo
	// d = &RequestDemo{}
	// d = &InvokeParamsDemo{}
	// d = &ChatHistoryDemo{}
	d = &RequestBootstrapDemo{}
	d.Run()
}
