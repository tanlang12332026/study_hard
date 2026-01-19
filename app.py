import json
import re
import sys
import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from crawl4ai import AsyncWebCrawler, CrawlResult, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, \
    RateLimiter
from lxml import html
import httpx
from parsel import Selector
from starlette.middleware.gzip import GZipMiddleware

from fake_useragent import FakeUserAgent

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.add_middleware(GZipMiddleware, minimum_size=666)

fake = FakeUserAgent()


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
                "DVAJ-726 彼女が3日間家族旅行で家を空けるというので、彼女の友達と3日間ハメまくった記録（仮） 宍戶里帆",
                "223 828",
                "1402",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56167/preview.jpg",
                "https://honi-moly-yami.mushroomtrack.com/hls/16p6j3GgHtTvx00KfFQFmQ/1768755883/56000/56167/56167.m3u8"
            ],
            [
                "ADN-750 無法原諒的女子 這女人不管欺負幾次為什麼都接受我… 星宮一花",
                "268 895",
                "2146",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56145/preview.jpg",
                "https://asf-doc.mushroomtrack.com/hls/EBhUonCTcXZX2Z6qZjIFeA/1768755851/56000/56145/56145.m3u8"
            ],
            [
                "IPZZ-728 去女友家過夜，結果一喝醉就變成接吻魔的女朋友的美乳辣妹姊姊色誘我…就在女友旁邊，被口水直流的貼身舌吻性愛弄到勃起停不下來，被無套內射榨取了18發的我 西宮夢",
                "214 022",
                "2985",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56216/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/U7dgKcBvO_OdkK2FOlGwSA/1768755836/56000/56216/56216.m3u8"
            ],
            [
                "CAWD-916 和乖乖安靜的女學生，穿著制服就無套內射打炮，真是畜生老師 谷村凪咲",
                "215 313",
                "1205",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56179/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/L41pX2RapjHOUXWh_f_Lqg/1768756370/56000/56179/56179.m3u8"
            ],
            [
                "DASS-833 路上で酔いつぶれ…汚い野良オトコ共達に拉致られヤク漬けに…中出し何発でもOK！キマってエビ反り昇天！絶対逃げられない！みんなの公共肉便器 葉月真由",
                "235 226",
                "1035",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56122/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/OuCd_8kCQDCkLE07GcKv8w/1768755975/56000/56122/56122.m3u8"
            ],
            [
                "DVAJ-725 娘が脱ぎ散らかした制服をこっそり着ていた妻と鉢合わせ サイズの合わないムチパツ姿で恥じらうのがエロ可愛すぎて10数年ぶり学生気分に戻ってハメまくった 有岡みう",
                "220 677",
                "1876",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56166/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/2kn-ItzvF-kBSGZ89QYHxQ/1768755731/56000/56166/56166.m3u8"
            ],
            [
                "IPZZ-748 氣質滿滿的美人姊姊散發費洛蒙 口水橫流把勃起的雞雞啃到一滴不剩，最棒的口交顏射 三澄寧寧",
                "237 867",
                "3602",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56220/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/9cdFO49q2alkMRjXGdf_3g/1768756552/56000/56220/56220.m3u8"
            ],
            [
                "DASS-821 時間暫停！對著夢寐以求的美巨乳女主播 惡劣痴漢 把勃起的雞雞摩擦 不小心無套內射了 白峰美羽",
                "206 994",
                "3549",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56224/preview.jpg",
                "https://adoda-smart-coin.mushroomtrack.com/hls/09WiXbqP13Ct08cGmXPOFw/1768755937/56000/56224/56224.m3u8"
            ],
            [
                "ADN-742 「老公，對不起……」巨乳人妻的真面目 蘆名穗花",
                "276 847",
                "2337",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56142/preview.jpg",
                "https://asf-doc.mushroomtrack.com/hls/lrRIKivpiOiKxG-1CAYNWw/1768756327/56000/56142/56142.m3u8"
            ],
            [
                "JUR-535 毎晩旦那とヤリまくる絶倫叔母と一泊二日の搾精旅行 ヌカれまくって性に目覚めた童貞の僕は… すべて忘れて連続中出し交尾にハマってしまった。 白石茉莉奈",
                "193 681",
                "1629",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56126/preview.jpg",
                "https://adoda-smart-coin.mushroomtrack.com/hls/uinqGCnK1RXkC8E3vcn5Ag/1768755720/56000/56126/56126.m3u8"
            ],
            [
                "MKMP-698 女子アナ上納システムの実態 某テレビ局のアナウンサーが男性タレントの食い物にされた性被害の悲劇 尾崎惠梨香",
                "238 578",
                "1565",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56170/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/b2Fq5RUw8C0nCFZAAT9xpw/1768755781/56000/56170/56170.m3u8"
            ],
            [
                "JUR-590 NTR肉串輪● 把我最愛的巨乳老婆猛烈幹下去 橘瑪麗",
                "198 096",
                "2942",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56231/preview.jpg",
                "https://asf-doc.mushroomtrack.com/hls/65RSDp0Z-MAsk8s2hqtZfQ/1768755998/56000/56231/56231.m3u8"
            ],
            [
                "JUR-565 「人生最後の勃起かもしれないんだ、一瞬だけでイイから挿れさせて！！」 勃起不全になった義父に同情して混浴したらまさかのフル勃起、相性抜群過ぎて馬乗り騎乗位で何度も生ハメ狂ってしまった私。 市來真尋",
                "223 936",
                "1283",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56127/preview.jpg",
                "https://asf-doc.mushroomtrack.com/hls/sL5TyxWrEJI_K6gKKV-7qQ/1768756059/56000/56127/56127.m3u8"
            ],
            [
                "ROYD-280 早上起來房間裡出現了一位浴衣都沒有穿好的後輩女同事！平常都對我很兇，不知道為什麼現在對我撒嬌... 黑島玲衣",
                "533 694",
                "5555",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56054/preview.jpg",
                "https://astin-cowing.mushroomtrack.com/hls/m8dlrciq9cY4EqktXlj78Q/1768755774/56000/56054/56054.m3u8"
            ],
            [
                "MVSD-662 沒想到幹練的巨乳OL女前輩會做這麼瘋狂的奶頭性愛！ 北野未奈",
                "1 164 613",
                "11080",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/55000/55908/preview.jpg",
                "https://hot-box-gen.mushroomtrack.com/hls/UpY7UhhWB9B3JC1XZ-C34g/1768755904/55000/55908/55908.m3u8"
            ],
            [
                "ROYD-278 幾年前學生時期強●我的那些男人，再次出現在眼前。剛從監獄出來的拷●魔，從早到晚對巨乳OL進行雙重播種內射壓制輪●… 北野未奈",
                "627 197",
                "4567",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56052/preview.jpg",
                "https://asf-doc.mushroomtrack.com/hls/rJd8zBpvFRLA0yz4ehJaWg/1768755774/56000/56052/56052.m3u8"
            ],
            [
                "SNOS-050 彼女、彼女の妹との温泉旅行で妹の方が二人きりになるたびに甘え密着ボディタッチからのおねだりキッス、 たまらず勃起するとジュボジュボしゃぶり始め暴発寸前チ●ポを色んな体位でハメてきて意のままに大量射精しちゃう恥ずかしい僕。 川越仁子",
                "207 845",
                "1825",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56109/preview.jpg",
                "https://home-clone-clear.mushroomtrack.com/hls/Y2joD7d_Vda4qfLw5sA3oQ/1768756549/56000/56109/56109.m3u8"
            ],
            [
                "START-480 どえっっろい素SEX解禁！ ホントはめっちゃキスが好きな小笠原菜乃の休日デートSEX 小笠原菜乃",
                "220 128",
                "1806",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56198/preview.jpg",
                "https://anono-cloneing.mushroomtrack.com/hls/aY2GwSFwP--bLQ1LtFLSvA/1768755837/56000/56198/56198.m3u8"
            ],
            [
                "SNOS-030 わたし、教え子たちに逆らえず 身動き取れない状態で飼われています。 明日葉三葉",
                "236 329",
                "3519",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56103/preview.jpg",
                "https://honi-moly-yami.mushroomtrack.com/hls/YBmGp5l7G839q9LCiG-6_A/1768756211/56000/56103/56103.m3u8"
            ],
            [
                "WAAA-594 「在我說可以之前不准給我射喔！」抓住普通抖M男子，玩弄他的奶頭！極限打手槍美巨乳痴女的無套性交散步 春陽萌花",
                "192 983",
                "1937",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56213/preview.jpg",
                "https://anono-cloneing.mushroomtrack.com/hls/Mrpkhq1UkiabZxKy6iFQlQ/1768756249/56000/56213/56213.m3u8"
            ],
            [
                "VDD-200 W脅迫スイートルーム 女医＆女性経営者in… 新村晶 北野未奈",
                "763 478",
                "7063",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56021/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/6FY9XZBwzBGc4QJzlwwM5w/1768756388/56000/56021/56021.m3u8"
            ],
            [
                "START-494 3ヶ月前に出会った絶対挿入禁止の既婚者オナトモW不倫で、極限焦らしを超えた最初で最後の発情無制限中出しSEX。 小倉由菜",
                "205 811",
                "1157",
                "https://assets-cdn.jable.tv/contents/videos_screenshots/56000/56199/preview.jpg",
                "https://akuma-trstin.mushroomtrack.com/hls/LqZfYrisDT6C1gQkxsSADg/1768756200/56000/56199/56199.m3u8"
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
    start_time = time.perf_counter()
    browser_config = BrowserConfig(headless=True, text_mode=True, light_mode=True)
    run_config1 = CrawlerRunConfig()
    run_config1.cache_mode = CacheMode.ENABLED if cache else CacheMode.WRITE_ONLY

    run_config2 = CrawlerRunConfig(capture_network_requests = True)
    run_config2.cache_mode =  CacheMode.WRITE_ONLY

    # run_config2.delay_before_return_html = 2
    urls = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result: CrawlResult = await crawler.arun(f"https://www.4kvm.org/xssearch?s={q}", config=run_config1)
        # print(result.html)
        if len(result.html) == 0:
            return {"message": "0"}
        root = html.fromstring(result.html)
        link = root.xpath('//div[@class="result-item"][1]//a/@href')
        link = link[0] if len(link) > 0 else None
        if link is None:
            return {"message": "0"}
        result: CrawlResult = await crawler.arun(link, config=run_config1)
        root = html.fromstring(result.html)
        link = root.xpath('//*[@class="se-q"]/a[1]/@href')
        link = link[0] if len(link) > 0 else None
        if link is None:
            return {"message": "0"}
        # 视频详情页
        result: CrawlResult = await crawler.arun(link, config=run_config1)
        root = html.fromstring(result.html)

        links = root.xpath('//*[@class="jujiepisodios"]/a/text()')
        link = root.xpath('//iframe/@src')

        link = link[0] if len(link) > 0 else None
        if link is None:
            return {"message": "0"}

        tasks = []
        for i in links:
            sps = link.split('&')
            sing_link = sps[0] + '&' + sps[1] + '&' + 'ep=' + i
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
        return {"message": [urls]}
    return {"message": "0"}

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


async def _handleHotAv(q, cache):
    num = int(q)
    start_time = time.perf_counter()
    if num > 1477 or num < 0:
        return {"message": []}
    time_now = int(time.time() * 1000)
    url = f"https://jable.tv/hot/{num}/?mode=async&function=get_block&block_id=list_videos_common_videos_list&sort_by=video_viewed&_={time_now}"

    # return _tmp()
    urls_links = []
    browser_config = BrowserConfig()
    browser_config.headless = True
    browser_config.enable_stealth = True
    browser_config.browser_mode = 'docker'
    # browser_config.text_mode = True
    browser_config.user_agent_mode = 'random'

    run_config = CrawlerRunConfig()
    run_config.verbose = False
    run_config.stream = True

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
        print(urls_links)
        if len(urls_links) == 0:
            return {"message": []}


    end_time = time.perf_counter() - start_time
    print(f'耗时 ---{end_time}')

    if len(urls_links) > 0:
        print(f"一共 {len(urls_links)}")
        return {"message": _sort_urls_links(urls_links)}
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
                value = value.strip()
            return float(value)
        except (IndexError, ValueError):
            # 下标越界/非数字时，返回最小的数（排到最后）
            return float('-inf')

    # 用sorted排序，reverse=True降序，key指定排序依据
    sorted_list = sorted(urls_links, key=get_sort_key, reverse=True)
    return sorted_list

async def _handleSearchAV(q, cache):

    if q == '':
        return {"message": []}

    if q.isdigit():
        return await _handleHotAv(q, cache)

    return {"message": []}


@app.get("/search")
async def root(request: Request, q: str, cache: bool = True, isKVM: bool = True, isAV: bool = False):
    print('ip', request.client.host)
    print(q)

    if isAV:
        return await _handleSearchAV(q, cache)

    if isKVM:
        return await _handleSearchKVM(q, cache)

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
        result: CrawlResult = await crawler.arun(f"https://v.ikanbot.com/search?q={q}", config=run_config1)
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

            return {"message": m3u8links}
        else:
            return {"message": "not found"}
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



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5173)