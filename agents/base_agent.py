from abc import ABC
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# DeepSeek 兼容 OpenAI 协议，切换模型只需改 base_url 和 model
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


class BaseAgent(ABC):
    model = "deepseek-chat"

    def _call_llm(self, system: str, user: str) -> str:
        """向 LLM 发送单轮对话，返回纯文本响应。"""
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content
