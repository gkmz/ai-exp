# 电子书 PDF 导出设计

## 目标

在 CAMEL 多智能体协作完成后，将五章完整正文自动导出为中文 PDF，默认输出到 `output/pdf/拖延心理学.pdf`。终端输出只承担进度提示，不作为电子书数据源。

## 非目标

- 不从历史 `output.txt` 自动恢复或解析电子书。
- 不改变 CAMEL 的角色协作协议和模型调用方式。
- 不在本功能中校验案例和实验引用的学术真实性。
- 不引入需要额外安装 TeX 或浏览器的 PDF 生成链路。

## 方案

使用 ReportLab 直接排版 PDF。直接排版可以在当前只有 Python 和 Pandoc 的环境中工作，并能明确控制中文字体、页面尺寸、章节分页和页码。Pandoc 保留为未来 EPUB/Markdown 转换的可选工具，不作为 PDF 的运行时依赖。

## 模块划分

### `ebook.py`

- `extract_chapter(content)`：从单轮心理学家响应中提取正式章节。只有检测到一个章节标题时才接受；包含多个章节标题的大纲会被忽略。
- `validate_chapters(chapters)`：检查第一至第五章是否齐全，缺失时抛出包含缺失章节编号的异常。
- `build_pdf(chapters, output_path)`：验证章节、创建输出目录、选择中文字体并生成 PDF。使用临时文件写入，成功后再替换最终文件，避免留下残缺产物。

### `digital-book-writing.py`

- 删除逐字动画输出。
- 在协作循环中收集 `assistant_response.msg.content` 中的正式章节。
- 收到 `CAMEL_TASK_DONE` 后调用 `build_pdf`；失败时打印可操作的错误信息并以非零状态退出。

## PDF 版式

- A5 纸张，适合电子阅读和打印。
- 独立封面：书名和核心观点。
- 目录页：五章标题和页码由 ReportLab 自动生成。
- 每章从新页开始，章节标题使用较大字号。
- 正文使用中文字体，段落按 CJK 规则换行，页脚显示页码。

## 字体策略

优先使用 `EBOOK_FONT_PATH` 环境变量指定的字体。未指定时探测 macOS 的苹方/冬青黑体和 Linux 的 Noto Sans CJK 等常见路径。找不到字体时直接报错并说明配置方式，不生成可能出现方框字的 PDF。

## 数据流

```text
RolePlaying.step()
  -> assistant_response.msg.content
  -> extract_chapter()
  -> chapters[1..5]
  -> validate_chapters()
  -> build_pdf()
  -> output/pdf/拖延心理学.pdf
```

## 错误处理

- 缺少章节：报告缺失编号，不调用 PDF 渲染。
- 字体不存在或无法注册：报告 `EBOOK_FONT_PATH` 配置方法。
- PDF 渲染异常：删除临时文件，保留已有正式 PDF，不覆盖有效旧文件。
- 输出目录不存在：自动创建。

## 测试设计

使用标准库 `unittest`：

1. 单个章节可以被识别并清理 Markdown 标题。
2. 含多个章节标题的大纲不会被误收集。
3. 缺章时校验失败并列出编号。
4. 五章最小正文可以生成 `%PDF` 文件，并且输出路径存在。

## 验收标准

- 运行 demo 后，五章齐全时生成 `output/pdf/拖延心理学.pdf`。
- 缺章时进程失败且不生成新残缺文件。
- PDF 能被 `pdfinfo`/`pypdf` 读取，中文文本不出现字体缺失方框。
- 渲染至少一页 PNG 检查封面、章节标题、正文和页码无裁切或重叠。
