"""允许直接执行 `python advance-demo/main.py`。"""

# 该文件只保留最薄的命令行启动职责，完整流程位于 app.py 的 main/run 中。
from app import main

if __name__ == "__main__":
    # 只有直接运行本文件时才启动，作为模块导入时不会产生副作用。
    main()
