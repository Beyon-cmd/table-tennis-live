"""常用选手中英文名对照表。

WTT 官方数据里的选手名是拼音/英文（如 WANG Chuqin、HARIMOTO Tomokazu），
这里收录常用选手的规范中文名（以中文媒体通用译名为准）。
只收录有把握的名字；未收录的选手保留原名，不强行音译。
"""
from __future__ import annotations

# 键为官方名的小写形式
_NAME_MAP: dict[str, str] = {
    # ---- 中国 ----
    "ma long": "马龙",
    "fan zhendong": "樊振东",
    "wang chuqin": "王楚钦",
    "lin shidong": "林诗栋",
    "liang jingkun": "梁靖崑",
    "lin gaoyuan": "林高远",
    "xu xin": "许昕",
    "sun yingsha": "孙颖莎",
    "wang manyu": "王曼昱",
    "chen meng": "陈梦",
    "wang yidi": "王艺迪",
    "chen xingtong": "陈幸同",
    "liu shiwen": "刘诗雯",
    "ding ning": "丁宁",
    "kuai man": "蒯曼",
    "qian tianyi": "钱天一",
    "he zhuojia": "何卓佳",
    "zhang rui": "张瑞",
    "fan siqi": "范思琦",
    "shi xunyao": "石洵瑶",
    "chen yi": "陈熠",
    "zang xiaotong": "臧小桐",
    "xiang peng": "向鹏",
    "xu yingbin": "徐瑛彬",
    "yuan licen": "袁励岑",
    "zhou qihao": "周启豪",
    "xue fei": "薛飞",
    "liu dingshuo": "刘丁硕",
    "zhou yu": "周雨",
    "fang bo": "方博",
    "yan an": "闫安",
    # ---- 日本 ----
    "harimoto tomokazu": "张本智和",
    "harimoto miwa": "张本美和",
    "ito mima": "伊藤美诚",
    "hayata hina": "早田希娜",
    "hirano miu": "平野美宇",
    "togami shunsuke": "户上隼辅",
    "matsushima sora": "松岛辉空",
    "shinozuka hirotoshi": "篠塚大登",
    "uda yukiya": "宇田幸矢",
    "ojio yuna": "大藤沙月",
    "yokoi sakura": "横井咲樱",
    "kihara miyuu": "木原美悠",
    "nagasaki miyu": "长崎美柚",
    "sato hitomi": "佐藤瞳",
    "hashimoto honoka": "桥本帆乃香",
    "morizono masataka": "森薗政崇",
    "yoshimura maharu": "吉村真晴",
    # ---- 韩国 ----
    "shin yubin": "申裕斌",
    "jeon jihee": "田志希",
    "seo hyowon": "徐孝元",
    "lee sangsu": "李尚洙",
    "lim jonghoon": "林钟勋",
    "jang woojin": "张禹珍",
    "cho seungmin": "赵大成",
    "an jaehyun": "安宰贤",
    "oh junsung": "吴晙诚",
    "park gyuhyeon": "朴圭贤",
    "lee eunhye": "李恩惠",
    # ---- 朝鲜 ----
    "kim kum yong": "金琴英",
    # ---- 中华台北 ----
    "lin yun-ju": "林昀儒",
    "chuang chih-yuan": "庄智渊",
    "kao cheng-jui": "高承睿",
    "cheng i-ching": "郑怡静",
    "chen szu-yu": "陈思羽",
    "li yu-jhun": "李昱諄",
    "feng yi-hsin": "冯翊新",
    "liao cheng-ting": "廖振珽",
    "huang yan-cheng": "黄彦诚",
    "chen chien-an": "陈建安",
    # ---- 中国香港 ----
    "wong chun ting": "黄镇廷",
    "doo hoi kem": "杜凯琹",
    "lee ho ching": "李皓晴",
    "ho kwan kit": "何钧杰",
    "ng pak nam": "吴柏男",
    "zhu chengzhu": "朱成竹",
    "minnie soo wai yam": "苏慧音",
    "lam siu hang": "林兆恒",
    # ---- 德国 ----
    "ovtcharov dimitrij": "奥恰洛夫",
    "boll timo": "波尔",
    "dang qiu": "邱党",
    "franziska patrick": "弗朗西斯卡",
    "han ying": "韩莹",
    "shan xiaona": "单晓娜",
    "mittelham nina": "米特海姆",
    "kaufmann annett": "考夫曼",
    "walther ricardo": "沃尔瑟",
    "duda benedikt": "杜达",
    "mengele steffen": "门格尔",
    # ---- 法国 ----
    "lebrun felix": "费利克斯·勒布伦",
    "lebrun alexis": "艾利克斯·勒布伦",
    "gauzy simon": "西蒙·高兹",
    "pavade prithika": "普莉蒂卡·帕瓦德",
    "yuan jianan": "袁嘉楠",
    "lutz charlotte": "夏洛特·卢茨",
    # ---- 瑞典 ----
    "moregard truls": "莫雷加德",
    "falck mattias": "法尔克",
    "karlberg anton": "安东·卡尔伯格",
    "kallberg kristian": "克里斯蒂安·卡尔松",
    # ---- 丹麦 ----
    "groth jonathan": "约纳坦·格罗斯",
    "lind anders": "安德斯·林德",
    # ---- 葡萄牙 ----
    "freitas marcos": "弗雷塔斯",
    "apolonia tiago": "阿波罗尼亚",
    "monteiro joao": "蒙泰罗",
    "geraldo joao": "格拉尔多",
    # ---- 奥地利 ----
    "gardos robert": "加尔多斯",
    "habesohn daniel": "哈贝松",
    "polcanova sofia": "波尔卡诺娃",
    # ---- 巴西 ----
    "calderano hugo": "雨果·卡尔德拉诺",
    "takahashi bruna": "高桥·布鲁娜",
    "ishiy vitor": "维托尔·伊希",
    # ---- 印度 ----
    "gnanasekaran sathiyan": "加纳纳塞卡然",
    "sharath achanta": "阿昌塔",
    "batra manika": "巴特拉",
    "desai harmeet": "德赛",
    # ---- 埃及 ----
    "assar omar": "奥马尔·阿萨尔",
    "meshref dina": "梅谢芙",
    # ---- 其它 ----
    "aruna quadri": "阿鲁纳",
    "jorgic darko": "达科·约奇克",
    "pucar tomislav": "普卡尔",
    "samsonov vladimir": "萨姆索诺夫",
    "ni xia lian": "倪夏莲",
    "li jie": "李洁",
    "eerland britt": "埃兰德",
    "feng tianwei": "冯天薇",
    "zeng jian": "曾尖",
    "sawettabut suthasini": "素塔西尼·沙卫塔布",
    "paranang orawan": "奥拉万·帕拉南",
    "szocs bernadette": "斯佐科斯",
    "singeorzan ioana": "辛格奥尔赞",
    "samara elizabeta": "萨马拉",
    "pitchford liam": "皮切福德",
    "drinkhall paul": "金克霍尔",
    "jarvis tom": "贾维斯",
    "gerassimenko kirill": "格拉斯门科",
    "alamian nima": "阿拉米扬",
    "diaz adriana": "迪亚兹",
    "kukulkova tatiana": "库库尔科娃",
    "matelova hana": "马特洛娃",
    "nuy tinck cedric": "努伊廷克",
    "robles alvaro": "罗布莱斯",
    "zhang lily": "张莉莉",
    # ---- TTBL / WTT 当前常见国际选手 ----
    "csaba andras": "安德拉斯·恰巴",
    "verdonschot wim": "维姆·费尔东斯霍特",
    "movileanu darius": "达里乌斯·莫维莱亚努",
    "berzosa daniel": "丹尼尔·贝尔索萨",
    "bertelsmeier andre": "安德烈·贝特尔斯迈尔",
    "zeljko filip": "菲利普·泽利科",
    "chirita iulian": "尤利安·基里察",
    "abiodun tiago": "蒂亚戈·阿比奥敦",
    "liao cheng-ting": "廖振珽",
    "rassenfosse adrien": "阿德里安·拉森福斯",
    "vinogradov dmitrii": "德米特里·维诺格拉多夫",
    "jha kanak": "卡纳克·贾",
    "quek izaac": "艾萨克·奎克",
    "kawakami ryuusei": "川上流星",
    "mende rin": "面手凛",
    "omoda kotomi": "小本琴美",
    "tsai yun-en": "蔡昀恩",
    "badowski marek": "马雷克·巴多夫斯基",
    # ---- 日本官网的日文姓名别名（含当前 T.League 外援） ----
    "張本 智和": "张本智和",
    "張本 美和": "张本美和",
    "松島 輝空": "松岛辉空",
    "大藤 沙月": "大藤沙月",
    "横井 咲桜": "横井咲樱",
    "伊藤 美誠": "伊藤美诚",
    "早田 ひな": "早田希娜",
    "平野 美宇": "平野美宇",
    "篠塚 大登": "篠塚大登",
    "戸上 隼輔": "户上隼辅",
    "吉村 真晴": "吉村真晴",
    "ユ ハンナ": "柳汉娜",
    "チェ ヒョジュ": "崔孝珠",
    "ガオ チェンルイ": "高承睿",
}


