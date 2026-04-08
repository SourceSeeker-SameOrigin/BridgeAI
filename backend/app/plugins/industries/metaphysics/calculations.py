"""玄学计算核心模块 - 所有数学/历法/天文计算集中于此。

LLM 擅长解读但不擅长精确计算，因此本模块负责所有需要精确数值的运算，
将结构化结果返回给 LLM 做解读。

依赖: cnlunar, lunarcalendar, ephem
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any

import cnlunar
import ephem
from lunarcalendar import Converter, Lunar, Solar

# ---------------------------------------------------------------------------
# 常量表
# ---------------------------------------------------------------------------

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 天干对应五行
GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

# 地支对应五行
ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 天干阴阳 (奇数索引=阳, 偶数索引=阴)
GAN_YINYANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(TIAN_GAN)}

# 地支阴阳
ZHI_YINYANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(DI_ZHI)}

# 藏干表
CANG_GAN: dict[str, list[str]] = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 五行生克关系
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 反向: 谁生我、谁克我
WUXING_SHENG_WO = {v: k for k, v in WUXING_SHENG.items()}
WUXING_KE_WO = {v: k for k, v in WUXING_KE.items()}

# 纳音六十甲子表
NAYIN_TABLE: dict[str, str] = {
    "甲子": "海中金", "乙丑": "海中金", "丙寅": "炉中火", "丁卯": "炉中火",
    "戊辰": "大林木", "己巳": "大林木", "庚午": "路旁土", "辛未": "路旁土",
    "壬申": "剑锋金", "癸酉": "剑锋金", "甲戌": "山头火", "乙亥": "山头火",
    "丙子": "涧下水", "丁丑": "涧下水", "戊寅": "城头土", "己卯": "城头土",
    "庚辰": "白蜡金", "辛巳": "白蜡金", "壬午": "杨柳木", "癸未": "杨柳木",
    "甲申": "泉中水", "乙酉": "泉中水", "丙戌": "屋上土", "丁亥": "屋上土",
    "戊子": "霹雳火", "己丑": "霹雳火", "庚寅": "松柏木", "辛卯": "松柏木",
    "壬辰": "长流水", "癸巳": "长流水", "甲午": "沙中金", "乙未": "沙中金",
    "丙申": "山下火", "丁酉": "山下火", "戊戌": "平地木", "己亥": "平地木",
    "庚子": "壁上土", "辛丑": "壁上土", "壬寅": "金箔金", "癸卯": "金箔金",
    "甲辰": "覆灯火", "乙巳": "覆灯火", "丙午": "天河水", "丁未": "天河水",
    "戊申": "大驿土", "己酉": "大驿土", "庚戌": "钗钏金", "辛亥": "钗钏金",
    "壬子": "桑柘木", "癸丑": "桑柘木", "甲寅": "大溪水", "乙卯": "大溪水",
    "丙辰": "沙中土", "丁巳": "沙中土", "戊午": "天上火", "己未": "天上火",
    "庚申": "石榴木", "辛酉": "石榴木", "壬戌": "大海水", "癸亥": "大海水",
}

# 十二生肖
SHENGXIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 时辰对应时间范围
SHICHEN_RANGE = [
    ("子", "23:00-01:00"), ("丑", "01:00-03:00"), ("寅", "03:00-05:00"),
    ("卯", "05:00-07:00"), ("辰", "07:00-09:00"), ("巳", "09:00-11:00"),
    ("午", "11:00-13:00"), ("未", "13:00-15:00"), ("申", "15:00-17:00"),
    ("酉", "17:00-19:00"), ("戌", "19:00-21:00"), ("亥", "21:00-23:00"),
]

# 中国主要城市经纬度 (用于真太阳时修正)
CITY_COORDS: dict[str, tuple[float, float]] = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668), "重庆": (29.5630, 106.5516),
    "杭州": (30.2741, 120.1551), "南京": (32.0603, 118.7969),
    "武汉": (30.5928, 114.3055), "西安": (34.3416, 108.9398),
    "长沙": (28.2282, 112.9388), "天津": (39.0842, 117.2010),
    "苏州": (31.2990, 120.5853), "郑州": (34.7466, 113.6254),
    "济南": (36.6512, 116.9972), "沈阳": (41.8057, 123.4315),
    "大连": (38.9140, 121.6147), "哈尔滨": (45.8038, 126.5350),
    "长春": (43.8171, 125.3235), "昆明": (25.0389, 102.7183),
    "贵阳": (26.6470, 106.6302), "兰州": (36.0611, 103.8343),
    "太原": (37.8706, 112.5489), "石家庄": (38.0428, 114.5149),
    "合肥": (31.8206, 117.2272), "南昌": (28.6820, 115.8579),
    "福州": (26.0745, 119.2965), "厦门": (24.4798, 118.0894),
    "南宁": (22.8170, 108.3665), "海口": (20.0174, 110.3492),
    "拉萨": (29.6500, 91.1000), "乌鲁木齐": (43.8256, 87.6168),
    "呼和浩特": (40.8414, 111.7519), "银川": (38.4872, 106.2309),
    "西宁": (36.6171, 101.7782), "台北": (25.0330, 121.5654),
    "香港": (22.3193, 114.1694), "澳门": (22.1987, 113.5439),
}

# 星座分界 (月, 日, 星座名)
ZODIAC_SIGNS = [
    (1, 20, "水瓶座"), (2, 19, "双鱼座"), (3, 21, "白羊座"),
    (4, 20, "金牛座"), (5, 21, "双子座"), (6, 21, "巨蟹座"),
    (7, 23, "狮子座"), (8, 23, "处女座"), (9, 23, "天秤座"),
    (10, 23, "天蝎座"), (11, 22, "射手座"), (12, 22, "摩羯座"),
]

# 黄道十二宫 (用于星盘)
ZODIAC_SIGNS_ASTRO = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]

# 八卦
BAGUA: dict[int, tuple[str, str, str]] = {
    1: ("乾", "天", "金"), 2: ("兑", "泽", "金"),
    3: ("离", "火", "火"), 4: ("震", "雷", "木"),
    5: ("巽", "风", "木"), 6: ("坎", "水", "水"),
    7: ("艮", "山", "土"), 8: ("坤", "地", "土"),
}

# 八卦二进制 (阳爻=1, 阴爻=0, 从下到上)
BAGUA_BINARY = {
    1: (1, 1, 1),  # 乾
    2: (1, 1, 0),  # 兑
    3: (1, 0, 1),  # 离
    4: (0, 0, 1),  # 震
    5: (1, 1, 0),  # 巽 - actually (0,1,1)
    6: (0, 1, 0),  # 坎
    7: (1, 0, 0),  # 艮
    8: (0, 0, 0),  # 坤
}

# 64卦名称表 (上卦, 下卦) -> 卦名
SIXTY_FOUR_GUA: dict[tuple[int, int], tuple[str, int]] = {
    (1, 1): ("乾为天", 1), (1, 2): ("天泽履", 10), (1, 3): ("天火同人", 13),
    (1, 4): ("天雷无妄", 25), (1, 5): ("天风姤", 44), (1, 6): ("天水讼", 6),
    (1, 7): ("天山遁", 33), (1, 8): ("天地否", 12),
    (2, 1): ("泽天夬", 43), (2, 2): ("兑为泽", 58), (2, 3): ("泽火革", 49),
    (2, 4): ("泽雷随", 17), (2, 5): ("泽风大过", 28), (2, 6): ("泽水困", 47),
    (2, 7): ("泽山咸", 31), (2, 8): ("泽地萃", 45),
    (3, 1): ("火天大有", 14), (3, 2): ("火泽睽", 38), (3, 3): ("离为火", 30),
    (3, 4): ("火雷噬嗑", 21), (3, 5): ("火风鼎", 50), (3, 6): ("火水未济", 64),
    (3, 7): ("火山旅", 56), (3, 8): ("火地晋", 35),
    (4, 1): ("雷天大壮", 34), (4, 2): ("雷泽归妹", 54), (4, 3): ("雷火丰", 55),
    (4, 4): ("震为雷", 51), (4, 5): ("雷风恒", 32), (4, 6): ("雷水解", 40),
    (4, 7): ("雷山小过", 62), (4, 8): ("雷地豫", 16),
    (5, 1): ("风天小畜", 9), (5, 2): ("风泽中孚", 61), (5, 3): ("风火家人", 37),
    (5, 4): ("风雷益", 42), (5, 5): ("巽为风", 57), (5, 6): ("风水涣", 59),
    (5, 7): ("风山渐", 53), (5, 8): ("风地观", 20),
    (6, 1): ("水天需", 5), (6, 2): ("水泽节", 60), (6, 3): ("水火既济", 63),
    (6, 4): ("水雷屯", 3), (6, 5): ("水风井", 48), (6, 6): ("坎为水", 29),
    (6, 7): ("水山蹇", 39), (6, 8): ("水地比", 7),
    (7, 1): ("山天大畜", 26), (7, 2): ("山泽损", 41), (7, 3): ("山火贲", 22),
    (7, 4): ("山雷颐", 27), (7, 5): ("山风蛊", 18), (7, 6): ("山水蒙", 4),
    (7, 7): ("艮为山", 52), (7, 8): ("山地剥", 23),
    (8, 1): ("地天泰", 11), (8, 2): ("地泽临", 19), (8, 3): ("地火明夷", 36),
    (8, 4): ("地雷复", 24), (8, 5): ("地风升", 46), (8, 6): ("地水师", 8),
    (8, 7): ("地山谦", 15), (8, 8): ("坤为地", 2),
}

# 十神名称
SHISHEN_NAMES = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]

# 五行对应的十神关系索引
# 以日干五行为基准: 同=比劫, 我生=食伤, 我克=财, 克我=官杀, 生我=印
def _get_shishen(day_gan: str, other_gan: str) -> str:
    """计算十神关系。"""
    day_wx = GAN_WUXING[day_gan]
    other_wx = GAN_WUXING[other_gan]
    day_yy = GAN_YINYANG[day_gan]
    other_yy = GAN_YINYANG[other_gan]
    same_polarity = day_yy == other_yy

    if day_wx == other_wx:
        return "比肩" if same_polarity else "劫财"
    elif WUXING_SHENG[day_wx] == other_wx:
        return "食神" if same_polarity else "伤官"
    elif WUXING_KE[day_wx] == other_wx:
        return "偏财" if same_polarity else "正财"
    elif WUXING_KE_WO[day_wx] == other_wx:
        return "七杀" if same_polarity else "正官"
    elif WUXING_SHENG_WO[day_wx] == other_wx:
        return "偏印" if same_polarity else "正印"
    return "未知"


# 主要神煞
def _calc_shensha(year_zhi: str, day_gan: str, day_zhi: str,
                  month_zhi: str, hour_zhi: str) -> list[str]:
    """计算常见神煞(简化版，取前5个最重要的)。"""
    results: list[str] = []
    all_zhi = [year_zhi, month_zhi, day_zhi, hour_zhi]

    # 天乙贵人
    tiyi_map = {
        "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
        "乙": ["子", "申"], "己": ["子", "申"],
        "丙": ["亥", "酉"], "丁": ["亥", "酉"],
        "壬": ["卯", "巳"], "癸": ["卯", "巳"],
        "辛": ["午", "寅"],
    }
    if day_gan in tiyi_map:
        for z in all_zhi:
            if z in tiyi_map[day_gan]:
                results.append("天乙贵人")
                break

    # 文昌星
    wenchang_map = {
        "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
        "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
    }
    if wenchang_map.get(day_gan) in all_zhi:
        results.append("文昌星")

    # 驿马
    yima_map = {"寅": "申", "申": "寅", "巳": "亥", "亥": "巳",
                "子": "午", "午": "子", "卯": "酉", "酉": "卯",
                "辰": "戌", "戌": "辰", "丑": "未", "未": "丑"}
    # 驿马以年支查: 申子辰马在寅, 寅午戌马在申, 巳酉丑马在亥, 亥卯未马在巳
    yima_map2 = {
        "申": "寅", "子": "寅", "辰": "寅",
        "寅": "申", "午": "申", "戌": "申",
        "巳": "亥", "酉": "亥", "丑": "亥",
        "亥": "巳", "卯": "巳", "未": "巳",
    }
    yima_target = yima_map2.get(year_zhi)
    if yima_target and yima_target in all_zhi:
        results.append("驿马")

    # 桃花 (咸池)
    taohua_map = {
        "申": "酉", "子": "酉", "辰": "酉",
        "寅": "卯", "午": "卯", "戌": "卯",
        "巳": "午", "酉": "午", "丑": "午",
        "亥": "子", "卯": "子", "未": "子",
    }
    taohua_target = taohua_map.get(year_zhi)
    if taohua_target and taohua_target in all_zhi:
        results.append("桃花(咸池)")

    # 华盖
    huagai_map = {
        "申": "辰", "子": "辰", "辰": "辰",
        "寅": "戌", "午": "戌", "戌": "戌",
        "巳": "丑", "酉": "丑", "丑": "丑",
        "亥": "未", "卯": "未", "未": "未",
    }
    huagai_target = huagai_map.get(year_zhi)
    if huagai_target and huagai_target in all_zhi:
        results.append("华盖")

    # 将星
    jiangxing_map = {
        "申": "子", "子": "子", "辰": "子",
        "寅": "午", "午": "午", "戌": "午",
        "巳": "酉", "酉": "酉", "丑": "酉",
        "亥": "卯", "卯": "卯", "未": "卯",
    }
    jx_target = jiangxing_map.get(year_zhi)
    if jx_target and jx_target in all_zhi:
        results.append("将星")

    # 羊刃
    yangren_map = {
        "甲": "卯", "丙": "午", "戊": "午",
        "庚": "酉", "壬": "子",
    }
    yr_target = yangren_map.get(day_gan)
    if yr_target and yr_target in all_zhi:
        results.append("羊刃")

    # 禄神
    lushen_map = {
        "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
        "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
    }
    lu_target = lushen_map.get(day_gan)
    if lu_target and lu_target in all_zhi:
        results.append("禄神")

    return results[:5] if len(results) > 5 else results


# ---------------------------------------------------------------------------
# 真太阳时计算
# ---------------------------------------------------------------------------

def get_longitude(birth_place: str) -> float:
    """根据出生地获取经度，默认北京。"""
    coords = CITY_COORDS.get(birth_place)
    if coords:
        return coords[1]
    # 尝试模糊匹配
    for city, (_, lon) in CITY_COORDS.items():
        if city in birth_place or birth_place in city:
            return lon
    return 116.4074  # 默认北京


def get_coords(birth_place: str) -> tuple[float, float]:
    """根据出生地获取经纬度。"""
    coords = CITY_COORDS.get(birth_place)
    if coords:
        return coords
    for city, c in CITY_COORDS.items():
        if city in birth_place or birth_place in city:
            return c
    return (39.9042, 116.4074)


def calc_true_solar_time(
    dt: datetime.datetime, longitude: float
) -> datetime.datetime:
    """计算真太阳时。

    真太阳时 = 地方平太阳时 + 时差方程
    地方平太阳时 = 北京时间 + (当地经度 - 120°) * 4分钟/度
    """
    # 经度修正 (每度4分钟)
    lon_correction_minutes = (longitude - 120.0) * 4.0

    # 时差方程 (Equation of Time) 简化计算
    day_of_year = dt.timetuple().tm_yday
    b = 2 * math.pi * (day_of_year - 81) / 365.0
    eot_minutes = (
        9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    )

    total_correction = lon_correction_minutes + eot_minutes
    return dt + datetime.timedelta(minutes=total_correction)


def hour_to_dizhi_index(hour: int, minute: int = 0) -> int:
    """将小时转换为地支索引(0-11)。

    子时: 23:00-01:00 -> 0
    丑时: 01:00-03:00 -> 1
    ...
    """
    total = hour * 60 + minute
    if total >= 23 * 60 or total < 1 * 60:
        return 0  # 子
    return (hour + 1) // 2


def calc_hour_pillar(day_gan_idx: int, hour_zhi_idx: int) -> tuple[str, str]:
    """根据日干和时支计算时柱天干。

    甲己日起甲子时、乙庚日起丙子时、丙辛日起戊子时、
    丁壬日起庚子时、戊癸日起壬子时。
    """
    base_map = {0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8}
    hour_gan_idx = (base_map[day_gan_idx] + hour_zhi_idx) % 10
    return TIAN_GAN[hour_gan_idx], DI_ZHI[hour_zhi_idx]


# ---------------------------------------------------------------------------
# 日主强弱评分 (100分模型)
# ---------------------------------------------------------------------------

def calc_day_master_strength(
    day_gan: str,
    month_zhi: str,
    all_gans: list[str],
    all_zhis: list[str],
) -> tuple[int, str]:
    """计算日主强弱评分 (0-100)。

    基于月令得分(40分) + 其他干支得分(60分)。
    返回 (分数, 强弱判断)。
    """
    day_wx = GAN_WUXING[day_gan]
    score = 0

    # 月令得分 (最大40分)
    month_wx = ZHI_WUXING[month_zhi]
    if month_wx == day_wx:
        score += 30  # 得令
    elif WUXING_SHENG_WO[day_wx] == month_wx:
        score += 25  # 生我
    elif WUXING_SHENG[day_wx] == month_wx:
        score += 10  # 我泄
    elif WUXING_KE[day_wx] == month_wx:
        score += 8   # 我耗
    elif WUXING_KE_WO[day_wx] == month_wx:
        score += 5   # 克我

    # 月令藏干加分
    for cg in CANG_GAN.get(month_zhi, []):
        cg_wx = GAN_WUXING[cg]
        if cg_wx == day_wx or WUXING_SHENG_WO[day_wx] == cg_wx:
            score += 3

    # 其他干支得分 (最大60分, 每个约5-8分)
    other_gans = [g for g in all_gans if g != day_gan]
    for g in other_gans:
        g_wx = GAN_WUXING[g]
        if g_wx == day_wx:
            score += 6
        elif WUXING_SHENG_WO[day_wx] == g_wx:
            score += 5
        elif WUXING_SHENG[day_wx] == g_wx:
            score -= 2
        elif WUXING_KE[day_wx] == g_wx:
            score -= 3
        elif WUXING_KE_WO[day_wx] == g_wx:
            score -= 4

    other_zhis = [z for z in all_zhis if z != month_zhi]
    for z in other_zhis:
        for cg in CANG_GAN.get(z, []):
            cg_wx = GAN_WUXING[cg]
            if cg_wx == day_wx:
                score += 4
            elif WUXING_SHENG_WO[day_wx] == cg_wx:
                score += 3
            elif WUXING_SHENG[day_wx] == cg_wx:
                score -= 1
            elif WUXING_KE[day_wx] == cg_wx:
                score -= 2
            elif WUXING_KE_WO[day_wx] == cg_wx:
                score -= 3

    # 限制在 0-100
    score = max(0, min(100, score))

    if score >= 60:
        strength = "身强"
    elif score >= 40:
        strength = "中和"
    else:
        strength = "身弱"

    return score, strength


def calc_xiyong(day_gan: str, strength: str) -> dict[str, list[str]]:
    """根据日主强弱初步判断喜用神和忌神。"""
    day_wx = GAN_WUXING[day_gan]

    if strength == "身强":
        # 身强喜: 克泄耗 (官杀、食伤、财)
        xi = [WUXING_KE_WO[day_wx], WUXING_SHENG[day_wx], WUXING_KE[day_wx]]
        ji = [day_wx, WUXING_SHENG_WO[day_wx]]
    elif strength == "身弱":
        # 身弱喜: 生扶 (印、比劫)
        xi = [WUXING_SHENG_WO[day_wx], day_wx]
        ji = [WUXING_KE_WO[day_wx], WUXING_SHENG[day_wx], WUXING_KE[day_wx]]
    else:
        # 中和: 视具体情况, 简化处理
        xi = [WUXING_SHENG[day_wx], WUXING_KE[day_wx]]
        ji = [WUXING_KE_WO[day_wx]]

    return {"喜用神": xi, "忌神": ji}


# ---------------------------------------------------------------------------
# Tool 1: 八字排盘
# ---------------------------------------------------------------------------

def bazi_paipan(
    birth_date: str,
    birth_time: str,
    gender: str,
    birth_place: str = "北京",
) -> dict[str, Any]:
    """完整的八字排盘计算。"""
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":"))

    # 真太阳时修正
    longitude = get_longitude(birth_place)
    dt = datetime.datetime(year, month, day, hour, minute)
    true_solar_dt = calc_true_solar_time(dt, longitude)

    # 使用 cnlunar 获取干支
    lunar = cnlunar.Lunar(true_solar_dt)

    year_gz = lunar.year8Char
    month_gz = lunar.month8Char
    day_gz = lunar.day8Char

    # 时柱计算
    hour_zhi_idx = hour_to_dizhi_index(true_solar_dt.hour, true_solar_dt.minute)
    day_gan_idx = TIAN_GAN.index(day_gz[0])
    hour_gan, hour_zhi = calc_hour_pillar(day_gan_idx, hour_zhi_idx)
    hour_gz = hour_gan + hour_zhi

    # 四柱拆解
    pillars = {
        "年柱": {"天干": year_gz[0], "地支": year_gz[1]},
        "月柱": {"天干": month_gz[0], "地支": month_gz[1]},
        "日柱": {"天干": day_gz[0], "地支": day_gz[1]},
        "时柱": {"天干": hour_gan, "地支": hour_zhi},
    }

    day_gan = day_gz[0]
    day_zhi = day_gz[1]

    # 十神
    for key, p in pillars.items():
        if key == "日柱":
            p["十神"] = "日主"
        else:
            p["十神"] = _get_shishen(day_gan, p["天干"])

    # 藏干及藏干十神
    for key, p in pillars.items():
        zhi = p["地支"]
        cg_list = CANG_GAN.get(zhi, [])
        p["藏干"] = cg_list
        p["藏干十神"] = [_get_shishen(day_gan, cg) for cg in cg_list]

    # 纳音
    for key, p in pillars.items():
        gz = p["天干"] + p["地支"]
        p["纳音"] = NAYIN_TABLE.get(gz, "")

    # 五行统计
    all_gans = [p["天干"] for p in pillars.values()]
    all_zhis = [p["地支"] for p in pillars.values()]

    wuxing_count: dict[str, int] = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for g in all_gans:
        wuxing_count[GAN_WUXING[g]] += 1
    for z in all_zhis:
        wuxing_count[ZHI_WUXING[z]] += 1

    # 日主强弱
    month_zhi = pillars["月柱"]["地支"]
    score, strength = calc_day_master_strength(day_gan, month_zhi, all_gans, all_zhis)

    # 喜用忌神
    xiyong = calc_xiyong(day_gan, strength)

    # 神煞
    year_zhi = pillars["年柱"]["地支"]
    hour_zhi_char = pillars["时柱"]["地支"]
    shensha = _calc_shensha(year_zhi, day_gan, day_zhi, month_zhi, hour_zhi_char)

    return {
        "真太阳时": true_solar_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "经度修正": f"出生地{birth_place}(经度{longitude}°)",
        "四柱": pillars,
        "日主": {
            "天干": day_gan,
            "五行": GAN_WUXING[day_gan],
            "阴阳": GAN_YINYANG[day_gan],
        },
        "日主强弱": {"分数": score, "判断": strength},
        "五行统计": wuxing_count,
        "喜用神": xiyong["喜用神"],
        "忌神": xiyong["忌神"],
        "神煞": shensha,
        "性别": gender,
    }


# ---------------------------------------------------------------------------
# Tool 2: 农历/节气转换
# ---------------------------------------------------------------------------

def lunar_convert(
    date_str: str,
    direction: str = "solar_to_lunar",
    leap: bool = False,
) -> dict[str, Any]:
    """农历公历互转，并返回节气等信息。"""
    parts = list(map(int, date_str.split("-")))
    year, month, day = parts[0], parts[1], parts[2]

    if direction == "solar_to_lunar":
        solar = Solar(year, month, day)
        lunar_date = Converter.Solar2Lunar(solar)
        result_date = f"{lunar_date.year}-{lunar_date.month:02d}-{lunar_date.day:02d}"
        is_leap = lunar_date.isleap

        # 使用 cnlunar 获取详细信息
        dt = datetime.datetime(year, month, day, 12, 0)
        lun = cnlunar.Lunar(dt)

        lunar_month_cn = lun.lunarMonthCn
        lunar_day_cn = lun.lunarDayCn

        return {
            "转换方向": "公历→农历",
            "公历日期": date_str,
            "农历日期": result_date,
            "农历中文": f"{lun.lunarYearCn}年{lunar_month_cn}{lunar_day_cn}",
            "是否闰月": is_leap,
            "当日节气": lun.todaySolarTerms if lun.todaySolarTerms != "无" else "非节气日",
            "下一节气": lun.nextSolarTerm,
            "下一节气日期": f"{year}-{lun.nextSolarTermDate[0]:02d}-{lun.nextSolarTermDate[1]:02d}",
            "干支年": lun.year8Char,
            "生肖": lun.chineseYearZodiac,
            "干支月": lun.month8Char,
            "干支日": lun.day8Char,
            "星期": lun.weekDayCn,
            "星座": lun.starZodiac,
        }
    else:
        # 农历转公历
        lunar_date = Lunar(year, month, day, isleap=leap)
        solar_date = Converter.Lunar2Solar(lunar_date)
        solar_str = f"{solar_date.year}-{solar_date.month:02d}-{solar_date.day:02d}"

        dt = datetime.datetime(solar_date.year, solar_date.month, solar_date.day, 12, 0)
        lun = cnlunar.Lunar(dt)

        return {
            "转换方向": "农历→公历",
            "农历日期": date_str,
            "是否闰月": leap,
            "公历日期": solar_str,
            "农历中文": f"{lun.lunarYearCn}年{lun.lunarMonthCn}{lun.lunarDayCn}",
            "当日节气": lun.todaySolarTerms if lun.todaySolarTerms != "无" else "非节气日",
            "下一节气": lun.nextSolarTerm,
            "干支年": lun.year8Char,
            "生肖": lun.chineseYearZodiac,
            "干支月": lun.month8Char,
            "干支日": lun.day8Char,
            "星期": lun.weekDayCn,
        }


# ---------------------------------------------------------------------------
# Tool 3: 大运流年
# ---------------------------------------------------------------------------

def dayun_liunian(
    birth_date: str,
    birth_time: str,
    gender: str,
    birth_place: str = "北京",
) -> dict[str, Any]:
    """计算大运和流年。"""
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":"))

    longitude = get_longitude(birth_place)
    dt = datetime.datetime(year, month, day, hour, minute)
    true_solar_dt = calc_true_solar_time(dt, longitude)

    lunar = cnlunar.Lunar(true_solar_dt)
    year_gz = lunar.year8Char
    month_gz = lunar.month8Char

    year_gan = year_gz[0]
    year_gan_idx = TIAN_GAN.index(year_gan)

    # 判断顺逆排
    # 阳年: 甲丙戊庚壬 (index 0,2,4,6,8)
    is_yang_year = year_gan_idx % 2 == 0
    is_male = gender.lower() in ("male", "男")

    # 阳年男/阴年女 → 顺排; 阳年女/阴年男 → 逆排
    is_shun = (is_yang_year and is_male) or (not is_yang_year and not is_male)
    direction = "顺排" if is_shun else "逆排"
    direction_explain = (
        f"{'阳' if is_yang_year else '阴'}年"
        f"{'男' if is_male else '女'}"
        f"→{direction}"
    )

    # 起运岁数计算
    # 顺排: 出生日到下一个节气的天数 / 3 = 起运岁数
    # 逆排: 出生日到上一个节气的天数 / 3 = 起运岁数
    solar_terms_dic = lunar.thisYearSolarTermsDic
    birth_day_of_year = true_solar_dt.timetuple().tm_yday

    # 收集该年所有节气日期并排序 (只取节: 立春、惊蛰、清明、立夏、芒种、小暑、立秋、白露、寒露、立冬、大雪、小寒)
    jie_names = ["小寒", "立春", "惊蛰", "清明", "立夏", "芒种",
                 "小暑", "立秋", "白露", "寒露", "立冬", "大雪"]

    jie_dates: list[tuple[str, int]] = []
    for name in jie_names:
        if name in solar_terms_dic:
            m, d = solar_terms_dic[name]
            jie_dt = datetime.datetime(year, m, d)
            jie_dates.append((name, jie_dt.timetuple().tm_yday))

    jie_dates.sort(key=lambda x: x[1])

    if is_shun:
        # 找出生日之后的最近的节
        next_jie_days = None
        for name, doy in jie_dates:
            if doy > birth_day_of_year:
                next_jie_days = doy - birth_day_of_year
                break
        if next_jie_days is None:
            next_jie_days = 30  # 跨年的情况，简化处理
    else:
        # 找出生日之前的最近的节
        prev_jie_days = None
        for name, doy in reversed(jie_dates):
            if doy <= birth_day_of_year:
                prev_jie_days = birth_day_of_year - doy
                break
        if prev_jie_days is None:
            prev_jie_days = 30
        next_jie_days = prev_jie_days

    # 每3天折算1年，余数折算月
    start_age = round(next_jie_days / 3)
    if start_age < 1:
        start_age = 1

    # 排大运
    month_gan_idx = TIAN_GAN.index(month_gz[0])
    month_zhi_idx = DI_ZHI.index(month_gz[1])

    dayun_list: list[dict[str, Any]] = []
    current_year = datetime.datetime.now().year
    current_age = current_year - year

    for i in range(1, 10):  # 排8-9步大运
        if is_shun:
            gan_idx = (month_gan_idx + i) % 10
            zhi_idx = (month_zhi_idx + i) % 12
        else:
            gan_idx = (month_gan_idx - i) % 10
            zhi_idx = (month_zhi_idx - i) % 12

        age_start = start_age + (i - 1) * 10
        age_end = age_start + 9
        gz = TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]

        entry: dict[str, Any] = {
            "序号": i,
            "年龄范围": f"{age_start}-{age_end}岁",
            "起始年份": year + age_start,
            "干支": gz,
            "天干": TIAN_GAN[gan_idx],
            "地支": DI_ZHI[zhi_idx],
            "五行": GAN_WUXING[TIAN_GAN[gan_idx]] + ZHI_WUXING[DI_ZHI[zhi_idx]],
            "纳音": NAYIN_TABLE.get(gz, ""),
        }
        if age_start <= current_age <= age_end:
            entry["当前大运"] = True
        dayun_list.append(entry)

    # 近10年流年
    liunian_list: list[dict[str, Any]] = []
    for y in range(current_year - 2, current_year + 8):
        # 计算该年干支
        gan_idx = (y - 4) % 10
        zhi_idx = (y - 4) % 12
        gz = TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]
        age = y - year
        liunian_list.append({
            "年份": y,
            "年龄": age,
            "干支": gz,
            "天干": TIAN_GAN[gan_idx],
            "地支": DI_ZHI[zhi_idx],
            "五行": GAN_WUXING[TIAN_GAN[gan_idx]] + ZHI_WUXING[DI_ZHI[zhi_idx]],
            "纳音": NAYIN_TABLE.get(gz, ""),
            "生肖": SHENGXIAO[zhi_idx],
        })

    return {
        "排运方向": direction,
        "方向说明": direction_explain,
        "起运岁数": start_age,
        "起运说明": f"出生后距最近节气{next_jie_days}天，折合约{start_age}岁起运",
        "年柱": year_gz,
        "月柱": month_gz,
        "大运列表": dayun_list,
        "近十年流年": liunian_list,
    }


# ---------------------------------------------------------------------------
# Tool 4: 梅花易数起卦
# ---------------------------------------------------------------------------

def meihua_qigua(
    numbers: list[int] | None = None,
    method: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """梅花易数起卦。

    三种方式:
    1. 数字起卦: numbers=[上卦数, 下卦数, 动爻数]
    2. 时间起卦: method="time"
    3. 文字起卦: text="某某"
    """
    if numbers and len(numbers) >= 3:
        upper_num = numbers[0]
        lower_num = numbers[1]
        dong_num = numbers[2]
    elif text:
        # 文字起卦: 按笔画数
        # 简化: 使用字符 Unicode 编码之和
        chars = list(text)
        if len(chars) == 1:
            total = ord(chars[0])
            upper_num = total
            lower_num = total
            dong_num = total
        elif len(chars) == 2:
            upper_num = ord(chars[0])
            lower_num = ord(chars[1])
            dong_num = upper_num + lower_num
        else:
            mid = len(chars) // 2
            upper_num = sum(ord(c) for c in chars[:mid])
            lower_num = sum(ord(c) for c in chars[mid:])
            dong_num = upper_num + lower_num
    else:
        # 时间起卦
        now = datetime.datetime.now()
        lunar = cnlunar.Lunar(now)
        # 年数+月数+日数 为上卦, 年数+月数+日数+时辰数 为下卦
        year_num = DI_ZHI.index(lunar.year8Char[1]) + 1
        month_num = lunar.lunarMonth
        day_num = lunar.lunarDay
        hour_idx = hour_to_dizhi_index(now.hour, now.minute) + 1

        upper_num = year_num + month_num + day_num
        lower_num = upper_num + hour_idx
        dong_num = lower_num

    # 取卦 (1-8)
    upper_gua = ((upper_num - 1) % 8) + 1
    lower_gua = ((lower_num - 1) % 8) + 1
    # 动爻 (1-6)
    dong_yao = ((dong_num - 1) % 6) + 1

    upper_info = BAGUA[upper_gua]
    lower_info = BAGUA[lower_gua]

    # 本卦
    ben_gua = SIXTY_FOUR_GUA.get((upper_gua, lower_gua), ("未知卦", 0))

    # 互卦: 本卦2,3,4爻为下卦; 3,4,5爻为上卦
    # 需要知道6爻组合
    # 上卦3爻 + 下卦3爻 = 6爻 (从下到上: 1,2,3为下卦; 4,5,6为上卦)
    def gua_to_yaos(gua_num: int) -> list[int]:
        """获取三爻 (从下到上)。"""
        # 乾=111, 兑=110, 离=101, 震=001, 巽=011, 坎=010, 艮=100, 坤=000
        yao_map = {
            1: [1, 1, 1], 2: [0, 1, 1], 3: [1, 0, 1], 4: [1, 0, 0],
            5: [0, 1, 1], 6: [0, 1, 0], 7: [0, 0, 1], 8: [0, 0, 0],
        }
        # 修正巽卦
        yao_map[5] = [1, 1, 0]
        return yao_map.get(gua_num, [0, 0, 0])

    lower_yaos = gua_to_yaos(lower_gua)  # 1,2,3爻
    upper_yaos = gua_to_yaos(upper_gua)  # 4,5,6爻
    all_yaos = lower_yaos + upper_yaos  # 索引0-5, 从下到上

    # 互卦下卦 = 2,3,4爻 (索引1,2,3)
    hu_lower_yaos = all_yaos[1:4]
    # 互卦上卦 = 3,4,5爻 (索引2,3,4)
    hu_upper_yaos = all_yaos[2:5]

    def yaos_to_gua(yaos: list[int]) -> int:
        """三爻转卦数。"""
        yao_to_gua_map = {
            (1, 1, 1): 1, (0, 1, 1): 2, (1, 0, 1): 3, (1, 0, 0): 4,
            (1, 1, 0): 5, (0, 1, 0): 6, (0, 0, 1): 7, (0, 0, 0): 8,
        }
        return yao_to_gua_map.get(tuple(yaos), 8)

    hu_upper = yaos_to_gua(hu_upper_yaos)
    hu_lower = yaos_to_gua(hu_lower_yaos)
    hu_gua = SIXTY_FOUR_GUA.get((hu_upper, hu_lower), ("未知卦", 0))

    # 变卦: 动爻变 (阳变阴, 阴变阳)
    bian_yaos = all_yaos.copy()
    bian_yaos[dong_yao - 1] = 1 - bian_yaos[dong_yao - 1]
    bian_lower = yaos_to_gua(bian_yaos[:3])
    bian_upper = yaos_to_gua(bian_yaos[3:])
    bian_gua = SIXTY_FOUR_GUA.get((bian_upper, bian_lower), ("未知卦", 0))

    # 体用关系
    # 动爻在下卦(1-3爻)→下卦为用,上卦为体; 动爻在上卦(4-6爻)→上卦为用,下卦为体
    if dong_yao <= 3:
        ti_gua_num = upper_gua
        yong_gua_num = lower_gua
        ti_label = "上卦"
        yong_label = "下卦"
    else:
        ti_gua_num = lower_gua
        yong_gua_num = upper_gua
        ti_label = "下卦"
        yong_label = "上卦"

    ti_wx = BAGUA[ti_gua_num][2]
    yong_wx = BAGUA[yong_gua_num][2]

    # 体用五行关系
    if ti_wx == yong_wx:
        tiyong_rel = "比和(同类)"
    elif WUXING_SHENG[yong_wx] == ti_wx:
        tiyong_rel = "用生体(吉)"
    elif WUXING_SHENG[ti_wx] == yong_wx:
        tiyong_rel = "体生用(泄)"
    elif WUXING_KE[yong_wx] == ti_wx:
        tiyong_rel = "用克体(凶)"
    elif WUXING_KE[ti_wx] == yong_wx:
        tiyong_rel = "体克用(吉,有得)"
    else:
        tiyong_rel = "待分析"

    return {
        "起卦方式": "数字起卦" if numbers else ("文字起卦" if text else "时间起卦"),
        "上卦": {
            "卦名": upper_info[0], "象": upper_info[1],
            "五行": upper_info[2], "卦数": upper_gua,
        },
        "下卦": {
            "卦名": lower_info[0], "象": lower_info[1],
            "五行": lower_info[2], "卦数": lower_gua,
        },
        "本卦": {"卦名": ben_gua[0], "序号": ben_gua[1]},
        "互卦": {
            "卦名": hu_gua[0], "序号": hu_gua[1],
            "上卦": BAGUA[hu_upper][0], "下卦": BAGUA[hu_lower][0],
        },
        "变卦": {
            "卦名": bian_gua[0], "序号": bian_gua[1],
            "上卦": BAGUA[bian_upper][0], "下卦": BAGUA[bian_lower][0],
        },
        "动爻": f"第{dong_yao}爻",
        "体用关系": {
            "体卦": f"{ti_label}({BAGUA[ti_gua_num][0]})",
            "用卦": f"{yong_label}({BAGUA[yong_gua_num][0]})",
            "体五行": ti_wx,
            "用五行": yong_wx,
            "关系": tiyong_rel,
        },
        "六爻": ["阳" if y == 1 else "阴" for y in all_yaos],
    }


# ---------------------------------------------------------------------------
# Tool 5: 紫微斗数排盘
# ---------------------------------------------------------------------------

# 紫微十四主星
ZIWEI_14_STARS = [
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞",
    "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
]

# 十二宫名称
TWELVE_PALACES = [
    "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
    "迁移宫", "交友宫", "事业宫", "田宅宫", "福德宫", "父母宫",
]

# 十二宫位地支 (固定排列，从寅开始逆时针)
PALACE_DIZHI = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

# 五行局
WUXING_JU: dict[tuple[str, str], tuple[str, int]] = {
    # (命宫天干, 命宫地支纳音) -> (局名, 局数)
}

# 简化的五行局映射: 根据命宫干支纳音五行
NAYIN_TO_JU: dict[str, tuple[str, int]] = {
    "金": ("金四局", 4), "木": ("木三局", 3), "水": ("水二局", 2),
    "火": ("火六局", 6), "土": ("土五局", 5),
}

# 时辰编号 (子=1, 丑=2, ... 亥=12) — 紫微斗数用
SHICHEN_NUM = {z: i + 1 for i, z in enumerate(DI_ZHI)}


def _calc_ming_palace_idx(lunar_month: int, hour_zhi_idx: int) -> int:
    """计算命宫所在宫位索引(十二宫位从寅=0开始)。

    公式: 命宫位置 = 寅宫 + (月-1) - (时辰-1)
    即: idx = (lunar_month - 1) - hour_zhi_idx
    如果 hour_zhi_idx=0(子时), 则命宫在月+1的位置(因为子时对宫)。

    标准公式: 命宫 = (月数 + 时辰数 - 2) 对应宫位需要取反
    更准确: 从寅宫起，顺数月份到出生月，再逆数时辰。
    """
    # 从寅宫开始，顺数到出生月: idx = lunar_month - 1
    # 然后从该位置逆数时辰: idx = idx - hour_zhi_idx
    idx = (lunar_month - 1 - hour_zhi_idx) % 12
    return idx


def _calc_shen_palace_idx(lunar_month: int, hour_zhi_idx: int) -> int:
    """计算身宫位置。

    身宫公式: 从寅宫起，顺数月份，再顺数时辰。
    """
    idx = (lunar_month - 1 + hour_zhi_idx) % 12
    return idx


def _palace_ganzhi(year_gan_idx: int, palace_zhi_idx: int) -> str:
    """根据年干和宫位地支推算宫位天干。

    五虎遁: 甲己年起丙寅，乙庚年起戊寅，丙辛年起庚寅，丁壬年起壬寅，戊癸年起甲寅。
    """
    base_map = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
    base_gan = base_map[year_gan_idx]
    gan_idx = (base_gan + palace_zhi_idx) % 10
    return TIAN_GAN[gan_idx] + PALACE_DIZHI[palace_zhi_idx]


def _calc_ziwei_star_position(lunar_day: int, ju_num: int) -> int:
    """计算紫微星所在宫位。

    紫微星定位需要根据农历日和五行局数。
    公式: 先求商和余数。
    """
    # 标准算法: 根据局数和日数定紫微位置
    # 紫微起法: day / ju_num 的商+余数决定位置
    quotient = lunar_day // ju_num
    remainder = lunar_day % ju_num

    if remainder == 0:
        # 整除: 紫微在第quotient宫(从寅宫数起)
        pos = quotient - 1
    else:
        # 有余数: 需要根据奇偶调整
        if remainder % 2 == 0:
            # 偶数余数: 向前进
            pos = quotient + remainder // 2
        else:
            # 奇数余数: 向后退
            pos = quotient + (remainder + 1) // 2

    return pos % 12


def _place_ziwei_series(ziwei_pos: int) -> dict[str, str]:
    """根据紫微星位置排布紫微系星。

    紫微系: 紫微、天机、太阳、武曲、天同、廉贞
    从紫微起,按固定间距排列。
    """
    # 紫微系星距紫微的宫位偏移 (逆时针)
    offsets = {
        "紫微": 0, "天机": -1, "太阳": -3, "武曲": -4,
        "天同": -5, "廉贞": -8,
    }
    result = {}
    for star, offset in offsets.items():
        pos = (ziwei_pos + offset) % 12
        result[star] = PALACE_DIZHI[pos]
    return result


def _place_tianfu_series(ziwei_pos: int) -> dict[str, str]:
    """根据紫微星位置排布天府系星。

    天府位置 = 紫微的对宫关系。
    天府系: 天府、太阴、贪狼、巨门、天相、天梁、七杀、破军
    """
    # 天府位置: 紫微位置的镜像 (以寅-申轴)
    tianfu_pos = (12 - ziwei_pos + 4) % 12
    # 另一种算法: 查表
    # 简化: 天府=4-紫微 (从辰宫起算)
    tianfu_pos = _calc_tianfu_from_ziwei(ziwei_pos)

    offsets = {
        "天府": 0, "太阴": 1, "贪狼": 2, "巨门": 3,
        "天相": 4, "天梁": 5, "七杀": 6, "破军": 10,
    }
    result = {}
    for star, offset in offsets.items():
        pos = (tianfu_pos + offset) % 12
        result[star] = PALACE_DIZHI[pos]
    return result


def _calc_tianfu_from_ziwei(ziwei_pos: int) -> int:
    """天府与紫微的对应关系。

    紫微在子→天府在辰; 紫微在丑→天府在卯; 紫微在寅→天府在寅;
    紫微在卯→天府在丑; 紫微在辰→天府在子; 紫微在巳→天府在亥;
    紫微在午→天府在戌; 紫微在未→天府在酉; 紫微在申→天府在申;
    紫微在酉→天府在未; 紫微在戌→天府在午; 紫微在亥→天府在巳;
    """
    # 紫微地支索引(PALACE_DIZHI从寅开始): 0=寅,1=卯,...,10=子,11=丑
    # 转为标准地支索引: 寅=2,卯=3,...子=0,丑=1
    zw_std = (ziwei_pos + 2) % 12  # 转为子=0的标准地支
    # 天府标准 = (12 - zw_std + 4) % 12 = (16 - zw_std) % 12
    tf_std = (16 - zw_std) % 12
    # 转回宫位索引
    return (tf_std - 2) % 12


def _calc_four_hua(year_gan_idx: int) -> dict[str, str]:
    """计算四化飞星 (化禄、化权、化科、化忌)。"""
    # 四化表: 每个年干对应四颗星的化
    SIHUA_TABLE = {
        0: {"化禄": "廉贞", "化权": "破军", "化科": "武曲", "化忌": "太阳"},  # 甲
        1: {"化禄": "天机", "化权": "天梁", "化科": "紫微", "化忌": "太阴"},  # 乙
        2: {"化禄": "天同", "化权": "天机", "化科": "文昌", "化忌": "廉贞"},  # 丙
        3: {"化禄": "太阴", "化权": "天同", "化科": "天机", "化忌": "巨门"},  # 丁
        4: {"化禄": "贪狼", "化权": "太阴", "化科": "右弼", "化忌": "天机"},  # 戊
        5: {"化禄": "武曲", "化权": "贪狼", "化科": "天梁", "化忌": "文曲"},  # 己
        6: {"化禄": "太阳", "化权": "武曲", "化科": "太阴", "化忌": "天同"},  # 庚
        7: {"化禄": "巨门", "化权": "太阳", "化科": "文曲", "化忌": "文昌"},  # 辛
        8: {"化禄": "天梁", "化权": "紫微", "化科": "左辅", "化忌": "武曲"},  # 壬
        9: {"化禄": "破军", "化权": "巨门", "化科": "太阴", "化忌": "贪狼"},  # 癸
    }
    return SIHUA_TABLE.get(year_gan_idx, {})


def ziwei_paipan(
    birth_date: str,
    birth_time: str,
    gender: str,
) -> dict[str, Any]:
    """紫微斗数排盘。"""
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":"))

    dt = datetime.datetime(year, month, day, hour, minute)
    lunar = cnlunar.Lunar(dt)

    lunar_year = lunar.lunarYear
    lunar_month = lunar.lunarMonth
    lunar_day = lunar.lunarDay
    is_leap = lunar.isLunarLeapMonth

    year_gan_idx = (lunar_year - 4) % 10
    hour_zhi_idx = hour_to_dizhi_index(hour, minute)

    # 命宫位置
    ming_idx = _calc_ming_palace_idx(lunar_month, hour_zhi_idx)
    shen_idx = _calc_shen_palace_idx(lunar_month, hour_zhi_idx)

    # 命宫干支
    ming_gz = _palace_ganzhi(year_gan_idx, ming_idx)

    # 五行局 (根据命宫干支纳音)
    nayin = NAYIN_TABLE.get(ming_gz, "")
    nayin_wx = ""
    for wx in ["金", "木", "水", "火", "土"]:
        if wx in nayin:
            nayin_wx = wx
            break
    if not nayin_wx:
        nayin_wx = "水"  # 默认

    ju_name, ju_num = NAYIN_TO_JU[nayin_wx]

    # 紫微星位置
    ziwei_pos = _calc_ziwei_star_position(lunar_day, ju_num)

    # 排布主星
    ziwei_series = _place_ziwei_series(ziwei_pos)
    tianfu_series = _place_tianfu_series(ziwei_pos)
    all_stars = {**ziwei_series, **tianfu_series}

    # 十二宫排列
    palaces: list[dict[str, Any]] = []
    for i in range(12):
        palace_idx = (ming_idx + i) % 12
        palace_gz = _palace_ganzhi(year_gan_idx, palace_idx)
        stars_in_palace = [
            star for star, pos in all_stars.items()
            if pos == PALACE_DIZHI[palace_idx]
        ]
        palace_info: dict[str, Any] = {
            "宫名": TWELVE_PALACES[i],
            "宫位": PALACE_DIZHI[palace_idx],
            "干支": palace_gz,
            "主星": stars_in_palace,
        }
        if palace_idx == shen_idx:
            palace_info["身宫"] = True
        palaces.append(palace_info)

    # 四化
    sihua = _calc_four_hua(year_gan_idx)

    # 当前大限 (每10年一个大限)
    current_year = datetime.datetime.now().year
    current_age = current_year - year
    daxian_start_ages = list(range(ju_num, 120, 10))
    current_daxian = ""
    for i, start_age in enumerate(daxian_start_ages):
        if start_age <= current_age < start_age + 10:
            daxian_idx = (ming_idx + i) % 12 if gender in ("male", "男") else (ming_idx - i) % 12
            current_daxian = f"{PALACE_DIZHI[daxian_idx]}({start_age}-{start_age + 9}岁)"
            break

    return {
        "农历": f"{lunar_year}年{lunar_month}月{lunar_day}日",
        "是否闰月": is_leap,
        "命宫": {
            "位置": PALACE_DIZHI[ming_idx],
            "干支": ming_gz,
        },
        "身宫": {"位置": PALACE_DIZHI[shen_idx]},
        "五行局": ju_name,
        "局数": ju_num,
        "十二宫": palaces,
        "紫微星位置": PALACE_DIZHI[ziwei_pos],
        "主星分布": all_stars,
        "四化飞星": sihua,
        "当前大限": current_daxian if current_daxian else "暂未计算",
        "性别": gender,
    }


# ---------------------------------------------------------------------------
# Tool 6: 奇门遁甲排盘
# ---------------------------------------------------------------------------

# 九宫 (洛书数)
JIUGONG_NAMES = ["一宫(坎)", "二宫(坤)", "三宫(震)", "四宫(巽)",
                 "五宫(中)", "六宫(乾)", "七宫(兑)", "八宫(艮)", "九宫(离)"]

# 三奇六仪
SANQI_LIUYI = ["戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"]
# 甲子戊, 甲戌己, 甲申庚, 甲午辛, 甲辰壬, 甲寅癸

# 八门
BA_MEN = ["休门", "死门", "伤门", "杜门", "中(无门)", "开门", "惊门", "生门", "景门"]

# 九星
JIU_XING = ["天蓬", "天芮", "天冲", "天辅", "天禽", "天心", "天柱", "天任", "天英"]

# 八神 (阳遁)
BA_SHEN_YANG = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]
BA_SHEN_YIN = ["值符", "九天", "九地", "玄武", "白虎", "六合", "太阴", "腾蛇"]

# 24节气用于判断阴阳遁
# 冬至后用阳遁，夏至后用阴遁
YANG_DUN_JIEQI = ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
                   "春分", "清明", "谷雨", "立夏", "小满", "芒种"]
YIN_DUN_JIEQI = ["夏至", "小暑", "大暑", "立秋", "处暑", "白露",
                  "秋分", "寒露", "霜降", "立冬", "小雪", "大雪"]

# 节气对应的遁数 (上中下三元)
JIEQI_JU: dict[str, list[int]] = {
    # 阳遁
    "冬至": [1, 7, 4], "小寒": [2, 8, 5], "大寒": [3, 9, 6],
    "立春": [8, 5, 2], "雨水": [9, 6, 3], "惊蛰": [1, 7, 4],
    "春分": [3, 9, 6], "清明": [4, 1, 7], "谷雨": [5, 2, 8],
    "立夏": [4, 1, 7], "小满": [5, 2, 8], "芒种": [6, 3, 9],
    # 阴遁
    "夏至": [9, 3, 6], "小暑": [8, 2, 5], "大暑": [7, 1, 4],
    "立秋": [2, 5, 8], "处暑": [1, 4, 7], "白露": [9, 3, 6],
    "秋分": [7, 1, 4], "寒露": [6, 9, 3], "霜降": [5, 8, 2],
    "立冬": [6, 9, 3], "小雪": [5, 8, 2], "大雪": [4, 7, 1],
}


def _determine_yinyang_dun(dt: datetime.datetime) -> tuple[str, str, int]:
    """判断阴遁/阳遁及局数。

    返回: (阴遁/阳遁, 当前节气, 局数)
    """
    lunar = cnlunar.Lunar(dt)
    solar_terms = lunar.thisYearSolarTermsDic

    # 找到当前所处的节气
    current_jieqi = ""
    current_day = (dt.month, dt.day)

    # 按节气排序
    sorted_terms = sorted(solar_terms.items(), key=lambda x: (x[1][0], x[1][1]))

    for i, (name, (m, d)) in enumerate(sorted_terms):
        if (m, d) <= current_day:
            current_jieqi = name

    if not current_jieqi:
        current_jieqi = "冬至"

    # 判断上中下三元
    # 简化: 使用日干支的旬来判断
    day_gz = lunar.day8Char
    day_gan_idx = TIAN_GAN.index(day_gz[0])
    day_zhi_idx = DI_ZHI.index(day_gz[1])

    # 求旬首: 天干地支索引差决定所在旬
    xun_idx = (day_zhi_idx - day_gan_idx) % 12
    # 甲子旬(0)=上元, 甲戌旬(10)=中元, 甲申旬(8)=下元
    # 简化三元判断
    if xun_idx in (0, 6):
        yuan = 0  # 上元
    elif xun_idx in (2, 8):
        yuan = 2  # 下元
    else:
        yuan = 1  # 中元

    is_yang = current_jieqi in YANG_DUN_JIEQI
    dun_type = "阳遁" if is_yang else "阴遁"

    ju_list = JIEQI_JU.get(current_jieqi, [1, 4, 7])
    ju_num = ju_list[yuan]

    return dun_type, current_jieqi, ju_num


def _get_xunshou(day_gz: str) -> str:
    """获取旬首 (日干支所在旬的甲X)。"""
    gan_idx = TIAN_GAN.index(day_gz[0])
    zhi_idx = DI_ZHI.index(day_gz[1])
    # 旬首地支 = 当前地支 - 当前天干索引
    xun_zhi_idx = (zhi_idx - gan_idx) % 12
    return "甲" + DI_ZHI[xun_zhi_idx]


def _get_kongwang(day_gz: str) -> list[str]:
    """获取空亡 (日干支所在旬的最后两个地支)。"""
    gan_idx = TIAN_GAN.index(day_gz[0])
    zhi_idx = DI_ZHI.index(day_gz[1])
    xun_zhi_idx = (zhi_idx - gan_idx) % 12
    # 空亡 = 该旬未用到的两个地支
    kong1 = DI_ZHI[(xun_zhi_idx + 10) % 12]
    kong2 = DI_ZHI[(xun_zhi_idx + 11) % 12]
    return [kong1, kong2]


def qimen_paipan(
    datetime_str: str,
    qimen_type: str = "时家奇门",
) -> dict[str, Any]:
    """奇门遁甲排盘。"""
    dt = datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
    lunar = cnlunar.Lunar(dt)

    day_gz = lunar.day8Char
    hour_zhi_idx = hour_to_dizhi_index(dt.hour, dt.minute)
    hour_gz = calc_hour_pillar(TIAN_GAN.index(day_gz[0]), hour_zhi_idx)
    hour_gz_str = hour_gz[0] + hour_gz[1]

    dun_type, jieqi, ju_num = _determine_yinyang_dun(dt)
    xunshou = _get_xunshou(day_gz)
    kongwang = _get_kongwang(day_gz)

    is_yang = dun_type == "阳遁"

    # 排九宫 (简化版)
    # 洛书九宫: 4 9 2 / 3 5 7 / 8 1 6
    luoshu = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    # 三奇六仪排布 (根据局数)
    sanqi_positions: dict[int, str] = {}
    if is_yang:
        for i in range(9):
            pos = (ju_num - 1 + i) % 9
            sanqi_positions[pos + 1] = SANQI_LIUYI[i]
    else:
        for i in range(9):
            pos = (ju_num - 1 - i) % 9
            sanqi_positions[pos + 1] = SANQI_LIUYI[i]

    # 八门排布 (根据值使所在宫位)
    # 简化: 休门从值使宫起排
    men_positions: dict[int, str] = {}
    for i in range(9):
        if is_yang:
            pos = (ju_num - 1 + i) % 9
        else:
            pos = (ju_num - 1 - i) % 9
        men_positions[pos + 1] = BA_MEN[i]

    # 九星排布
    xing_positions: dict[int, str] = {}
    for i in range(9):
        if is_yang:
            pos = (ju_num - 1 + i) % 9
        else:
            pos = (ju_num - 1 - i) % 9
        xing_positions[pos + 1] = JIU_XING[i]

    # 八神排布
    shen_list = BA_SHEN_YANG if is_yang else BA_SHEN_YIN
    shen_positions: dict[int, str] = {}
    # 八神从值符宫起排
    for i, shen in enumerate(shen_list):
        pos = (ju_num - 1 + i) % 9
        if pos + 1 == 5:
            continue  # 跳过中宫
        shen_positions[pos + 1] = shen

    # 组装九宫信息
    nine_palaces: list[dict[str, str]] = []
    for gong_num in range(1, 10):
        palace: dict[str, str] = {
            "宫位": JIUGONG_NAMES[gong_num - 1],
        }
        if gong_num in sanqi_positions:
            palace["天盘奇仪"] = sanqi_positions[gong_num]
        if gong_num in men_positions:
            palace["八门"] = men_positions[gong_num]
        if gong_num in xing_positions:
            palace["九星"] = xing_positions[gong_num]
        if gong_num in shen_positions:
            palace["八神"] = shen_positions[gong_num]
        nine_palaces.append(palace)

    # 马星 (根据日支)
    day_zhi = day_gz[1]
    yima_map = {
        "申": "寅", "子": "寅", "辰": "寅",
        "寅": "申", "午": "申", "戌": "申",
        "巳": "亥", "酉": "亥", "丑": "亥",
        "亥": "巳", "卯": "巳", "未": "巳",
    }
    ma_xing = yima_map.get(day_zhi, "")

    return {
        "排盘类型": qimen_type,
        "排盘时间": datetime_str,
        "阴阳遁": dun_type,
        "局数": f"{dun_type}第{ju_num}局",
        "所在节气": jieqi,
        "日干支": day_gz,
        "时干支": hour_gz_str,
        "旬首": xunshou,
        "空亡": kongwang,
        "九宫布局": nine_palaces,
        "马星": ma_xing,
        "值符": xing_positions.get(ju_num, ""),
        "值使": men_positions.get(ju_num, ""),
    }


# ---------------------------------------------------------------------------
# Tool 7: 星座星盘
# ---------------------------------------------------------------------------

def _ecliptic_lon_to_sign(lon_deg: float) -> tuple[str, float]:
    """黄道经度转星座。"""
    idx = int(lon_deg // 30) % 12
    degree_in_sign = lon_deg % 30
    return ZODIAC_SIGNS_ASTRO[idx], round(degree_in_sign, 2)


def _calc_asc(dt_utc: datetime.datetime, lat: float, lon: float) -> float:
    """计算上升点(ASC)的黄道经度。

    使用简化公式，通过 ephem 计算恒星时和黄道倾角来推算。
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.date = ephem.Date(dt_utc)

    # 恒星时(弧度)
    lst = obs.sidereal_time()
    lst_deg = math.degrees(float(lst))

    # 黄道倾角 (约23.44度)
    obliquity = 23.44

    # ASC公式 (简化)
    # tan(ASC) = cos(ARMC) / -(sin(ARMC)*cos(ε) + tan(φ)*sin(ε))
    armc_rad = float(lst)
    eps_rad = math.radians(obliquity)
    phi_rad = math.radians(lat)

    numerator = math.cos(armc_rad)
    denominator = -(
        math.sin(armc_rad) * math.cos(eps_rad)
        + math.tan(phi_rad) * math.sin(eps_rad)
    )

    asc_rad = math.atan2(numerator, denominator)
    asc_deg = math.degrees(asc_rad) % 360

    return asc_deg


