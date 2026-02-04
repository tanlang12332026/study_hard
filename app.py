import base64
import json
import os


# 如果环境变量里有这个“错误的路径”，就把它删掉
if "SSL_CERT_FILE" in os.environ:
    del os.environ["SSL_CERT_FILE"]


import random
import re
import sys
import asyncio
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response
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
is_reload_av02 = False
is_reload_av03 = False
MY_GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") if os.getenv("MY_GITHUB_TOKEN") else ""
REPO_OWNER = "tanlang12332026"
REPO_NAME = "study_hard"
WORKFLOW_FILE = os.getenv("WORKFLOW_FILE") if os.getenv("WORKFLOW_FILE") else "danmu.yaml"

async def delayed_trigger():

    extra_time = [1, 3 , 5, 7]

    extra_time = random.choice(extra_time)

    await asyncio.sleep(60 *6*(20 + extra_time))
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
            await redis.setex(cache_url, 3600 * 3, json.dumps([urls]))
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

async def _getDataFromOtherServer(q,cache, server_name)  -> dict:
    print(f'正在从备用服务器请求数据 --- {server_name}', flush=True)
    url = f"https://{server_name}.xiaodu1234.xyz/search?q={q}&isKVM={False}&isAV={True}&cache={cache}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=55)
            print(f"备用服务器 -- {server_name} 请求数据成功")
            return res.json()
    except Exception as e:
        print(f"备用服务器 -- {server_name} 请求数据失败", e)
        return {"message": []}

async def _sleep02(background_tasks):
    global is_reload_av02
    await asyncio.sleep(60 * 2)
    is_reload_av02 = False
    background_tasks.add_task(
        trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, "danmu03.yaml"))

async def _sleep03():
    global is_reload_av03
    await asyncio.sleep(60 * 2)

    is_reload_av03 = False


async def _handleHotAv_search(background_tasks, q, cache):
    return await _handleHotAv_h5(background_tasks, q, cache, isSearch=True)

async def _handleHotAv_h5(background_tasks, q, cache, isSearch=False):
    start_time = time.perf_counter()
    time_now = int(time.time() * 1000)
    url = ''
    cache_url = ''
    if not isSearch:
        num = int(q)
        url = f"https://jable.tv/hot/{num}/?mode=async&function=get_block&block_id=list_videos_common_videos_list&sort_by=video_viewed&_={time_now}"
        cache_url = f"https://jable.tv/hot/{num}/"
        if num > 1477 or num < 0:
            return {"message": []}
    else:
        url = f"https://jable.tv/search/{q}/"
        cache_url = url

    redis, data = await _getCacheData(cache_url)
    if redis and data:
        await redis.aclose()
        return {"message": data}

    async with httpx.AsyncClient() as client:
        print(url, flush=True)
        res = await client.get(url, timeout=10)
        # print(res.content)
        root = Selector(text=str(res.content))
        box = root.css('div.img-box.cover-md a::attr(href)').getall()
        print(box, flush=True)

        tasks = []
        urls_links = []
        for url in box:
            task = asyncio.create_task(client.get(url, timeout=10))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item_res in results:
            if item_res.text == '':
                continue
            root = html.fromstring(item_res.text)
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
            match = re.search(pattern, item_res.text)

            if match:
                m3u8_link = match.group(1)
                # print(f"提取到的链接: {m3u8_link}")
                print((title, wcount, likecount, img))
                urls_links.append([title, wcount, likecount, img, m3u8_link])
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
        return {"message": []}

async def _handleHotAv(background_tasks, q, cache):
    global av_failure_count
    global is_reload_av02
    global is_reload_av03
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
    if WORKFLOW_FILE == 'danmu.yaml' and av_failure_count > 0:
        # 去另外服务器获取数据
        print(f'正在从备用服务器请求数据 ---', flush=True)
        data:dict = await _getDataFromOtherServer(q, cache,"av02")
        datas = data.get('message', [])
        if len(datas) > 0:
            return {"message": datas}
        else:
            if not is_reload_av02 :
                print('正在重启服务器02')
                background_tasks.add_task(trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, "danmu02.yaml",
                                                                 inputs={"reason": "Python API 触发"}))
                asyncio.create_task(_sleep02(background_tasks))
                is_reload_av02 = True
            data: dict = await _getDataFromOtherServer(q, cache,"av03")
            datas = data.get('message', [])
            if len(datas) > 0:
                return {"message": datas}
            else:
                if not is_reload_av03:
                    print('正在重启服务器03')
                    background_tasks.add_task(
                        trigger_github_actions(MY_GITHUB_TOKEN, REPO_OWNER, REPO_NAME, "danmu03.yaml",
                                               inputs={"reason": "Python API 触发"}))
                    asyncio.create_task(_sleep03())
                    is_reload_av03 = True

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

    if av_failure_count >= 3 and WORKFLOW_FILE != 'danmu.yaml':
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
        return await _handleHotAv_h5(background_tasks, q, cache)

    return await _handleHotAv_search(background_tasks, q, cache)


