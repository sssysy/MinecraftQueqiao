from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import re

from gsuid_core.logger import logger

_RENDER_DIR = Path(__file__).parent
_STYLE_DIR = _RENDER_DIR / "template" / "style"
_FONT_PATH = _RENDER_DIR.parent / "fonts" / "mc-unicode-font.otf"

_CSS_CACHE: dict[str, str] = {}
_FONT_CACHE: str | None = None

_CSS_LINK_PATTERN = re.compile(
    r'<link\b(?=[^>]*\brel=["\']stylesheet["\'])(?=[^>]*\bhref=["\']([^"\']+\.css)["\'])[^>]*>',
    re.IGNORECASE,
)


def get_font_data_uri() -> str:
    """获取本地 Minecraft Unicode 字体的 Base64 Data URI（含内存缓存）。"""
    global _FONT_CACHE
    if _FONT_CACHE is None:
        if _FONT_PATH.exists():
            data = _FONT_PATH.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            _FONT_CACHE = f"data:font/otf;base64,{b64}"
        else:
            logger.warning(f"[MCQueQiao] 未找到本地字体文件: {_FONT_PATH}")
            _FONT_CACHE = ""
    return _FONT_CACHE


def _inline_local_css(html_content: str) -> str:
    """内联 HTML 内部引用的本地 CSS 文件。"""
    if "<link" not in html_content:
        return html_content

    def _replace_link(match: re.Match) -> str:
        css_href = match.group(1)
        filename = Path(css_href).name
        if filename not in _CSS_CACHE:
            css_file = _STYLE_DIR / filename
            if css_file.is_file():
                _CSS_CACHE[filename] = css_file.read_text(encoding="utf-8")
            else:
                return match.group(0)
        css_content = _CSS_CACHE[filename]
        return f"<style>\n/* Inlined: {filename} */\n{css_content}\n</style>"

    try:
        return _CSS_LINK_PATTERN.sub(_replace_link, html_content)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 内联 CSS 异常: {e}")
        return html_content


def _replace_local_fonts(html_content: str) -> str:
    """将模板/CSS 中的 /fonts/... 替换为本地字体的 Base64 Data URI。"""
    if "/fonts/" not in html_content:
        return html_content
    font_uri = get_font_data_uri()
    if font_uri:
        return re.sub(
            r'/fonts/[A-Za-z0-9_.\-]+\.(?:otf|ttf|woff2?)',
            font_uri,
            html_content,
        )
    return html_content


def fill_template(template: str, replacements: dict[str, str]) -> str:
    """填充 HTML 模板并内联静态样式与字体。"""
    html = _inline_local_css(template)
    html = _replace_local_fonts(html)
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", value)
    return html


async def render_html(
    html_content: str,
    selector: str,
    *,
    viewport_width: int = 1200,
    viewport_height: int = 900,
    device_scale_factor: float = 2.0,
    timeout: float = 25.0,
) -> bytes:
    """统一使用 Playwright 渲染 HTML 页面并截取指定元素。"""
    try:
        from playwright.async_api import (
            TimeoutError as PlaywrightTimeoutError,
            async_playwright,
        )
    except ImportError:
        logger.error("[MCQueQiao] playwright 库未安装，无法进行 HTML 渲染")
        raise RuntimeError("playwright 库未安装，此功能无法使用")

    html_content = _inline_local_css(html_content)
    html_content = _replace_local_fonts(html_content)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=device_scale_factor,
            )
            page = await context.new_page()
            page.set_default_timeout(int(timeout * 1000))
            page.set_default_navigation_timeout(int(timeout * 1000))

            await page.set_content(
                html_content,
                wait_until="networkidle",
                timeout=int(timeout * 1000),
            )

            # 等待所有图片加载完成
            await page.wait_for_function(
                "() => Array.from(document.querySelectorAll('img')).every(img => img.complete)",
                timeout=15000,
            )
            await page.wait_for_timeout(100)

            element = page.locator(selector)
            await element.wait_for(state="visible")
            bbox = await element.bounding_box()
            if bbox is None:
                raise RuntimeError(f"无法获取目标元素位置: {selector}")

            needed_height = int(bbox["y"] + bbox["height"] + 20)
            needed_width = int(bbox["x"] + bbox["width"] + 20)
            if needed_height > viewport_height or needed_width > viewport_width:
                await page.set_viewport_size({
                    "width": max(viewport_width, needed_width),
                    "height": max(viewport_height, needed_height),
                })
                await page.wait_for_timeout(50)
                bbox = await element.bounding_box()
                if bbox is None:
                    raise RuntimeError(f"无法获取目标元素位置: {selector}")

            clip_rect = {
                "x": bbox["x"],
                "y": bbox["y"],
                "width": bbox["width"],
                "height": bbox["height"],
            }

            screenshot_bytes = await page.screenshot(
                clip=clip_rect,
                type="png",
            )
            await browser.close()
            return screenshot_bytes

    except PlaywrightTimeoutError as e:
        logger.warning(f"[MCQueQiao] Playwright 渲染 HTML 超时: {e!r}")
        raise TimeoutError("Playwright 渲染图片超时")
    except Exception as e:
        logger.error(f"[MCQueQiao] Playwright 渲染 HTML 失败: {e!r}")
        raise
