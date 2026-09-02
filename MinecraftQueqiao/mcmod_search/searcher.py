import html
import re
from typing import List, Tuple
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from gsuid_core.logger import logger

SEARCH_BASE_URL = "https://search.mcmod.cn/s"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def parse_mcmod_page(
    soup: BeautifulSoup, status_code: int, final_url: str = ""
) -> Tuple[bool, List[Tuple[str, str]]]:
    """通过 DOM 结构契约判定页面状态并提取搜索结果。

    返回 (is_captcha, results)。
    """
    # 1. HTTP 状态非 200 或发生重定向离开搜索页，直接视为遭遇验证码/拦截
    if status_code != 200 or (final_url and "search.mcmod.cn/s" not in final_url):
        return True, []

    # 2. 存在结果列表：提取模组名称与链接
    result_list = soup.find("div", class_="search-result-list")
    if result_list:
        results: List[Tuple[str, str]] = []
        for item in result_list.find_all("div", class_="result-item"):
            head = item.find("div", class_="head")
            if not head:
                continue

            title_a = None
            for a in head.find_all("a"):
                # 过滤分类角标链接，定位正文标题链接
                if a.find_parent("div", class_="class-category"):
                    continue
                if a.get_text(strip=True):
                    title_a = a
                    break

            if not title_a:
                continue

            clean_name = re.sub(r"\s+", " ", title_a.text).strip()
            clean_name = html.unescape(clean_name)

            href = title_a.get("href", "").strip()
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                href = f"https://www.mcmod.cn{href}"

            if clean_name and href:
                results.append((clean_name, href))

        return False, results

    # 3. 正常 0 结果页：检查是否存在 MC 百科搜索页标准骨架（搜索框 / 分类菜单）
    is_normal_search_page = bool(
        soup.find("input", id="search-input")
        or soup.find("div", class_="search-box")
        or soup.find("div", class_="search-menu-mcmod")
    )
    if is_normal_search_page:
        return False, []

    # 4. 既无结果列表，又缺少正常搜索页 DOM 骨架，判定为遭遇验证码/拦截
    return True, []


async def search_mcmod(keyword: str, max_results: int = 10) -> str:
    """在 MC 百科检索模组并返回格式化文本"""
    clean_kw = keyword.strip()
    if not clean_kw:
        return "请输入要搜索的模组名称，例如：mcmod搜索 jei"

    search_url = f"{SEARCH_BASE_URL}?key={quote_plus(clean_kw)}"

    try:
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=10.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(SEARCH_BASE_URL, params={"key": clean_kw})
            status_code = resp.status_code
            html_text = resp.text
            final_url = str(resp.url)
    except Exception as e:
        logger.error(f"[MCQueQiao] MC百科搜索请求失败: {e}")
        return f"遭遇验证码，请手动访问：{search_url}"

    soup = BeautifulSoup(html_text, "html.parser")
    is_captcha, results = parse_mcmod_page(soup, status_code, final_url)

    # 验证码/拦截处理
    if is_captcha:
        return f"遭遇验证码，请手动访问：{search_url}"

    # 无结果处理
    if not results:
        return f"未搜索到关于“{clean_kw}”的模组结果，请更换关键词重试。"

    # 格式化输出
    display_results = results[:max_results]
    lines = ["搜索到以下结果："]
    for name, link in display_results:
        lines.append(f"{name}：{link}")

    return "\n".join(lines)
