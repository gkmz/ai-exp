import os
import sys
from pathlib import Path

from camel.models import ModelFactory
from camel.societies import RolePlaying
from camel.types import ModelPlatformType
from colorama import Fore
from dotenv import load_dotenv

from ebook import EbookExportError, IncompleteEbookError, build_pdf, extract_chapter

load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL_ID") or ""
OUTPUT_PATH = Path("output/pdf/拖延心理学.pdf")

# 定义电子书协作目标，章节正文由角色会话逐轮生成。
TASK_PROMPT = """
创作一本关于"拖延症心理学"的短篇电子书，目标读者是对心理学感兴趣的普通大众。
要求：
1. 内容科学严谨，基于实证研究
2. 语言通俗易懂，避免过多专业术语
3. 包含实用的改善建议和案例分析
4. 篇幅控制在8000-10000字
5. 必须恰好分为五章，按第一章至第五章依次创作，每章包含完整正文
6. 每章标题必须独占一行，并严格使用“## 第一章：标题”至“## 第五章：标题”的格式
7. 将引言融入第一章，将总结融入第五章，不要创建独立的引言或结语章节
8. 大纲完成后，每轮只交付一个完整章节，不要在同一响应中合并多章正文
"""


def _create_session() -> RolePlaying:
    """创建共享同一模型的作家与心理学家协作会话。"""
    # 本示例使用兼容 OpenAI 协议的 Qwen 平台配置。
    model = ModelFactory.create(
        model_platform=ModelPlatformType.QWEN,
        model_type=LLM_MODEL,
        url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )
    return RolePlaying(
        assistant_role_name="心理学家",
        user_role_name="作家",
        task_prompt=TASK_PROMPT,
        model=model,
        # 原始任务已定义 PDF 导出的结构契约，禁止任务细化代理再次改写。
        with_task_specify=False,
    )


def _collect_chapters(role_play_session: RolePlaying) -> tuple[dict[int, str], int]:
    """运行角色协作并收集五个正式章节。"""
    chat_turn_limit, turn_count = 30, 0
    input_msg = role_play_session.init_chat()
    chapters: dict[int, str] = {}

    while turn_count < chat_turn_limit:
        turn_count += 1
        assistant_response, user_response = role_play_session.step(input_msg)

        # RolePlaying 先生成作家消息；DONE 表示上一轮心理学家正文已经交付。
        user_message = user_response.msg
        if user_response.terminated or user_message is None:
            raise EbookExportError("作家代理提前终止，未返回任务完成标志")
        if "CAMEL_TASK_DONE" in user_message.content:
            return chapters, turn_count

        assistant_message = assistant_response.msg
        if assistant_response.terminated or assistant_message is None:
            raise EbookExportError("心理学家未返回有效内容，电子书协作已终止")

        # 只收集单章正文，含多个标题的大纲和最终摘要会被自动跳过。
        chapter = extract_chapter(assistant_message.content)
        if chapter is not None:
            chapter_number, chapter_content = chapter
            chapters[chapter_number] = chapter_content
            print(Fore.GREEN + f"已收集第 {chapter_number} 章")
        else:
            print(Fore.BLUE + f"第 {turn_count} 轮协作完成")

        input_msg = assistant_message

    raise EbookExportError(f"达到 {chat_turn_limit} 轮限制，协作任务仍未完成")


def main() -> int:
    """运行电子书协作流程并将完整内容导出为 PDF。"""
    print(Fore.YELLOW + f"协作任务：\n{TASK_PROMPT}")
    try:
        chapters, turn_count = _collect_chapters(_create_session())
        output_path = build_pdf(chapters, OUTPUT_PATH)
    except (IncompleteEbookError, EbookExportError) as exc:
        print(Fore.RED + f"电子书导出失败：{exc}", file=sys.stderr)
        return 1

    print(Fore.MAGENTA + f"电子书创作完成，共 {turn_count} 轮协作")
    print(Fore.GREEN + f"PDF 已输出：{output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
