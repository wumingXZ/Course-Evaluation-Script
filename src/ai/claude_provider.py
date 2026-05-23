from .base import BaseProvider


class ClaudeProvider(BaseProvider):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic 包未安装，请运行: pip install anthropic"
            )

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text