def _calc_aspects(positions: dict[str, float]) -> list[dict[str, Any]]:
    """计算主要相位。"""
    aspect_defs = [
        ("合相", 0, 8), ("六合", 60, 6), ("四分", 90, 8),
        ("三合", 120, 8), ("对冲", 180, 8),
    ]
    results: list[dict[str, Any]] = []
    names = list(positions.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            diff = abs(positions[names[i]] - positions[names[j]])
            if diff > 180:
                diff = 360 - diff
            for aspect_name, angle, orb in aspect_defs:
                if abs(diff - angle) <= orb:
                    results.append({
                        "行星1": names[i],
                        "行星2": names[j],
                        "相位": aspect_name,
                        "精确度": round(abs(diff - angle), 2),
                    })
    return results


def xingzuo_xingpan(
    birth_date: str,
    birth_time: str,
    birth_place: str = "北京",
) -> dict[str, Any]:
    """计算星座星盘。"""
    year, month, day = map(int, birth_date.split("-"))
    hour, minute = map(int, birth_time.split(":"))

    lat, lon = get_coords(birth_place)

    # 转UTC (中国时间-8)
    dt_local = datetime.datetime(year, month, day, hour, minute)
    dt_utc = dt_local - datetime.timedelta(hours=8)

    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.date = ephem.Date(dt_utc)

    # 计算各行星位置
    bodies = {
        "太阳": ephem.Sun(obs),
        "月亮": ephem.Moon(obs),
        "水星": ephem.Mercury(obs),
        "金星": ephem.Venus(obs),
        "火星": ephem.Mars(obs),
        "木星": ephem.Jupiter(obs),
        "土星": ephem.Saturn(obs),
    }

    positions: dict[str, float] = {}
    planet_info: list[dict[str, Any]] = []

    for name, body in bodies.items():
        ecl = ephem.Ecliptic(body)
        lon_deg = math.degrees(float(ecl.lon))
        sign, deg_in_sign = _ecliptic_lon_to_sign(lon_deg)
        positions[name] = lon_deg
        planet_info.append({
            "行星": name,
            "星座": sign,
            "度数": f"{int(deg_in_sign)}°{int((deg_in_sign % 1) * 60)}'",
            "黄经": round(lon_deg, 2),
        })

    # 上升星座
    asc_lon = _calc_asc(dt_utc, lat, lon)
    asc_sign, asc_deg = _ecliptic_lon_to_sign(asc_lon)

    # 相位
    aspects = _calc_aspects(positions)

    return {
        "出生地": birth_place,
        "经纬度": f"北纬{lat}° 东经{lon}°",
        "行星位置": planet_info,
        "上升星座": {
            "星座": asc_sign,
            "度数": f"{int(asc_deg)}°{int((asc_deg % 1) * 60)}'",
        },
        "太阳星座": next(p for p in planet_info if p["行星"] == "太阳")["星座"],
        "月亮星座": next(p for p in planet_info if p["行星"] == "月亮")["星座"],
        "主要相位": aspects[:10],  # 最多返回10个
    }


# ---------------------------------------------------------------------------
# Tool 8: 择日黄历
# ---------------------------------------------------------------------------

def zeri_huangli(
    date_str: str | None = None,
    activity: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """择日黄历查询。

    两种模式:
    1. 查询指定日期的黄历信息
    2. 在日期范围内查找适合某活动的吉日
    """
    if date_str:
        # 模式1: 查询指定日期
        year, month, day = map(int, date_str.split("-"))
        dt = datetime.datetime(year, month, day, 12, 0)
        lunar = cnlunar.Lunar(dt)

        # 冲煞
        clash = lunar.chineseZodiacClash

        # 方位
        lucky_dir = lunar.get_luckyGodsDirection()

        return {
            "公历": date_str,
            "农历": f"{lunar.lunarYearCn}年{lunar.lunarMonthCn}{lunar.lunarDayCn}",
            "干支": f"{lunar.year8Char}年 {lunar.month8Char}月 {lunar.day8Char}日",
            "星期": lunar.weekDayCn,
            "生肖": lunar.chineseYearZodiac,
            "节气": lunar.todaySolarTerms if lunar.todaySolarTerms != "无" else "非节气日",
            "建除十二神": lunar.today12DayOfficer,
            "十二神": lunar.today12DayGod,
            "二十八宿": lunar.today28Star,
            "纳音": lunar.get_nayin(),
            "宜": lunar.goodThing,
            "忌": lunar.badThing,
            "吉神宜趋": lunar.goodGodName,
            "凶神宜忌": lunar.badGodName,
            "冲煞": clash,
            "吉方": lucky_dir,
            "日级别": lunar.todayLevelName,
        }
    elif activity and start_date and end_date:
        # 模式2: 择日 - 在范围内找适合该活动的日子
        s_year, s_month, s_day = map(int, start_date.split("-"))
        e_year, e_month, e_day = map(int, end_date.split("-"))
        start = datetime.date(s_year, s_month, s_day)
        end = datetime.date(e_year, e_month, e_day)

        good_days: list[dict[str, str]] = []
        current = start
        while current <= end:
            dt = datetime.datetime(current.year, current.month, current.day, 12, 0)
            lunar = cnlunar.Lunar(dt)
            if activity in lunar.goodThing:
                good_days.append({
                    "公历": current.strftime("%Y-%m-%d"),
                    "农历": f"{lunar.lunarMonthCn}{lunar.lunarDayCn}",
                    "干支日": lunar.day8Char,
                    "星期": lunar.weekDayCn,
                    "建除": lunar.today12DayOfficer,
                    "宜": ", ".join(lunar.goodThing[:8]),
                    "忌": ", ".join(lunar.badThing[:5]),
                })
            current += datetime.timedelta(days=1)

        return {
            "查询活动": activity,
            "查询范围": f"{start_date} ~ {end_date}",
            "吉日列表": good_days,
            "吉日数量": len(good_days),
        }
    else:
        return {"error": "请提供 date 或 (activity + start_date + end_date) 参数"}
