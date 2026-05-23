from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai 包未安装，请运行: pip install openai"
            )

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or ""
