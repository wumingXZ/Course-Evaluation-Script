import os

from ..models import AIConfig, Sentiment
from .base import BaseProvider
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider


SENTIMENT_CN = {
    Sentiment.LIKE: "喜欢（正面评价为主）",
    Sentiment.NEUTRAL: "一般（中性评价为主）",
    Sentiment.DISLIKE: "讨厌（负面评价为主）",
}


class AIWriter:
    def __init__(self, config: AIConfig):
        self.config = config
        self.provider = self._create_provider()

    def _create_provider(self) -> BaseProvider:
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"环境变量 {self.config.api_key_env} 未设置，"
                f"请设置 API Key 或修改 term.yaml 中的 ai.api_key_env"
            )

        if self.config.provider == "claude":
            return ClaudeProvider(self.config.model, api_key, self.config.base_url)
        elif self.config.provider == "openai":
            return OpenAIProvider(self.config.model, api_key, self.config.base_url)
        else:
            raise ValueError(f"不支持的 AI provider: {self.config.provider}")

    def generate_fill_text(
        self,
        course_name: str,
        question_title: str,
        sentiment: Sentiment,
        existing_presets: list[str] | None = None,
    ) -> str:
        system = (
            "你是一名复旦大学的学生，正在完成课程评价。"
            "请根据课程名称、题目和对课程的态度，生成一段自然、个性化的中文评价文字。"
            "文字应简洁（30-80字），内容具体，不要泛泛而谈。"
            "不要出现引号包裹，直接输出评价文字。"
        )

        preset_hint = ""
        if existing_presets:
            preset_hint = "参考模板（请用自己的话改写，不要照抄）：\n" + "\n".join(
                f"  - {p}" for p in existing_presets
            )
        else:
            preset_hint = "（无参考模板）"

        user = (
            f"课程名称：{course_name}\n"
            f"题目：{question_title}\n"
            f"态度：{SENTIMENT_CN.get(sentiment, '一般')}\n\n"
            f"{preset_hint}\n\n"
            f"请生成一段针对该课程和题目的个性化评价："
        )

        return self.provider.chat(system, user)
