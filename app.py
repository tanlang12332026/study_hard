import json
import os
import random
import re
import sys
import asyncio
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from crawl4ai import AsyncWebCrawler, CrawlResult, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, \
    RateLimiter
from lxml import html
import httpx
from parsel import Selector
from starlette.middleware.gzip import GZipMiddleware

from fake_useragent import FakeUserAgent
from redis.asyncio import Redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 程序启动时执行
    asyncio.create_task(delayed_trigger())
    yield
    # 程序关闭时执行（如果需要可以写在这里）

app = FastAPI(lifespan = lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.add_middleware(GZipMiddleware, minimum_size=666)

fake = FakeUserAgent()

av_failure_count = 0  # 3此重启服务器
MY_GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") if os.getenv("MY_GITHUB_TOKEN") else ""
REPO_OWNER = "tanlang12332026"
REPO_NAME = "study_hard"
WORKFLOW_FILE = os.getenv("WORKFLOW_FILE") if os.getenv("WORKFLOW_FILE") else "danmu.yaml"

async def delayed_trigger():

    extra_time = [1, 3 , 5, 7]

    extra_time = random.choice(extra_time)

    await asyncio.sleep(60 * (20 + extra_time))
    trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, WORKFLOW_FILE,
                                                     inputs={"reason": "启动后定时器20分钟触发"})


def _tmp():
    data = {
        "message": [
            [
                "CAWD-915 性慾覺醒的鄉下姪女，將濕濕的幼嫩小穴慢慢地在叔叔身上磨蹭… 青葉春",
                "216 543",
                "2246",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56178/preview.jpg",
                "https://adoda-smart-coin.mushroomtrack.com/hls/x1w6QYDRHx11A-AMOM4NEg/1768756150/56000/56178/56178.m3u8"
            ],

            [
                "WAAA-573 超專注接吻的自慰支援！滿嘴口水吸舔，體液濕透的緊密貼合內射高潮連連！沉溺在接吻聲音中的主觀ASMR規格！耳朵和大腦都融化！ 根尾明里",
                "194 007",
                "1091",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56187/preview.jpg",
                "https://anono-cloneing.mushroomtrack.com/hls/Qmy-DX53GcdYPCEEPmX_ag/1768755883/56000/56187/56187.m3u8"
            ]
        ]
    }
    return data

@app.get("/")
async def root(request: Request):
    print('ip', request.client.host)
    return {"message": "Hello World"}


async def _handleSearchKVM(q:str, cache: bool):

    cache_url = f"https://www.4kvm.org/xssearch?s={q}"
    redis, data = await _getCacheData(cache_url)
    if redis and data:
        await redis.aclose()
        return {"message": data}

    start_time = time.perf_counter()
    browser_config = BrowserConfig(headless=True, text_mode=True, light_mode=True)
    run_config1 = CrawlerRunConfig()
    run_config1.cache_mode = CacheMode.ENABLED if cache else CacheMode.WRITE_ONLY

    run_config2 = CrawlerRunConfig(capture_network_requests = True)
    run_config2.cache_mode =  CacheMode.WRITE_ONLY

    # run_config2.delay_before_return_html = 2
    urls = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result: CrawlResult = await crawler.arun(cache_url, config=run_config1)
        # print(result.html)
        if len(result.html) == 0:
            if redis:
                await redis.aclose()
            return {"message": []}
        root = html.fromstring(result.html)
        link = root.xpath('//div[@class="result-item"][1]//a/@href')
        link = link[0] if len(link) > 0 else None
        if link is None:
            if redis:
                await redis.aclose()
            return {"message": []}
        result: CrawlResult = await crawler.arun(link, config=run_config1)
        root = html.fromstring(result.html)
        link = root.xpath('//*[@class="se-q"]/a[1]/@href')
        link = link[0] if len(link) > 0 else None
        if link is None:
            if redis:
                await redis.aclose()
            return {"message": []}
        # 视频详情页
        result: CrawlResult = await crawler.arun(link, config=run_config1)
        root = html.fromstring(result.html)

        links = root.xpath('//*[@class="jujiepisodios"]/a/text()')
        link = root.xpath('//iframe/@src')

        link = link[0] if len(link) > 0 else None
        if link is None:
            if redis:
                await redis.aclose()
            return {"message": []}

        tasks = []
        for (index, i) in enumerate(links):
            sps = link.split('&')
            sing_link = sps[0] + '&' + sps[1] + '&' + 'ep=' + str(index)
            task = asyncio.create_task(_handm3u8_mp4(i, crawler, sing_link, run_config2))
            tasks.append(task)

        result_links = await asyncio.gather(*tasks)
        for r_link in result_links:
            print('finish')
            print(r_link)
            m3u8 = r_link[1]
            mp4 = r_link[2]
            if mp4 and len(mp4) > 0:
                urls.append(mp4)
            else:
                if m3u8 and len(m3u8) > 0:
                    urls.append(m3u8)
                else:
                    urls.append('1')

    end_time = time.perf_counter() - start_time
    print(f'耗时 ---{end_time}')
    if len(urls) > 0:
        if redis:
            await redis.setex(cache_url, 3600 * 3, json.dumps(urls))
            await redis.aclose()

        if redis:
            await redis.aclose()
        return {"message": [urls]}
    if redis:
        await redis.aclose()
    return {"message": []}

