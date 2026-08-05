# CAMEL 电子书生成 Demo

这个示例通过 CAMEL 的 `RolePlaying` 让“作家”和“心理学家”协作完成五章电子书，并在章节齐全后自动生成中文 PDF。

## 环境配置

在 `.env` 中配置模型服务：

```dotenv
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-compatible-endpoint/v1
LLM_MODEL_ID=your-model-id
```

安装依赖并运行：

```bash
uv sync
uv run python digital-book-writing.py
```

成功后生成：

```text
output/pdf/拖延心理学.pdf
```

macOS 可以直接打开：

```bash
open output/pdf/拖延心理学.pdf
```

## 中文字体

程序会自动探测 macOS 和 Linux 的常见中文字体。如果当前系统未安装候选字体，使用 `EBOOK_FONT_PATH` 指定一个支持中文的 TTF 或 TTC 字体：

```bash
EBOOK_FONT_PATH=/path/to/chinese-font.ttf uv run python digital-book-writing.py
```

缺少章节、字体不可用或 PDF 渲染失败时，程序会返回非零状态，并且不会用残缺文件覆盖已有 PDF。
