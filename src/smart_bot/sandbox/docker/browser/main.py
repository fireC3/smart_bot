from fastapi import FastAPI
import asyncio
from playwright.async_api import async_playwright
from markdownify import markdownify as md

app = FastAPI()

# 你本机代理
PROXY = "http://127.0.0.1:7897"


class WebFetchTool:
    MAX_PER_READ = 1000
    name = "web_fetch"
    description = "Fetch page and extract clean readable content"

    def __init__(self):
        self._cached_url = None
        self._cached_content = None

    # ==========================
    # 优先：普通 httpx 请求
    # ==========================
    async def _httpx_fetch(self, url):
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.bilibili.com/",
        }
        try:
            async with httpx.AsyncClient(proxy=PROXY, headers=headers, follow_redirects=True) as client:
                response = await client.get(url, timeout=15)
                return md(response.text)
        except:
            return ""

    # ==========================
    # 降级：超强反风控浏览器渲染
    # ==========================
    async def _playwright_fetch_bypass(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                proxy={"server": PROXY},
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )

            page = await context.new_page()

            # 彻底抹除爬虫指纹（必过 B 站 412）
            await page.add_init_script("""
                () => {
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN','zh','en-US'] });
                    window.chrome = { runtime: {} };
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                }
            """)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(1.5)
                html = await page.content()
            finally:
                await browser.close()

            return md(html)

    # ==========================
    # 主逻辑：优先 httpx，失败自动用 playwright
    # ==========================
    async def run(self, url: str, start: int = 0, end: int = None):
        if end is None:
            end = start + self.MAX_PER_READ

        try:
            if url != self._cached_url:
                print(f"[WebFetch] 尝试普通请求: {url}")
                res = await self._httpx_fetch(url)

                if len(res.strip()) < 150:
                    print(f"[WebFetch] 普通请求失败，自动切换浏览器渲染...")
                    self._cached_content = await self._playwright_fetch_bypass(url)
                else:
                    self._cached_content = res

                self._cached_url = url

            # 切片返回
            text = self._cached_content or "No content"
            total_len = len(text)
            start = max(0, start)
            end = min(end, total_len)
            chunk = text[start:end]

            return {
                "url": url,
                "range": f"{start} ~ {end} total {total_len}",
                "content": chunk,
                "success": True
            }

        except Exception as e:
            return {
                "url": url,
                "range": f"{start} ~ {end} total {0}",
                "content": f"Browse failed: {str(e)}",
                "success": False
            }


web_fetch = WebFetchTool()

# --------------------------
# API 接口不变
# --------------------------
@app.get("/fetch")
async def fetch(url: str, start: int = 0, end: int = WebFetchTool.MAX_PER_READ):
    return await web_fetch.run(url, start, end)

@app.get("/")
def root():
    return {"status": "running"}