async def _handm3u8_mp4(page, crawler, link, run_config2):
    result: CrawlResult = await crawler.arun(link, config=run_config2)
    # print(result.html)
    root = html.fromstring(result.html)
    # m3u8
    pattern = r'https.*?\/ws.*?\.svg'
    # 编译正则（提升效率）
    regex = re.compile(pattern)

    # 匹配第一个符合条件的链接
    match_result = regex.search(result.html)
    first_matched_url =  None
    mp4 = None
    if match_result:
        first_matched_url = match_result.group()  # 获取匹配到的字符串
        # print(f"✅ 第一个符合条件的链接：{first_matched_url}")
        first_matched_url = first_matched_url.replace('ws', 'm3')
        first_matched_url = first_matched_url.replace('svg', 'm3u8')
        # print(first_matched_url)
    else:
        print("❌ 未匹配到符合条件的链接")
        # 匹配MP4

    mp4 = ''

    item = {}
    for item2 in result.network_requests:
        if item2['url'].startswith('https://play.kvmplay.org/ws') and item2['url'].endswith('svg'):
            # print('m3u8 ---', item)
            # print(item)
            item = item2
            break
    if 'url' in item:
        async with httpx.AsyncClient() as client:
            res = await client.post(item['url'], timeout=25, headers=item['headers'], data=item['post_data'])
            # print(1)
            if res.status_code == 200:
                # print(res.content)
                mp4 = json.loads(res.content)['url']
                # print(mp4)

    return (page, first_matched_url, mp4)

async def _getCacheData(cache_url):
    print('cache_url', cache_url)
    REDIS_URL = os.environ.get('REDIS_URL', None)
    redis_url = None
    try:
        from redis_config import REDIS_URL as redis_url2
        redis_url = redis_url2
    except ImportError:
        pass

    REDIS_URL = redis_url if REDIS_URL is None else REDIS_URL

    redis = None
    try:
        print('redis url', REDIS_URL)
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
        print("redis---- :", await redis.ping())
    except Exception as e:
        print("错误了", e, "REDIS_URL", REDIS_URL)

    if redis:
        res = await redis.get(cache_url)
        time2= await redis.ttl(cache_url)
        print("命中缓存 cache_url redis---- :", res)
        if time2 > 0:
            print("缓存时间", time2)
        if res:
            data = json.loads(res)
            if data and len(data) > 0:
                return redis, data
    return redis, None

async def _getDataFromOtherServer(server_name)  -> dict:
    print(f'正在从备用服务器请求数据 --- {server_name}')
    url = f"https://{server_name}.xiaodu1234.xyz"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        print(f"备用服务器 -- {server_name} 请求数据成功")
        return res.json()

