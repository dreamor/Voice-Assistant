"""
通用浏览器操作工具 - browser_ops
使用 stdlib webbrowser 模块打开 URL 和搜索
"""
import logging
import urllib.parse
import webbrowser

logger = logging.getLogger(__name__)


def open_url(url: str) -> str:
    """用默认浏览器打开 URL"""
    if not url or not url.strip():
        return "URL 不能为空"
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"已在浏览器中打开: {url}"
    except Exception as e:
        return f"打开 URL 失败: {e}"


def search_web(query: str, engine: str = "google") -> str:
    """用默认浏览器搜索关键词"""
    if not query or not query.strip():
        return "搜索关键词不能为空"
    engine = engine.lower().strip()
    encoded = urllib.parse.quote_plus(query.strip())
    engine_urls = {
        "google": f"https://www.google.com/search?q={encoded}",
        "bing": f"https://www.bing.com/search?q={encoded}",
        "baidu": f"https://www.baidu.com/s?wd={encoded}",
        "duckduckgo": f"https://duckduckgo.com/?q={encoded}",
    }
    url = engine_urls.get(engine)
    if not url:
        available = ", ".join(engine_urls.keys())
        return f"不支持的搜索引擎: {engine}，可用: {available}"
    try:
        webbrowser.open(url)
        return f"已使用 {engine} 搜索: {query}"
    except Exception as e:
        return f"搜索失败: {e}"