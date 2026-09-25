"""历史大赛数据源（奥运会 / 世锦赛 / 团体世锦赛 / 世界杯 / 团体世界杯 / 混合团体世界杯）。

赛事清单（年份、地点、官方 EventId）来自 ITTF 官方赛事数据库
（ittf-admin-api，与 worldtabletennis.com / ittf.com 同源）；
各项目决赛对阵（冠亚军）逐届与维基百科奖牌记录核对。
总比分与逐局比分来自官方通讯社 / 官方机构发布（新华社、央视、人民网、
中新网、ITTF 官网、奥运会官网等），未核实到权威来源的场次留空（不编造）。

每场大赛生成「决赛」比赛条目，便于搜索（按赛事名 / 年份 / 选手）；
比分字段格式：总分（冠军局数, 亚军局数）+ 逐局比分（冠军视角）。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from data_sources.base import DataSource
from data_sources.asian_games import AsianGamesFeed
from data_sources.major_team_results import TEAM_RESULTS, team_games
from models import Match, STATUS_FINISHED


CURRENT_MAJOR_CATEGORIES = frozenset(("奥运会", "世锦赛", "世界杯"))


class OfficialMajorFeed(Protocol):
    """未来接入已核实的官方当期接口时实现此协议；不凭赛历生成比分。"""

    category: str

    def get_matches(self) -> list[Match]: ...

    def get_match_detail(self, match_id: str) -> Match | None: ...


# 决赛条目：
# (项目, (冠军展示名, 冠军原文), (亚军展示名, 亚军原文), (总分冠军, 总分亚军)|None, [逐局比分(冠军视角)]|None)
# 团体赛未核实逐场对阵时仅填总分（sets=None）。
MAJOR_EVENTS: list[dict] = [
    # ================= 奥运会 =================
    {
        "id": 590, "type": "奥运会", "name_zh": "伦敦奥运会", "year": 2012,
        "start": "2012-07-28", "end": "2012-08-08", "city": "伦敦", "country": "英国",
        "finals": [
            ("男子单打", ("张继科", "Zhang Jike"), ("王皓", "Wang Hao"),
             (4, 1), [(18, 16), (11, 5), (11, 6), (10, 12), (13, 11)]),
            ("女子单打", ("李晓霞", "Li Xiaoxia"), ("丁宁", "Ding Ning"),
             (4, 1), [(11, 8), (14, 12), (8, 11), (11, 6), (11, 4)]),
            ("男子团体", ("中国", "China"), ("韩国", "South Korea"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 360, "type": "奥运会", "name_zh": "里约热内卢奥运会", "year": 2016,
        "start": "2016-08-06", "end": "2016-08-17", "city": "里约热内卢", "country": "巴西",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("张继科", "Zhang Jike"),
             (4, 0), [(14, 12), (11, 5), (11, 4), (11, 4)]),
            ("女子单打", ("丁宁", "Ding Ning"), ("李晓霞", "Li Xiaoxia"),
             (4, 3), [(11, 9), (5, 11), (14, 12), (9, 11), (8, 11), (11, 7), (11, 7)]),
            ("男子团体", ("中国", "China"), ("日本", "Japan"), (3, 1), None),
            ("女子团体", ("中国", "China"), ("德国", "Germany"), (3, 0), None),
        ],
    },
    {
        "id": 2345, "type": "奥运会", "name_zh": "东京奥运会", "year": 2020,
        "start": "2021-07-23", "end": "2021-08-08", "city": "东京", "country": "日本",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("樊振东", "Fan Zhendong"),
             (4, 2), [(11, 4), (10, 12), (11, 8), (11, 9), (3, 11), (11, 7)]),
            ("女子单打", ("陈梦", "Chen Meng"), ("孙颖莎", "Sun Yingsha"),
             (4, 2), [(9, 11), (11, 6), (11, 4), (5, 11), (11, 4), (11, 9)]),
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
            ("混合双打", ("水谷隼/伊藤美诚", "Jun Mizutani/Mima Ito"), ("许昕/刘诗雯", "Xu Xin/Liu Shiwen"),
             (4, 3), [(5, 11), (7, 11), (11, 8), (11, 9), (11, 9), (6, 11), (11, 6)]),
        ],
    },
    {
        "id": 2603, "type": "奥运会", "name_zh": "巴黎奥运会", "year": 2024,
        "start": "2024-07-26", "end": "2024-08-11", "city": "巴黎", "country": "法国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("莫雷加德", "Truls Moregard"),
             (4, 1), [(7, 11), (11, 9), (11, 9), (11, 8), (11, 8)]),
            ("女子单打", ("陈梦", "Chen Meng"), ("孙颖莎", "Sun Yingsha"),
             (4, 2), [(4, 11), (11, 7), (11, 4), (9, 11), (11, 9), (11, 6)]),
            ("男子团体", ("中国", "China"), ("瑞典", "Sweden"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
            ("混合双打", ("王楚钦/孙颖莎", "Wang Chuqin/Sun Yingsha"), ("李正植/金琴英", "Ri Jong-sik/Kim Kum-yong"),
             (4, 2), [(11, 6), (7, 11), (11, 8), (11, 5), (7, 11), (11, 8)]),
        ],
    },
    # ================= 世锦赛（单项） =================
    {
        "id": 765, "type": "世锦赛", "name_zh": "鹿特丹世锦赛", "year": 2011,
        "start": "2011-05-08", "end": "2011-05-15", "city": "鹿特丹", "country": "荷兰",
        "finals": [
            ("男子单打", ("张继科", "Zhang Jike"), ("王皓", "Wang Hao"),
             (4, 2), [(12, 10), (11, 7), (6, 11), (9, 11), (11, 5), (14, 12)]),
            ("女子单打", ("丁宁", "Ding Ning"), ("李晓霞", "Li Xiaoxia"),
             (4, 2), [(12, 10), (13, 11), (11, 9), (8, 11), (8, 11), (11, 7)]),
            ("混合双打", ("张超/曹臻", "Zhang Chao/Cao Zhen"), ("郝帅/木子", "Hao Shuai/Mu Zi"),
             (4, 1), [(11, 7), (11, 7), (11, 9), (9, 11), (11, 8)]),
        ],
    },
    {
        "id": 599, "type": "世锦赛", "name_zh": "巴黎世锦赛", "year": 2013,
        "start": "2013-05-13", "end": "2013-05-20", "city": "巴黎", "country": "法国",
        "finals": [
            ("男子单打", ("张继科", "Zhang Jike"), ("王皓", "Wang Hao"),
             (4, 2), [(11, 7), (11, 8), (6, 11), (14, 12), (5, 11), (11, 7)]),
            ("女子单打", ("李晓霞", "Li Xiaoxia"), ("刘诗雯", "Liu Shiwen"),
             (4, 2), [(11, 8), (4, 11), (11, 7), (12, 10), (6, 11), (13, 11)]),
            ("混合双打", ("金赫峰/金仲", "Kim Hyok-bong/Kim Jong"), ("李尚洙/朴英淑", "Lee Sang-su/Park Young-sook"),
             (4, 2), [(11, 6), (11, 8), (11, 3), (6, 11), (8, 11), (11, 7)]),
        ],
    },
    {
        "id": 326, "type": "世锦赛", "name_zh": "苏州世锦赛", "year": 2015,
        "start": "2015-04-26", "end": "2015-05-03", "city": "苏州", "country": "中国",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("方博", "Fang Bo"),
             (4, 2), [(11, 7), (7, 11), (11, 4), (11, 8), (11, 13), (11, 4)]),
            ("女子单打", ("丁宁", "Ding Ning"), ("刘诗雯", "Liu Shiwen"),
             (4, 3), [(7, 11), (15, 13), (11, 7), (11, 9), (9, 11), (4, 11), (11, 8)]),
            ("混合双打", ("许昕/梁夏银", "Xu Xin/Yang Ha-eun"), ("吉村真晴/石川佳纯", "Maharu Yoshimura/Kasumi Ishikawa"),
             (4, 0), [(11, 7), (11, 8), (11, 4), (11, 6)]),
        ],
    },
    {
        "id": 472, "type": "世锦赛", "name_zh": "杜塞尔多夫世锦赛", "year": 2017,
        "start": "2017-05-29", "end": "2017-06-05", "city": "杜塞尔多夫", "country": "德国",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("樊振东", "Fan Zhendong"),
             (4, 3), [(7, 11), (11, 6), (11, 3), (11, 8), (5, 11), (7, 11), (12, 10)]),
            ("女子单打", ("丁宁", "Ding Ning"), ("朱雨玲", "Zhu Yuling"),
             (4, 2), [(11, 4), (9, 11), (4, 11), (12, 10), (11, 6), (11, 7)]),
            ("混合双打", ("吉村真晴/石川佳纯", "Maharu Yoshimura/Kasumi Ishikawa"), ("陈建安/郑怡静", "Chen Chien-an/Cheng I-ching"),
             (4, 3), [(8, 11), (8, 11), (11, 8), (10, 12), (11, 4), (11, 9), (11, 5)]),
        ],
    },
    {
        "id": 1987, "type": "世锦赛", "name_zh": "布达佩斯世锦赛", "year": 2019,
        "start": "2019-04-21", "end": "2019-04-28", "city": "布达佩斯", "country": "匈牙利",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("法尔克", "Mattias Falck"),
             (4, 1), [(11, 5), (11, 7), (7, 11), (11, 9), (11, 5)]),
            ("女子单打", ("刘诗雯", "Liu Shiwen"), ("陈梦", "Chen Meng"),
             (4, 2), [(9, 11), (11, 7), (11, 7), (7, 11), (11, 0), (11, 9)]),
            ("混合双打", ("许昕/刘诗雯", "Xu Xin/Liu Shiwen"), ("吉村真晴/石川佳纯", "Maharu Yoshimura/Kasumi Ishikawa"),
             (4, 1), [(11, 5), (11, 8), (9, 11), (11, 9), (11, 4)]),
        ],
    },
    {
        "id": 2346, "type": "世锦赛", "name_zh": "休斯敦世锦赛", "year": 2021,
        "start": "2021-11-23", "end": "2021-11-29", "city": "休斯敦", "country": "美国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("莫雷加德", "Truls Moregard"),
             (4, 0), [(11, 6), (11, 9), (11, 7), (11, 8)]),
            ("女子单打", ("王曼昱", "Wang Manyu"), ("孙颖莎", "Sun Yingsha"),
             (4, 2), [(11, 13), (11, 7), (6, 11), (11, 6), (11, 8), (17, 15)]),
            ("混合双打", ("王楚钦/孙颖莎", "Wang Chuqin/Sun Yingsha"), ("张本智和/早田希娜", "Tomokazu Harimoto/Hina Hayata"),
             (3, 0), [(11, 2), (11, 5), (11, 8)]),
        ],
    },
    {
        "id": 2660, "type": "世锦赛", "name_zh": "德班世锦赛", "year": 2023,
        "start": "2023-05-20", "end": "2023-05-28", "city": "德班", "country": "南非",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("王楚钦", "Wang Chuqin"),
             (4, 2), [(8, 11), (11, 9), (11, 7), (12, 10), (11, 13), (11, 3)]),
            ("女子单打", ("孙颖莎", "Sun Yingsha"), ("陈梦", "Chen Meng"),
             (4, 2), [(5, 11), (11, 8), (11, 7), (11, 7), (7, 11), (11, 6)]),
            ("混合双打", ("王楚钦/孙颖莎", "Wang Chuqin/Sun Yingsha"), ("张本智和/早田希娜", "Tomokazu Harimoto/Hina Hayata"),
             (3, 0), [(11, 6), (11, 2), (11, 7)]),
        ],
    },
    {
        "id": 3108, "type": "世锦赛", "name_zh": "多哈世锦赛", "year": 2025,
        "start": "2025-05-17", "end": "2025-05-25", "city": "多哈", "country": "卡塔尔",
        "finals": [
            ("男子单打", ("王楚钦", "Wang Chuqin"), ("雨果·卡尔德拉诺", "Hugo Calderano"),
             (4, 1), [(12, 10), (11, 3), (4, 11), (11, 2), (11, 7)]),
            ("女子单打", ("孙颖莎", "Sun Yingsha"), ("王曼昱", "Wang Manyu"),
             (4, 3), [(11, 6), (12, 10), (8, 11), (5, 11), (12, 10), (11, 13), (11, 7)]),
            ("混合双打", ("王楚钦/孙颖莎", "Wang Chuqin/Sun Yingsha"), ("吉村真晴/大藤沙月", "Maharu Yoshimura/Satsuki Odo"),
             (3, 1), [(11, 7), (11, 8), (7, 11), (11, 8)]),
        ],
    },
    # ================= 团体世锦赛 =================
    {
        "id": 924, "type": "团体世锦赛", "name_zh": "莫斯科团体世锦赛", "year": 2010,
        "start": "2010-05-23", "end": "2010-05-30", "city": "莫斯科", "country": "俄罗斯",
        "finals": [
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 1), None),
            ("女子团体", ("新加坡", "Singapore"), ("中国", "China"), (3, 1), None),
        ],
    },
    {
        "id": 923, "type": "团体世锦赛", "name_zh": "多特蒙德团体世锦赛", "year": 2012,
        "start": "2012-03-25", "end": "2012-04-01", "city": "多特蒙德", "country": "德国",
        "finals": [
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("新加坡", "Singapore"), (3, 0), None),
        ],
    },
    {
        "id": 277, "type": "团体世锦赛", "name_zh": "东京团体世锦赛", "year": 2014,
        "start": "2014-04-28", "end": "2014-05-05", "city": "东京", "country": "日本",
        "finals": [
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 1), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 197, "type": "团体世锦赛", "name_zh": "吉隆坡团体世锦赛", "year": 2016,
        "start": "2016-02-28", "end": "2016-03-06", "city": "吉隆坡", "country": "马来西亚",
        "finals": [
            ("男子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 896, "type": "团体世锦赛", "name_zh": "哈尔姆斯塔德团体世锦赛", "year": 2018,
        "start": "2018-04-29", "end": "2018-05-06", "city": "哈尔姆斯塔德", "country": "瑞典",
        "finals": [
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 1), None),
        ],
    },
    {
        "id": 2535, "type": "团体世锦赛", "name_zh": "成都团体世锦赛", "year": 2022,
        "start": "2022-09-30", "end": "2022-10-09", "city": "成都", "country": "中国",
        "finals": [
            ("男子团体", ("中国", "China"), ("德国", "Germany"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 2751, "type": "团体世锦赛", "name_zh": "釜山团体世锦赛", "year": 2024,
        "start": "2024-02-16", "end": "2024-02-25", "city": "釜山", "country": "韩国",
        "finals": [
            ("男子团体", ("中国", "China"), ("法国", "France"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 2), None),
        ],
    },
    {
        "id": 3216, "type": "团体世锦赛", "name_zh": "伦敦团体世锦赛", "year": 2026,
        "start": "2026-04-28", "end": "2026-05-10", "city": "伦敦", "country": "英国",
        "finals": [
            ("男子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 2), None),
        ],
    },
    # ================= 世界杯（单打） =================
    {
        "id": 662, "type": "世界杯", "name_zh": "男子世界杯", "year": 2010,
        "start": "2010-10-29", "end": "2010-10-31", "city": "马格德堡", "country": "德国",
        "finals": [
            ("男子单打", ("王皓", "Wang Hao"), ("张继科", "Zhang Jike"),
             (4, 1), [(8, 11), (11, 8), (12, 10), (11, 9), (11, 9)]),
        ],
    },
    {
        "id": 687, "type": "世界杯", "name_zh": "女子世界杯", "year": 2010,
        "start": "2010-09-24", "end": "2010-09-26", "city": "吉隆坡", "country": "马来西亚",
        "finals": [
            ("女子单打", ("郭焱", "Guo Yan"), ("姜华珺", "Jiang Huajun"),
             (4, 1), [(11, 9), (11, 6), (11, 7), (9, 11), (11, 9)]),
        ],
    },
    {
        "id": 748, "type": "世界杯", "name_zh": "男子世界杯", "year": 2011,
        "start": "2011-11-11", "end": "2011-11-13", "city": "巴黎", "country": "法国",
        "finals": [
            ("男子单打", ("张继科", "Zhang Jike"), ("王皓", "Wang Hao"),
             (4, 2), [(7, 11), (7, 11), (11, 9), (11, 4), (11, 5), (11, 3)]),
        ],
    },
    {
        "id": 763, "type": "世界杯", "name_zh": "女子世界杯", "year": 2011,
        "start": "2011-10-28", "end": "2011-10-30", "city": "新加坡", "country": "新加坡",
        "finals": [
            ("女子单打", ("丁宁", "Ding Ning"), ("李晓霞", "Li Xiaoxia"),
             (4, 1), [(11, 9), (11, 5), (7, 11), (14, 12), (11, 9)]),
        ],
    },
    {
        "id": 581, "type": "世界杯", "name_zh": "男子世界杯", "year": 2012,
        "start": "2012-09-28", "end": "2012-09-30", "city": "利物浦", "country": "英格兰",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("波尔", "Timo Boll"),
             (4, 0), [(11, 4), (11, 3), (11, 8), (11, 9)]),
        ],
    },
    {
        "id": 598, "type": "世界杯", "name_zh": "女子世界杯", "year": 2012,
        "start": "2012-09-21", "end": "2012-09-23", "city": "黄石", "country": "中国",
        "finals": [
            ("女子单打", ("刘诗雯", "Liu Shiwen"), ("萨马拉", "Elizabeta Samara"),
             (4, 0), [(11, 6), (11, 7), (11, 3), (11, 3)]),
        ],
    },
    {
        "id": 580, "type": "世界杯", "name_zh": "男子世界杯", "year": 2013,
        "start": "2013-10-25", "end": "2013-10-27", "city": "韦尔维耶", "country": "比利时",
        "finals": [
            ("男子单打", ("许昕", "Xu Xin"), ("萨姆索诺夫", "Vladimir Samsonov"),
             (4, 1), [(11, 6), (12, 14), (11, 8), (11, 9), (11, 7)]),
        ],
    },
    {
        "id": 597, "type": "世界杯", "name_zh": "女子世界杯", "year": 2013,
        "start": "2013-09-20", "end": "2013-09-23", "city": "神户", "country": "日本",
        "finals": [
            ("女子单打", ("刘诗雯", "Liu Shiwen"), ("武杨", "Wu Yang"),
             (4, 0), [(11, 3), (11, 7), (11, 7), (11, 2)]),
        ],
    },
    {
        "id": 328, "type": "世界杯", "name_zh": "男子世界杯", "year": 2014,
        "start": "2014-10-24", "end": "2014-10-26", "city": "杜塞尔多夫", "country": "德国",
        "finals": [
            ("男子单打", ("张继科", "Zhang Jike"), ("马龙", "Ma Long"),
             (4, 3), [(8, 11), (11, 4), (13, 11), (7, 11), (2, 11), (11, 5), (12, 10)]),
        ],
    },
    {
        "id": 329, "type": "世界杯", "name_zh": "女子世界杯", "year": 2014,
        "start": "2014-10-17", "end": "2014-10-19", "city": "林茨", "country": "奥地利",
        "finals": [
            ("女子单打", ("丁宁", "Ding Ning"), ("李晓霞", "Li Xiaoxia"),
             (4, 0), [(11, 7), (11, 9), (13, 11), (11, 5)]),
        ],
    },
    {
        "id": 315, "type": "世界杯", "name_zh": "男子世界杯", "year": 2015,
        "start": "2015-10-16", "end": "2015-10-18", "city": "哈尔姆斯塔德", "country": "瑞典",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("樊振东", "Fan Zhendong"),
             (4, 0), [(11, 7), (11, 6), (11, 8), (11, 8)]),
        ],
    },
    {
        "id": 316, "type": "世界杯", "name_zh": "女子世界杯", "year": 2015,
        "start": "2015-10-30", "end": "2015-11-01", "city": "仙台", "country": "日本",
        "finals": [
            ("女子单打", ("刘诗雯", "Liu Shiwen"), ("石川佳纯", "Kasumi Ishikawa"),
             (4, 0), [(14, 12), (11, 2), (11, 9), (11, 2)]),
        ],
    },
    {
        "id": 374, "type": "世界杯", "name_zh": "男子世界杯", "year": 2016,
        "start": "2016-10-01", "end": "2016-10-03", "city": "萨尔布吕肯", "country": "德国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("许昕", "Xu Xin"),
             (4, 1), [(11, 5), (11, 6), (11, 8), (7, 11), (12, 10)]),
        ],
    },
    {
        "id": 375, "type": "世界杯", "name_zh": "女子世界杯", "year": 2016,
        "start": "2016-10-07", "end": "2016-10-09", "city": "费城", "country": "美国",
        "finals": [
            ("女子单打", ("平野美宇", "Miu Hirano"), ("郑怡静", "Cheng I-ching"),
             (4, 0), [(11, 9), (11, 5), (11, 4), (11, 8)]),
        ],
    },
    {
        "id": 506, "type": "世界杯", "name_zh": "男子世界杯", "year": 2017,
        "start": "2017-10-20", "end": "2017-10-22", "city": "列日", "country": "比利时",
        "finals": [
            ("男子单打", ("奥恰洛夫", "Dimitrij Ovtcharov"), ("波尔", "Timo Boll"),
             (4, 2), [(10, 12), (11, 8), (11, 7), (9, 11), (11, 7), (11, 2)]),
        ],
    },
    {
        "id": 507, "type": "世界杯", "name_zh": "女子世界杯", "year": 2017,
        "start": "2017-10-27", "end": "2017-10-29", "city": "马克姆", "country": "加拿大",
        "finals": [
            ("女子单打", ("朱雨玲", "Zhu Yuling"), ("刘诗雯", "Liu Shiwen"),
             (4, 3), [(11, 13), (8, 11), (11, 7), (11, 8), (10, 12), (11, 9), (12, 10)]),
        ],
    },
    {
        "id": 895, "type": "世界杯", "name_zh": "男子世界杯", "year": 2018,
        "start": "2018-10-19", "end": "2018-10-21", "city": "巴黎", "country": "法国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("波尔", "Timo Boll"),
             (4, 1), [(11, 9), (11, 5), (11, 6), (9, 11), (11, 8)]),
        ],
    },
    {
        "id": 894, "type": "世界杯", "name_zh": "女子世界杯", "year": 2018,
        "start": "2018-09-28", "end": "2018-09-30", "city": "成都", "country": "中国",
        "finals": [
            ("女子单打", ("丁宁", "Ding Ning"), ("朱雨玲", "Zhu Yuling"),
             (4, 0), [(11, 9), (11, 8), (12, 10), (11, 8)]),
        ],
    },
    {
        "id": 2015, "type": "世界杯", "name_zh": "男子世界杯", "year": 2019,
        "start": "2019-11-29", "end": "2019-12-01", "city": "成都", "country": "中国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("张本智和", "Tomokazu Harimoto"),
             (4, 2), [(9, 11), (11, 4), (6, 11), (11, 8), (11, 2), (11, 7)]),
        ],
    },
    {
        "id": 2014, "type": "世界杯", "name_zh": "女子世界杯", "year": 2019,
        "start": "2019-10-18", "end": "2019-10-20", "city": "成都", "country": "中国",
        "finals": [
            ("女子单打", ("刘诗雯", "Liu Shiwen"), ("朱雨玲", "Zhu Yuling"),
             (4, 2), [(4, 11), (11, 8), (11, 8), (11, 6), (3, 11), (11, 9)]),
        ],
    },
    {
        "id": 2265, "type": "世界杯", "name_zh": "男子世界杯", "year": 2020,
        "start": "2020-11-13", "end": "2020-11-15", "city": "威海", "country": "中国",
        "finals": [
            ("男子单打", ("樊振东", "Fan Zhendong"), ("马龙", "Ma Long"),
             (4, 3), [(3, 11), (11, 8), (11, 3), (11, 6), (7, 11), (7, 11), (11, 9)]),
        ],
    },
    {
        "id": 2263, "type": "世界杯", "name_zh": "女子世界杯", "year": 2020,
        "start": "2020-11-08", "end": "2020-11-10", "city": "威海", "country": "中国",
        "finals": [
            ("女子单打", ("陈梦", "Chen Meng"), ("孙颖莎", "Sun Yingsha"),
             (4, 1), [(11, 13), (11, 6), (11, 9), (11, 6), (11, 8)]),
        ],
    },
    {
        "id": 2937, "type": "世界杯", "name_zh": "乒乓球世界杯（澳门）", "year": 2024,
        "start": "2024-04-15", "end": "2024-04-21", "city": "澳门", "country": "中国",
        "finals": [
            ("男子单打", ("马龙", "Ma Long"), ("林高远", "Lin Gaoyuan"),
             (4, 3), [(9, 11), (9, 11), (5, 11), (11, 8), (11, 6), (11, 4), (11, 8)]),
            ("女子单打", ("孙颖莎", "Sun Yingsha"), ("王曼昱", "Wang Manyu"),
             (4, 3), [(8, 11), (5, 11), (11, 4), (5, 11), (11, 8), (11, 5), (11, 9)]),
        ],
    },
    {
        "id": 3109, "type": "世界杯", "name_zh": "乒乓球世界杯（澳门）", "year": 2025,
        "start": "2025-04-14", "end": "2025-04-20", "city": "澳门", "country": "中国",
        "finals": [
            ("男子单打", ("雨果·卡尔德拉诺", "Hugo Calderano"), ("林诗栋", "Lin Shidong"),
             (4, 1), [(6, 11), (11, 7), (11, 9), (11, 4), (11, 5)]),
            ("女子单打", ("孙颖莎", "Sun Yingsha"), ("蒯曼", "Kuai Man"),
             (4, 0), [(11, 9), (11, 6), (11, 9), (11, 6)]),
        ],
    },
    {
        "id": 3379, "type": "世界杯", "name_zh": "乒乓球世界杯（澳门）", "year": 2026,
        "start": "2026-03-30", "end": "2026-04-05", "city": "澳门", "country": "中国",
        "finals": [
            ("男子单打", ("王楚钦", "Wang Chuqin"), ("松岛辉空", "Sora Matsushima"),
             (4, 3), [(9, 11), (18, 16), (11, 8), (11, 13), (8, 11), (11, 4), (11, 8)]),
            ("女子单打", ("孙颖莎", "Sun Yingsha"), ("王曼昱", "Wang Manyu"),
             (4, 1), [(11, 9), (11, 8), (13, 11), (8, 11), (11, 7)]),
        ],
    },
    # ================= 团体世界杯 =================
    {
        "id": 938, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2010,
        "start": "2010-10-01", "end": "2010-10-03", "city": "迪拜", "country": "阿联酋",
        "finals": [
            ("男子团体", ("中国", "China"), ("韩国", "South Korea"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("新加坡", "Singapore"), (3, 0), None),
        ],
    },
    {
        "id": 937, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2011,
        "start": "2011-11-03", "end": "2011-11-06", "city": "马格德堡", "country": "德国",
        "finals": [
            ("男子团体", ("中国", "China"), ("韩国", "South Korea"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 936, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2013,
        "start": "2013-03-28", "end": "2013-03-31", "city": "广州", "country": "中国",
        "finals": [
            ("男子团体", ("中国", "China"), ("中华台北", "Chinese Taipei"), (3, 1), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 205, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2015,
        "start": "2015-01-08", "end": "2015-01-11", "city": "迪拜", "country": "阿联酋",
        "finals": [
            ("男子团体", ("中国", "China"), ("奥地利", "Austria"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("朝鲜", "North Korea"), (3, 0), None),
        ],
    },
    {
        "id": 893, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2018,
        "start": "2018-02-22", "end": "2018-02-25", "city": "伦敦", "country": "英国",
        "finals": [
            ("男子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    {
        "id": 2016, "type": "团体世界杯", "name_zh": "团体世界杯", "year": 2019,
        "start": "2019-11-06", "end": "2019-11-10", "city": "东京", "country": "日本",
        "finals": [
            ("男子团体", ("中国", "China"), ("韩国", "South Korea"), (3, 1), None),
            ("女子团体", ("中国", "China"), ("日本", "Japan"), (3, 0), None),
        ],
    },
    # ================= 混合团体世界杯 =================
    {
        "id": 2860, "type": "混合团体世界杯", "name_zh": "混合团体世界杯", "year": 2023,
        "start": "2023-12-04", "end": "2023-12-10", "city": "成都", "country": "中国",
        "finals": [("混合团体", ("中国", "China"), ("韩国", "South Korea"), (8, 1), None)],
    },
    {
        "id": 2979, "type": "混合团体世界杯", "name_zh": "混合团体世界杯", "year": 2024,
        "start": "2024-12-01", "end": "2024-12-08", "city": "成都", "country": "中国",
        "finals": [("混合团体", ("中国", "China"), ("韩国", "South Korea"), (8, 1), None)],
    },
    {
        "id": 3263, "type": "混合团体世界杯", "name_zh": "混合团体世界杯", "year": 2025,
        "start": "2025-11-30", "end": "2025-12-07", "city": "成都", "country": "中国",
        "finals": [("混合团体", ("中国", "China"), ("日本", "Japan"), (8, 1), None)],
    },
]


class MajorsDataSource(DataSource):
    """大赛默认只显示当期官方赛程；旧决赛留作非默认档案。"""

    name = "majors"

    def __init__(self, official_feeds: tuple[OfficialMajorFeed, ...] = ()):
        self._asian_games = AsianGamesFeed()
        self._latest: dict[str, Match] = {}
        self._team_games: dict[str, list] = {}
        self._official_feeds = tuple(official_feeds)
        if any(feed.category not in CURRENT_MAJOR_CATEGORIES for feed in self._official_feeds):
            raise ValueError("未知的大赛分类")
        self._official_latest: dict[str, dict[str, Match]] = {}

    def get_live_matches(self) -> list[Match]:
        return [m for m in self.get_matches() if m.status == "live"]

    def get_schedule(self) -> list[Match]:
        return self.get_matches()

    def get_historical_matches(self) -> list[Match]:
        matches: list[Match] = []
        for event in MAJOR_EVENTS:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            for cat, (champ, champ_raw), (runner, runner_raw), score, sets in event["finals"]:
                team_record = TEAM_RESULTS.get((event["id"], cat))
                score_known = score is not None
                score_a, score_b = (score if score is not None else (0, 0))
                matches.append(
                    Match(
                        id=f"major:{event['id']}:{cat}",
                        source=self.name,
                        competition=(
                            f"{event['year']} {event['name_zh']} · "
                            f"{event['city']} · {cat}"
                        ),
                        status=STATUS_FINISHED,
                        start_time=datetime.fromisoformat(team_record[0]) if team_record else start,
                        player_a=champ,
                        player_b=runner,
                        player_a_raw=champ_raw,
                        player_b_raw=runner_raw,
                        score_a=score_a,
                        score_b=score_b,
                        sets=list(sets) if sets else [],
                        score_known=score_known,
                        games=team_games(event["id"], cat),
                        last_update=end,
                    )
                )
        return matches

    def get_matches(self) -> list[Match]:
        try:
            matches = self._asian_games.matches()
        except Exception:
            # 官网暂时不可用时保留已获取的比分，不用历史比赛充数。
            matches = [replace(match, data_stale=True) for match in self._latest.values()]
        for match in matches:
            if match.id in self._team_games:
                match.games = self._team_games[match.id]
            if match.status == "live" and "团体" in match.competition:
                try:
                    self._asian_games.detail(match)
                    self._team_games[match.id] = match.games
                except Exception:
                    pass
        self._latest = {m.id: m for m in matches}
        for feed in self._official_feeds:
            try:
                current = feed.get_matches()
                if any(m.source != self.name or m.major_category != feed.category
                       or m.id.startswith("major:") for m in current):
                    raise ValueError("官方当期数据分类或来源不一致")
                self._official_latest[feed.category] = {m.id: m for m in current}
                matches.extend(current)
            except Exception:
                # 仅沿用该官方源已成功取得的数据，并明确标记为旧数据。
                matches.extend(replace(m, data_stale=True)
                               for m in self._official_latest.get(feed.category, {}).values())
        return matches

    def get_match_detail(self, match_id: str) -> Match | None:
        for feed in self._official_feeds:
            if match_id in self._official_latest.get(feed.category, {}):
                try:
                    return feed.get_match_detail(match_id)
                except Exception:
                    return replace(self._official_latest[feed.category][match_id], data_stale=True)
        if match_id.startswith("asiangames:"):
            match = self._latest.get(match_id)
            if match is None:
                return None
            try:
                detailed = self._asian_games.detail(match)
                if detailed.games:
                    self._team_games[match.id] = detailed.games
                return detailed
            except Exception:
                return match
        for m in self.get_historical_matches():
            if m.id == match_id:
                return m
        return None