async def _handleHotAv(background_tasks, q, cache):
    global av_failure_count
    num = int(q)
    start_time = time.perf_counter()
    if num > 1477 or num < 0:
        return {"message": []}
    time_now = int(time.time() * 1000)
    url = f"https://jable.tv/hot/{num}/?mode=async&function=get_block&block_id=list_videos_common_videos_list&sort_by=video_viewed&_={time_now}"
    cache_url = f"https://jable.tv/hot/{num}/"
    redis, data = await _getCacheData(cache_url)
    if redis and data:
        await redis.aclose()
        return {"message": data}

    # 如果是主服务器
    if WORKFLOW_FILE is 'danmu.yaml' and av_failure_count > 0:
        # 去另外服务器获取数据
        data:dict = await _getDataFromOtherServer("av02")
        datas = data.get('message', [])
        if len(datas) > 0:
            return {"message": datas}
        # 03
        return await _getDataFromOtherServer("av03")

    # return _tmp()
    urls_links = []
    browser_config = BrowserConfig()
    browser_config.headless = True
    browser_config.enable_stealth = True
    browser_config.browser_mode = 'docker' if redis else 'dedicated'
    # browser_config.text_mode = True
    browser_config.user_agent = fake.chrome

    run_config = CrawlerRunConfig()
    run_config.verbose = False
    run_config.stream = True
    run_config.semaphore_count = 12
    # run_config.delay_before_return_html = 20000

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result: CrawlResult = await crawler.arun(url, config=run_config)
        # print(result.html)
        root = Selector(text=result.html)
        box = root.css('div.img-box.cover-md a::attr(href)').getall()
        # print(len(box))
        results_info = []
        async for item_res in await crawler.arun_many(box, run_config.clone()):
            # print(item_res.url)
            if item_res.html == '':

                continue
            root = html.fromstring(item_res.html)
            # 建议使用这个正则，它可以过滤掉引号
            pattern = r"hlsUrl\s*=\s*'(.*?\.m3u8)'"
            title = root.xpath('//*[@class="header-left"]/h4/text()')
            title = title[0] if len(title) > 0 else ''
            wcount = root.xpath('//*[@class="mr-3"][2]/text()')
            wcount = wcount[0] if len(wcount) > 0 else '0'
            likecount = root.xpath('//span[@class="count"]/text()')
            likecount = likecount[0] if len(likecount) > 0 else '0'
            img = root.xpath('//video[1]/@poster')
            img = img[0] if len(img) > 0 else ''
            match = re.search(pattern, item_res.html)

            if match:
                m3u8_link = match.group(1)
                # print(f"提取到的链接: {m3u8_link}")
                print((title, wcount, likecount, img))
                urls_links.append([title, wcount, likecount, img, m3u8_link])


            else:
                print("未匹配到链接")
        await crawler.close()
        await crawler.crawler_strategy.close()
        await crawler.crawler_strategy.browser_manager.close()


    end_time = time.perf_counter() - start_time
    print(f'耗时 ---{end_time}')

    if len(urls_links) > 0:
        print(f"一共 {len(urls_links)}")
        result_links = _sort_urls_links(urls_links)
        if len(result_links) > 15 and redis:
            await redis.setex(cache_url, 7200, json.dumps(result_links))
            await redis.aclose()
        return {"message": result_links}

    if redis:
        await redis.aclose()
    av_failure_count = av_failure_count + 1

    if av_failure_count >= 3:
        av_failure_count = 0
        background_tasks.add_task(trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, WORKFLOW_FILE, inputs={"reason": "Python API 触发"}))

    return {"message": []}


def _sort_urls_links(urls_links):
    """
    对二维数组 urls_links 按内部数组下标1的数字（字符串/数字）降序排序
    :param urls_links: 待排序的二维数组
    :return: 排序后的新数组（原数组不变）
    """

    def get_sort_key(item):
        """自定义排序key：提取下标1的元素并转为数字，处理异常"""
        try:
            # 确保能取到下标1的元素，且能转为浮点数（兼容整数/小数）
            value = item[1]
            # 如果是字符串，先去除首尾空格再转换
            if isinstance(value, str):
                value = value.replace(' ', '')
            return float(value)
        except (IndexError, ValueError):
            # 下标越界/非数字时，返回最小的数（排到最后）
            return float('-inf')

    # 用sorted排序，reverse=True降序，key指定排序依据
    sorted_list = sorted(urls_links, key=get_sort_key, reverse=True)
    return sorted_list

async def _handleSearchAV(background_tasks,q, cache):

    if q == '':
        return {"message": []}

    if q.isdigit():
        return await _handleHotAv(background_tasks, q, cache)

    return {"message": []}


