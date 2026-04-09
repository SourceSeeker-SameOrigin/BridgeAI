"""玄学计算工具插件 - 精确的玄学计算工具集。

所有计算在本地完成，不依赖外部 LLM API。
LLM 负责解读计算结果，工具负责精确运算。
"""

import logging
from typing import Any

from app.plugins.base import PluginBase, PluginTool
from app.plugins.industries.metaphysics.calculations import (
    bazi_paipan,
    dayun_liunian,
    lunar_convert,
    meihua_qigua,
    qimen_paipan,
    tarot_draw,
    xingzuo_xingpan,
    zeri_huangli,
    ziwei_paipan,
)

logger = logging.getLogger(__name__)


class MetaphysicsPlugin(PluginBase):
    """玄学计算工具插件。

    提供八字排盘、农历转换、大运流年、梅花易数、紫微斗数、
    奇门遁甲、星座星盘、择日黄历等精确计算能力。
    """

    name = "metaphysics"
    display_name = "玄学计算工具"
    description = (
        "精确的玄学计算工具集：八字排盘、农历转换、大运流年、"
        "梅花易数、紫微斗数、奇门遁甲、星座星盘、择日黄历、塔罗牌占卜"
    )
    version = "1.0.0"
    category = "metaphysics"

    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="bazi_paipan",
                description=(
                    "八字排盘：根据出生日期时间计算完整八字命盘，"
                    "包括四柱干支、十神、藏干、五行统计、日主强弱、神煞、喜用神"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "birth_date": {
                            "type": "string",
                            "description": "出生日期，格式 YYYY-MM-DD",
                        },
                        "birth_time": {
                            "type": "string",
                            "description": "出生时间，格式 HH:MM (24小时制)",
                        },
                        "gender": {
                            "type": "string",
                            "description": "性别: male/female 或 男/女",
                            "enum": ["male", "female", "男", "女"],
                        },
                        "birth_place": {
                            "type": "string",
                            "description": "出生地城市名(用于真太阳时修正)，如'北京'",
                            "default": "北京",
                        },
                    },
                    "required": ["birth_date", "birth_time", "gender"],
                },
            ),
            PluginTool(
                name="lunar_convert",
                description="农历公历互转，同时返回节气、干支、生肖等信息",
                parameters={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "日期，格式 YYYY-MM-DD",
                        },
                        "direction": {
                            "type": "string",
                            "description": "转换方向",
                            "enum": ["solar_to_lunar", "lunar_to_solar"],
                            "default": "solar_to_lunar",
                        },
                        "leap": {
                            "type": "boolean",
                            "description": "是否闰月(仅农历转公历时使用)",
                            "default": False,
                        },
                    },
                    "required": ["date"],
                },
            ),
            PluginTool(
                name="dayun_liunian",
                description="大运流年排盘：计算起运岁数、大运排列、近十年流年干支",
                parameters={
                    "type": "object",
                    "properties": {
                        "birth_date": {
                            "type": "string",
                            "description": "出生日期，格式 YYYY-MM-DD",
                        },
                        "birth_time": {
                            "type": "string",
                            "description": "出生时间，格式 HH:MM",
                        },
                        "gender": {
                            "type": "string",
                            "description": "性别",
                            "enum": ["male", "female", "男", "女"],
                        },
                        "birth_place": {
                            "type": "string",
                            "description": "出生地城市名",
                            "default": "北京",
                        },
                    },
                    "required": ["birth_date", "birth_time", "gender"],
                },
            ),
            PluginTool(
                name="meihua_qigua",
                description=(
                    "梅花易数起卦：支持数字起卦、时间起卦、文字起卦，"
                    "返回本卦/互卦/变卦/体用关系"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "数字起卦，传入3个数[上卦数, 下卦数, 动爻数]",
                        },
                        "method": {
                            "type": "string",
                            "description": "起卦方式，传'time'为时间起卦",
                            "enum": ["time"],
                        },
                        "text": {
                            "type": "string",
                            "description": "文字起卦，传入文字",
                        },
                    },
                },
            ),
            PluginTool(
                name="ziwei_paipan",
                description="紫微斗数排盘：计算命宫、身宫、十二宫、十四主星、四化飞星",
                parameters={
                    "type": "object",
                    "properties": {
                        "birth_date": {
                            "type": "string",
                            "description": "出生日期，格式 YYYY-MM-DD",
                        },
                        "birth_time": {
                            "type": "string",
                            "description": "出生时间，格式 HH:MM",
                        },
                        "gender": {
                            "type": "string",
                            "description": "性别",
                            "enum": ["male", "female", "男", "女"],
                        },
                    },
                    "required": ["birth_date", "birth_time", "gender"],
                },
            ),
            PluginTool(
                name="qimen_paipan",
                description="奇门遁甲排盘：排布九宫、三奇六仪、八门、九星、八神",
                parameters={
                    "type": "object",
                    "properties": {
                        "datetime": {
                            "type": "string",
                            "description": "排盘时间，格式 YYYY-MM-DD HH:MM",
                        },
                        "type": {
                            "type": "string",
                            "description": "排盘类型",
                            "default": "时家奇门",
                        },
                    },
                    "required": ["datetime"],
                },
            ),
            PluginTool(
                name="xingzuo_xingpan",
                description=(
                    "星座星盘：计算太阳/月亮/上升星座及七大行星位置，"
                    "以及主要相位(合相、六合、四分、三合、对冲)"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "birth_date": {
                            "type": "string",
                            "description": "出生日期，格式 YYYY-MM-DD",
                        },
                        "birth_time": {
                            "type": "string",
                            "description": "出生时间，格式 HH:MM",
                        },
                        "birth_place": {
                            "type": "string",
                            "description": "出生地城市名",
                            "default": "北京",
                        },
                    },
                    "required": ["birth_date", "birth_time"],
                },
            ),
            PluginTool(
                name="zeri_huangli",
                description=(
                    "择日黄历：查询指定日期的宜忌/吉方/冲煞等黄历信息，"
                    "或在日期范围内查找适合某活动的吉日"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "查询日期，格式 YYYY-MM-DD",
                        },
                        "activity": {
                            "type": "string",
                            "description": "择日活动，如'嫁娶'、'搬家'、'开业'",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "择日范围开始日期",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "择日范围结束日期",
                        },
                    },
                },
            ),
            PluginTool(
                name="tarot_draw",
                description=(
                    "塔罗牌占卜：支持单牌、三牌、爱情三角、二选一、"
                    "马蹄铁、六芒星、凯尔特十字、生命之树等8种牌阵"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "spread_type": {
                            "type": "string",
                            "description": "牌阵类型",
                            "enum": [
                                "single",
                                "three",
                                "love",
                                "choice",
                                "horseshoe",
                                "hexagram",
                                "celtic",
                                "life_tree",
                            ],
                            "default": "three",
                        },
                        "question": {
                            "type": "string",
                            "description": "用户的问题或想了解的事项",
                        },
                    },
                },
            ),
        ]

    def get_system_prompt_extension(self) -> str:
        return (
            "【玄学计算工具已启用】\n"
            "你现在具备精确的玄学计算能力，包括：\n"
            "1. 八字排盘(bazi_paipan) - 四柱干支、十神、藏干、五行、日主强弱、神煞、喜用神\n"
            "2. 农历转换(lunar_convert) - 公历农历互转、节气查询\n"
            "3. 大运流年(dayun_liunian) - 起运岁数、大运排列、流年干支\n"
            "4. 梅花易数(meihua_qigua) - 本卦/互卦/变卦、体用关系\n"
            "5. 紫微斗数(ziwei_paipan) - 命宫身宫、十四主星、四化飞星\n"
            "6. 奇门遁甲(qimen_paipan) - 九宫排布、三奇六仪、八门九星八神\n"
            "7. 星座星盘(xingzuo_xingpan) - 太阳/月亮/上升星座、行星位置、相位\n"
            "8. 择日黄历(zeri_huangli) - 宜忌查询、吉日推荐\n"
            "9. 塔罗牌占卜(tarot_draw) - 韦特78张全牌、8种牌阵、正逆位解读\n\n"
            "【行为铁律 — 违反将产生完全错误的结果】\n"
            "1. 收到出生信息后，第一个动作必须是调用工具，禁止先输出任何排盘文字。\n"
            "2. 禁止在调用工具之前猜测或计算四柱、大运等数据。你的计算错误率超过70%。\n"
            "3. 正确流程：用户给信息 → 立刻调工具 → 等结果返回 → 基于结果写报告。\n"
            "4. 报告中所有数字（四柱、岁数、年份、干支）只能引用工具返回的原始值。\n"
            "5. 合盘场景：先调完所有人的所有工具，拿齐数据后再统一写分析报告。\n"
            "6. 绝不要调一个工具就开始写半截分析，这会导致输出中断。"
        )

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        dispatch = {
            "bazi_paipan": self._exec_bazi,
            "lunar_convert": self._exec_lunar,
            "dayun_liunian": self._exec_dayun,
            "meihua_qigua": self._exec_meihua,
            "ziwei_paipan": self._exec_ziwei,
            "qimen_paipan": self._exec_qimen,
            "xingzuo_xingpan": self._exec_xingzuo,
            "zeri_huangli": self._exec_zeri,
            "tarot_draw": self._exec_tarot,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        try:
            result = await handler(arguments)
            return {"success": True, "data": result}
        except Exception as e:
            logger.exception("Metaphysics tool '%s' failed", tool_name)
            return {"success": False, "error": str(e)}

    async def _exec_bazi(self, args: dict[str, Any]) -> dict:
        return bazi_paipan(
            birth_date=args["birth_date"],
            birth_time=args["birth_time"],
            gender=args["gender"],
            birth_place=args.get("birth_place", "北京"),
        )

    async def _exec_lunar(self, args: dict[str, Any]) -> dict:
        return lunar_convert(
            date_str=args["date"],
            direction=args.get("direction", "solar_to_lunar"),
            leap=args.get("leap", False),
        )

    async def _exec_dayun(self, args: dict[str, Any]) -> dict:
        return dayun_liunian(
            birth_date=args["birth_date"],
            birth_time=args["birth_time"],
            gender=args["gender"],
            birth_place=args.get("birth_place", "北京"),
        )

    async def _exec_meihua(self, args: dict[str, Any]) -> dict:
        return meihua_qigua(
            numbers=args.get("numbers"),
            method=args.get("method"),
            text=args.get("text"),
        )

    async def _exec_ziwei(self, args: dict[str, Any]) -> dict:
        return ziwei_paipan(
            birth_date=args["birth_date"],
            birth_time=args["birth_time"],
            gender=args["gender"],
        )

    async def _exec_qimen(self, args: dict[str, Any]) -> dict:
        return qimen_paipan(
            datetime_str=args["datetime"],
            qimen_type=args.get("type", "时家奇门"),
        )

    async def _exec_xingzuo(self, args: dict[str, Any]) -> dict:
        return xingzuo_xingpan(
            birth_date=args["birth_date"],
            birth_time=args["birth_time"],
            birth_place=args.get("birth_place", "北京"),
        )

    async def _exec_zeri(self, args: dict[str, Any]) -> dict:
        return zeri_huangli(
            date_str=args.get("date"),
            activity=args.get("activity"),
            start_date=args.get("start_date"),
            end_date=args.get("end_date"),
        )

    async def _exec_tarot(self, args: dict[str, Any]) -> dict:
        return tarot_draw(
            spread_type=args.get("spread_type", "three"),
            question=args.get("question"),
        )