def to_chinese_name(name: str) -> str | None:
    """官方英文名 -> 中文名；未收录返回 None。双打按 “/” 拆开逐个翻译。"""
    key = " ".join((name or "").strip().lower().split())
    if not key:
        return None
    if key in _NAME_MAP:
        return _NAME_MAP[key]
    # 排名源使用名在前、姓在后；比赛源常使用姓在前。
    if "/" not in key:
        words = key.split()
        candidates = {_NAME_MAP[" ".join(words[i:] + words[:i])]
                      for i in range(1, len(words))
                      if " ".join(words[i:] + words[:i]) in _NAME_MAP}
        if len(candidates) == 1:
            return candidates.pop()
    parts = [p.strip() for p in name.split("/") if p.strip()]
    if len(parts) > 1:
        mapped = [to_chinese_name(p) for p in parts]
        if all(mapped):
            return " / ".join(mapped)
    return None


# ---- 俱乐部中文名 ----
# 键为官网队名的小写形式
_TEAM_MAP: dict[str, str] = {
    # 德国 TTBL
    "1. fc saarbrücken-tt": "萨尔布吕肯",
    "borussia düsseldorf": "杜塞尔多夫",
    "ttf liebherr ochsenhausen": "奥克森豪森",
    "asc grünwettersbach": "格林维特斯巴赫",
    "ttc rhönsprudel fulda-maberzell": "富尔达-马贝尔策尔",
    "ttc oe clarity-tel.syst.bad homburg": "巴特洪堡",
    "tsv bad königshofen": "巴特科尼希斯霍芬",
    "ttc schwalbe bergneustadt": "贝格诺伊施塔特",
    "bv borussia 09 dortmund": "多特蒙德",
    "ttc zugbrücke grenzau": "格伦曹",
    "sv werder bremen": "不来梅",
    "post sv mühlhausen": "米尔豪森",
    # 日本 T.League（官网使用缩写，只收录有把握的）
    "km東京": "木下东京",
    "tt彩たま": "TT彩玉",
    "ka神奈川": "神奈川",
    "岡山": "冈山",
    "琉球": "琉球",
    "金沢": "金泽",
    "京都": "京都",
    "九州": "九州",
    "日本生命": "日本生命",
    "静岡": "静冈",
    "横浜": "横滨",
}


def to_chinese_team(name: str) -> str | None:
    """官网队名 -> 中文名；未收录返回 None。"""
    key = (name or "").strip().lower()
    return _TEAM_MAP.get(key)