@app.get("/search")
async def root(request: Request, background_tasks: BackgroundTasks, q: str, cache: bool = True, isKVM: bool = True, isAV: bool = False):
    print('ip', request.client.host)
    print(q)

    if isAV:
        return await _handleSearchAV(background_tasks, q, cache)

    if isKVM:
        return await _handleSearchKVM(q, cache)

    cache_url = f"https://v.ikanbot.com/search?q={q}"
    redis, data = await _getCacheData(cache_url)
    if redis and data:
        await redis.aclose()
        return {"message": data}

    browser_config = BrowserConfig(headless=True, text_mode=True, light_mode=True)

    run_config1 = CrawlerRunConfig()
    run_config1.cache_mode = CacheMode.ENABLED if cache else CacheMode.WRITE_ONLY
    run_config = CrawlerRunConfig()
    run_config.wait_for = 'li:has-text("线路1")'
    run_config.wait_for_timeout = 10000
    run_config.cache_mode = CacheMode.ENABLED if cache else CacheMode.WRITE_ONLY

    if cache:
        await asyncio.sleep(0.1)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result: CrawlResult = await crawler.arun(cache_url, config=run_config1)
        if len(result.html) == 0: return {"message": "0"}
        root = html.fromstring(result.html)
        links = root.xpath('//*[@class="media-heading"]/a/@href')
        # print(links)
        if len(links) > 0:
            detail_link = "https://v.ikanbot.com" + links[0]
            res: CrawlResult = await crawler.arun(detail_link, config=run_config)
            # print(res.html)
            root2 = html.fromstring(res.html)

            lines = root2.xpath('//*[@class="mar-top-10"]')
            m3u8links = []
            datas = []
            for line in lines:
                datas = line.xpath('(.//*[@class="line-res"])//div[@name="lineData"]/@udata')
                m3u8links.append(datas)

            # print(m3u8links)
            print("线路 ", len(m3u8links))

            print("集数 ", len(m3u8links[0]))
            if redis:
                await redis.setex(cache_url, 3600 * 6, json.dumps(m3u8links))
                await redis.aclose()
            return {"message": m3u8links}
        else:
            if redis:
                await redis.aclose()
            return {"message": []}
@app.get("/danmu")
async def danmu(request: Request, q: str, page: int =0, size: int = 0):
    print(q, str)
    print('ip', request.client.host)
    async with httpx.AsyncClient() as client:
        res = await client.get("https://jokkad-danmu-api.hf.space/123456/api/v2/search/episodes", params={
            "anime": q
        }, timeout=25)
        obj = res.json()
        print('剧集加载成功')
        if obj.get("success", None):
            animes = obj.get("animes", [])
            if animes and len(animes) > 0:
                anime = animes[0]
                episodes = anime.get("episodes", [])
                if size > 0 and size > len(episodes):
                    for item_anime in animes:
                        if item_anime.get("episodes", []) and len(item_anime.get("episodes", [])) + 1 >= size: # -1 适配大风打更人只有39集我擦了
                            episodes = item_anime.get("episodes", [])
                            break
                if episodes and len(episodes) > 0 and page < len(episodes):
                    episode = episodes[page]
                    id = episode.get("episodeId", "")
                    print(f'剧集id {id}')
                    if id > 0:
                        res = await client.get(f"https://jokkad-danmu-api.hf.space/123456/api/v2/comment/{id}", timeout=32)
                        obj = res.json()
                        print('弹幕加载成功')
                        print(len(obj.get("comments", [])))
                        if obj.get("comments", None) and len(obj.get("comments", [])) > 0:

                            def parse_danmaku(item):
                                p_parts = item['p'].split(',')

                                # 颜色处理：确保转为 hex 且补齐 6 位
                                # 注意：如果发现颜色不对，请检查是否应该用 p_parts[3]
                                decimal_color = int(p_parts[2])
                                hex_color = f"#{decimal_color:06x}"

                                # 模式映射：推荐使用字符串，而非数字
                                mode = int(p_parts[1])
                                # 1为滚动(right)，其他暂定为底部(bottom)
                                d_type = 'right' if mode == 1 else 'bottom'

                                return [
                                    item.get('t'),
                                    d_type,
                                    hex_color,
                                    p_parts[3] if len(p_parts) > 3 else 'User',
                                    item.get('m')


                                ]

                            # 使用列表推导式一行生成结果
                            formatted_danmaku = [parse_danmaku(item) for item in obj.get("comments", [])[0:50001]]

                            return {"data": formatted_danmaku, "code": 0}
                        else:
                            return {"message": "0"}
                    return {"message": "0"}
                else:
                    return {"message": "0"}
            else:
                return {"message": "0"}
        else:
            return {"message": "0"}

@app.get("/trigger")
async def triggle_actions(background_task: BackgroundTasks):

    background_task.add_task(trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, WORKFLOW_FILE, inputs={"reason": "Python API 触发"}))
    return {"message": "触发成功"}

def trigger_github_actions(
        token: str,
        owner: str,
        repo: str,
        workflow_id: str,
        branch: str = "main",
        inputs: dict = None
):
    """
    通过 API 触发 GitHub Actions 工作流
    :param token: GitHub PAT
    :param owner: 仓库所有者
    :param repo: 仓库名
    :param workflow_id: 工作流文件名/ID
    :param branch: 触发的分支
    :param inputs: 工作流入参（对应 workflow_dispatch 的 inputs）
    :return: 响应结果
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {
        "ref": branch,
        "inputs": inputs or {}
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 204:
        print("工作流触发成功！")
        return lambda : True
    else:
        print(f"触发失败：{response.status_code} - {response.text}")
        return lambda : False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5173)