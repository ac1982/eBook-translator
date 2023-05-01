import openai
import json
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from requests.exceptions import SSLError
from openai.error import APIConnectionError

# 使用 tenacity 重试装饰器
@retry(
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(10),
    retry=retry_if_exception_type((openai.error.RateLimitError, SSLError, APIConnectionError)),
)
def completion_with_backoff(**kwargs):
    return openai.ChatCompletion.create(**kwargs)

# 定义一个翻译函数
def translate_content(content):
    # 从配置文件中读取配置
    with open('config.json', 'r') as f:
        config = json.load(f)

    # 设置 OpenAI API 密钥
    openai.api_key = config['openai_api_key']

    # 调用具有指数退避策略的聊天补全函数
    response = completion_with_backoff(
        model=config['model'],
        messages=[
            {"role": "system", "content": config['system']},
            {"role": "user", "content": content},
        ],
        temperature=0.3,  # 调整这个值以控制随机性
        # max_tokens=None,  # 设置生成 token 的最大数量限制
    )

    # 提取翻译后的文本和使用的总 token 数
    translated_text = response.choices[0].message.content
    total_tokens = response.usage['total_tokens']
    return translated_text, total_tokens
