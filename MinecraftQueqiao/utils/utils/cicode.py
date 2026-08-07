import re

# [[CICode,url=...,name=...]] 聊天图片标记
CICODE_RE = re.compile(r"\[\[CICode,([^\]]+)\]\]")


def parse_cicode(text: str) -> tuple[str, list[str]]:
    """解析CICODE"""
    urls: list[str] = []

    def _replace(match: re.Match) -> str:
        for part in match.group(1).split(","):
            if part.startswith("url="):
                url = part[4:].strip()
                if url.startswith(("http://", "https://")):
                    urls.append(url)
        return ""  # 从文本中移除 CICode

    return CICODE_RE.sub(_replace, text), urls