async def _handleKanXiGe(q, cache):
    if q == '':
        return {"message": []}
    base_url = "https://www.kanxige.com"
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{base_url}/search/-------------.html?wd={q}&submit=")
        print(res.text)
        root = Selector(res.text)
        box = root.xpath('//*[@class="stui-vodlist__box"]')
        boxs = []
        for item in box:
            ref = base_url + item.xpath('./a[1]/@href').get()
            title = item.xpath('./a[1]/@title').get()
            img = item.xpath('./a[1]/@data-original').get()
            print(ref, title, img)
            boxs.append({
                'title': title,
                'img': img,
                'ref': ref,
            })
    return {"message": boxs}
@app.get("/search")
async def root(request: Request, background_tasks: BackgroundTasks, q: str, cache: bool = True, isKVM: bool = True, isAV: bool = False, isKanXiGe: bool = False):
    print('ip', request.client.host)
    print(q)

    if isAV:
        return await _handleSearchAV(background_tasks, q, cache)

    if isKVM:
        return await _handleSearchKVM(q, cache)

    if isKanXiGe:
        return await _handleKanXiGe(q,cache)

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

@app.get("/sub")
async def sub(request: Request):
    print(request.client.host)
    async with httpx.AsyncClient() as client:
        res = await client.post('https://api.hostmonit.com/get_optimization_ip', json={
            "key": "iDetkOys"
        })
        ips = res.json().get('info', [])
        ips = [ip['ip'] for ip in ips]
        print(ips)
        print(len(ips))
        # bs = """
        # dmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAc3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6OjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU1JThFJTlGJUU3JTk0JTlGJUU1JTlDJUIwJUU1JTlEJTgwLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAc3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU1JThFJTlGJUU3JTk0JTlGJUU1JTlDJUIwJUU1JTlEJTgwLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNsb3VkZmxhcmUuMTgyNjgyLnh5ejo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Nsb3VkZmxhcmUuMTgyNjgyLnh5ei00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNsb3VkZmxhcmUuMTgyNjgyLnh5ejo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Nsb3VkZmxhcmUuMTgyNjgyLnh5ei04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBzcGVlZC5tYXJpc2FsbmMuY29tOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjc3BlZWQubWFyaXNhbG5jLmNvbS00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQHNwZWVkLm1hcmlzYWxuYy5jb206ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNzcGVlZC5tYXJpc2FsbmMuY29tLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGZyZWV5eC5jbG91ZGZsYXJlODguZXUub3JnOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjZnJlZXl4LmNsb3VkZmxhcmU4OC5ldS5vcmctNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBmcmVleXguY2xvdWRmbGFyZTg4LmV1Lm9yZzo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2ZyZWV5eC5jbG91ZGZsYXJlODguZXUub3JnLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGJlc3RjZi50b3A6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNiZXN0Y2YudG9wLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAYmVzdGNmLnRvcDo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Jlc3RjZi50b3AtODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2RuLjIwMjAxMTEueHl6OjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2RuLjIwMjAxMTEueHl6LTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2RuLjIwMjAxMTEueHl6OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2RuLjIwMjAxMTEueHl6LTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNmaXAuY2ZjZG4udmlwOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2ZpcC5jZmNkbi52aXAtNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjZmlwLmNmY2RuLnZpcDo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmaXAuY2ZjZG4udmlwLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNmLjBzbS5jb206NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjZi4wc20uY29tLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2YuMHNtLmNvbTo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmLjBzbS5jb20tODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2YuMDkwMjI3Lnh5ejo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmLjA5MDIyNy54eXotNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjZi4wOTAyMjcueHl6OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2YuMDkwMjI3Lnh5ei04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjZi56aGV0ZW5nc2hhLmV1Lm9yZzo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmLnpoZXRlbmdzaGEuZXUub3JnLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2YuemhldGVuZ3NoYS5ldS5vcmc6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjZi56aGV0ZW5nc2hhLmV1Lm9yZy04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjbG91ZGZsYXJlLjlqeS5jYzo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Nsb3VkZmxhcmUuOWp5LmNjLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2xvdWRmbGFyZS45ankuY2M6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjbG91ZGZsYXJlLjlqeS5jYy04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjZi56ZXJvbmUtY2RuLnBwLnVhOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2YuemVyb25lLWNkbi5wcC51YS00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNmLnplcm9uZS1jZG4ucHAudWE6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjZi56ZXJvbmUtY2RuLnBwLnVhLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNmaXAuMTMyMzEyMy54eXo6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjZmlwLjEzMjMxMjMueHl6LTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2ZpcC4xMzIzMTIzLnh5ejo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmaXAuMTMyMzEyMy54eXotODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY25hbWVmdWNreHhzLnl1Y2hlbi5pY3U6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjbmFtZWZ1Y2t4eHMueXVjaGVuLmljdS00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNuYW1lZnVja3h4cy55dWNoZW4uaWN1OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY25hbWVmdWNreHhzLnl1Y2hlbi5pY3UtODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2xvdWRmbGFyZS1pcC5tb2Zhc2hpLmx0ZDo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Nsb3VkZmxhcmUtaXAubW9mYXNoaS5sdGQtNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjbG91ZGZsYXJlLWlwLm1vZmFzaGkubHRkOjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2xvdWRmbGFyZS1pcC5tb2Zhc2hpLmx0ZC04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMTUxNTUueHl6OjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjMTE1MTU1Lnh5ei00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDExNTE1NS54eXo6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMxMTUxNTUueHl6LTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNuYW1lLnhpcmFuY2RuLnVzOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY25hbWUueGlyYW5jZG4udXMtNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjbmFtZS54aXJhbmNkbi51czo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NuYW1lLnhpcmFuY2RuLnVzLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGYzMDU4MTcxY2FkLjAwMjQwNC54eXo6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNmMzA1ODE3MWNhZC4wMDI0MDQueHl6LTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAZjMwNTgxNzFjYWQuMDAyNDA0Lnh5ejo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2YzMDU4MTcxY2FkLjAwMjQwNC54eXotODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAOC44ODkyODgueHl6OjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjOC44ODkyODgueHl6LTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAOC44ODkyODgueHl6OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjOC44ODkyODgueHl6LTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQGNkbi50enByby54eXo6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCNjZG4udHpwcm8ueHl6LTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2RuLnR6cHJvLnh5ejo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2Nkbi50enByby54eXotODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAY2YuODc3NzcxLnh5ejo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4I2NmLjg3Nzc3MS54eXotNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUBjZi44Nzc3NzEueHl6OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjY2YuODc3NzcxLnh5ei04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUB4bi0tYjZnYWMuZXUub3JnOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjeG4tLWI2Z2FjLmV1Lm9yZy00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQHhuLS1iNmdhYy5ldS5vcmc6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCN4bi0tYjZnYWMuZXUub3JnLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE3Mi42NC4yMjkuMjUxOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JUE3JUJCJUU1JThBJUE4LUhLRy00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE3Mi42NC4yMjkuMjUxOjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JUE3JUJCJUU1JThBJUE4LUhLRy04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDQuMTYuODcuMTcyOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JUE3JUJCJUU1JThBJUE4LVNKQy00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDEwNC4xNi44Ny4xNzI6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclQTclQkIlRTUlOEElQTgtU0pDLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDEwNC4xOC44Mi4xNjM6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclQTclQkIlRTUlOEElQTgtSEtHLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTA0LjE4LjgyLjE2Mzo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyVBNyVCQiVFNSU4QSVBOC1IS0ctODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS43LjMwOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JUE3JUJCJUU1JThBJUE4LUxBWC00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNy4zMDo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyVBNyVCQiVFNSU4QSVBOC1MQVgtODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS40MC4xMDI6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclQTclQkIlRTUlOEElQTgtTEFYLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS40MC4xMDI6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclQTclQkIlRTUlOEElQTgtTEFYLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNDQuMTc5OjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLUxBWC00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNDQuMTc5OjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLUxBWC04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDQuMTYuODcuMTcyOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLVNKQy00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDEwNC4xNi44Ny4xNzI6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTglODElOTQlRTklODAlOUEtU0pDLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNDQuMTAyOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLUxBWC00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNDQuMTAyOjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLUxBWC04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDQuMTYuNDQuMjA6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTglODElOTQlRTklODAlOUEtU0pDLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTA0LjE2LjQ0LjIwOjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU4JTgxJTk0JUU5JTgwJTlBLVNKQy04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDQuMTYuMTY5LjExNjo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFOCU4MSU5NCVFOSU4MCU5QS1TSkMtNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDQuMTYuMTY5LjExNjo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFOCU4MSU5NCVFOSU4MCU5QS1TSkMtODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTk4LjQxLjIyMy4xMzc6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclOTQlQjUlRTQlQkYlQTEtU0lOLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTk4LjQxLjIyMy4xMzc6ODA/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PW5vbmUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclOTQlQjUlRTQlQkYlQTEtU0lOLTgwLVdTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNS4xMTc6NDQzP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT10bHMmc25pPXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZmcD1jaHJvbWUmdHlwZT13cyZob3N0PXNwZWVkdGVzdC54aWFvZHUxMjM0Lnh5eiZwYXRoPSUyRiUzRmVkJTNEMjA0OCMlRTclOTQlQjUlRTQlQkYlQTEtU0lOLTQ0My1XUy1UTFMKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS41LjExNzo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyU5NCVCNSVFNCVCRiVBMS1TSU4tODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS43LjMwOjQ0Mz9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9dGxzJnNuaT1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomZnA9Y2hyb21lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JTk0JUI1JUU0JUJGJUExLVNJTi00NDMtV1MtVExTCnZsZXNzOi8vYjc5YmM4Y2YtMmJiZi00N2U3LTg2ZDgtMmVmMDQ1NjcyYzNlQDE2Mi4xNTkuNy4zMDo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyU5NCVCNSVFNCVCRiVBMS1TSU4tODAtV1MKdmxlc3M6Ly9iNzliYzhjZi0yYmJmLTQ3ZTctODZkOC0yZWYwNDU2NzJjM2VAMTYyLjE1OS4zMy44Mjo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyU5NCVCNSVFNCVCRiVBMS1TSU4tNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxNjIuMTU5LjMzLjgyOjgwP2VuY3J5cHRpb249bm9uZSZzZWN1cml0eT1ub25lJnR5cGU9d3MmaG9zdD1zcGVlZHRlc3QueGlhb2R1MTIzNC54eXomcGF0aD0lMkYlM0ZlZCUzRDIwNDgjJUU3JTk0JUI1JUU0JUJGJUExLVNJTi04MC1XUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDguMTYyLjE5My4yMTo0NDM/ZW5jcnlwdGlvbj1ub25lJnNlY3VyaXR5PXRscyZzbmk9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JmZwPWNocm9tZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyU5NCVCNSVFNCVCRiVBMS1TSU4tNDQzLVdTLVRMUwp2bGVzczovL2I3OWJjOGNmLTJiYmYtNDdlNy04NmQ4LTJlZjA0NTY3MmMzZUAxMDguMTYyLjE5My4yMTo4MD9lbmNyeXB0aW9uPW5vbmUmc2VjdXJpdHk9bm9uZSZ0eXBlPXdzJmhvc3Q9c3BlZWR0ZXN0LnhpYW9kdTEyMzQueHl6JnBhdGg9JTJGJTNGZWQlM0QyMDQ4IyVFNyU5NCVCNSVFNCVCRiVBMS1TSU4tODAtV1M=
        # """
        # origin = base64.b64decode(bs.encode('utf-8')).decode('utf-8')
        # print(origin)

        url = "vless://b79bc8cf-2bbf-47e7-86d8-2ef045672c3e@haha:443?encryption=none&security=tls&sni=speedtest.xiaodu1234.xyz&fp=chrome&type=ws&host=speedtest.xiaodu1234.xyz&path=%2F%3Fed%3D2048#%E5%8E%9F%E7%94%9F%E5%9C%B0%E5%9D%80-443-WS-TLS"
        targets = []
        for ip in ips:
            targets.append(url.replace('haha', ip.strip()))

        print(len(targets))
        ipstr = '\n'.join(targets)
        print(ipstr)

        return Response(
            content=base64.b64encode(ipstr.encode('utf-8')).decode('utf-8').strip(),
            media_type="text/plain; charset=utf-8"  # 核心：指定 content-type
        )

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