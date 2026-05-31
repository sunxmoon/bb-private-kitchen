import asyncio
import json
import logging
import re
import subprocess

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _clean_spaces(obj):
    """Remove unnecessary spaces between CJK characters."""
    cjk = r'[一-鿿，。！？：；（）]'
    if isinstance(obj, str):
        return re.sub(rf'(?<={cjk})\s+(?={cjk})', '', obj)
    elif isinstance(obj, list):
        return [_clean_spaces(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: _clean_spaces(v) for k, v in obj.items()}
    return obj


RECIPE_PROMPT_TEMPLATE = """你是一位经验丰富的「私房菜主厨」。请为这道名为"{dish_name}"的菜品生成一份详细且专业的菜谱。
{description_text}

【输出格式约束】
必须且只能返回一个合法的JSON对象，不要包含任何Markdown代码块标记（如```json），也不要包含任何多余的说明文字。JSON结构必须严格遵循以下模板：

{{
  "ingredients": [
    {{"name": "食材名称（如：五花肉）", "amount": "用量（如：500g）"}},
    {{"name": "食材名称", "amount": "用量"}}
  ],
  "steps": [
    "第一步的具体操作，言简意赅，动作明确。",
    "第二步的具体操作...",
    "最后的摆盘或出锅动作。"
  ],
  "cook_time": "总时长（必须包含时间单位，例如：\"45分钟\"、\"1.5小时\"）",
  "difficulty": "难度评估（必须严格在\"简单\"、\"中等\"、\"困难\"三个词中选择一个）",
  "tips": [
    "小贴士1：关于火候、选材或调味的私房秘诀。",
    "小贴士2：可以避免失败的注意事项。"
  ]
}}

【内容风格要求】
1. 步骤语言要求专业、精炼，具有实操性。
2. 严禁在中文词组中间或中文字符之间出现不必要的空格。
3. 小贴士（tips）必须是一个数组，提供1-3条真正有用的私房菜烹饪技巧。
"""


_RETRY_DELAYS = [2, 4, 8]
_CACHE_TTL = 300  # 5 minutes


class AIClient:
    def __init__(self):
        self.host_url = settings.AGY_HOST_URL or None
        self._available = None
        self._available_ts = 0.0

    async def check_available(self) -> bool:
        import time
        now = time.monotonic()
        if self._available is not None and now - self._available_ts < _CACHE_TTL:
            return self._available
        self._available = None
        if self.host_url:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{self.host_url}/health", timeout=5)
                    data = resp.json()
                    self._available = data.get("ok", False)
            except Exception as e:
                logger.warning("AGY proxy health check failed: %s", e)
                self._available = False
        else:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["agy", "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                self._available = result.returncode == 0
            except Exception as e:
                logger.warning("AGY CLI check failed: %s", e)
                self._available = False
        self._available_ts = time.monotonic()
        return self._available

    async def _call_api_once(self, prompt: str) -> str:
        if self.host_url:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.host_url}/generate",
                    json={"prompt": prompt},
                    timeout=120,
                )
                if resp.status_code >= 400:
                    try:
                        err = resp.json()
                        msg = err.get("stderr") or err.get("error") or resp.text
                    except Exception:
                        msg = resp.text
                    raise RuntimeError(f"proxy {resp.status_code}: {msg[:500]}")
                return resp.text
        else:
            result = await asyncio.to_thread(
                subprocess.run,
                ["agy", "--print", prompt],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"agy CLI failed: {result.stderr}")
            return result.stdout

    async def _call_api(self, prompt: str) -> str:
        last_error = None
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                return await self._call_api_once(prompt)
            except (RuntimeError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                # Don't retry on 4xx client errors (except timeout)
                if isinstance(e, RuntimeError) and "proxy 4" in str(e) and "proxy 408" not in str(e):
                    raise
                if attempt < len(_RETRY_DELAYS):
                    delay = _RETRY_DELAYS[attempt]
                    total = len(_RETRY_DELAYS) + 1
                    logger.warning(
                        "AI call failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1, total, delay, e,
                    )
                    await asyncio.sleep(delay)
        raise last_error

    async def generate_recipe(self, dish_name: str, description: str = None) -> dict:
        description_text = ""
        if description:
            description_text = f"菜品描述：{description}"
        else:
            description_text = "请根据菜名推测合理的做法"

        prompt = RECIPE_PROMPT_TEMPLATE.format(
            dish_name=dish_name,
            description_text=description_text
        )

        raw = await self._call_api(prompt)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    pass

            data = _clean_spaces(data)

            if isinstance(data, dict) and "result" in data:
                res = data["result"]
                if isinstance(res, str):
                    try:
                        inner_data = json.loads(res)
                        return _clean_spaces(inner_data)
                    except json.JSONDecodeError:
                        return _clean_spaces(res)
                return _clean_spaces(res)

            if isinstance(data, str):
                 if data.strip().startswith('{'):
                     try:
                         data = json.loads(data)
                         data = _clean_spaces(data)
                     except (json.JSONDecodeError, KeyError, TypeError):
                         pass

            return data
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    data = _clean_spaces(data)
                    if isinstance(data, dict) and "result" in data:
                        res = data["result"]
                        if isinstance(res, str):
                            try:
                                inner_data = json.loads(res)
                                return _clean_spaces(inner_data)
                            except json.JSONDecodeError:
                                return _clean_spaces(res)
                        return _clean_spaces(res)
                    return data
                except Exception:
                    pass
            raise


ai_client = AIClient()
