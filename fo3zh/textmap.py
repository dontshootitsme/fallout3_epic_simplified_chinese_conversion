"""哪些 (记录类型, 子记录) 是"要给玩家看的文本"——抽取与写回共用这一张表。

依据 xEdit 官方 fopdoc（Fallout3 记录定义）+ 辐射3 GOTY 本机实测：

  INFO/NAM1  对话正文        INFO/NAM2 = Script Notes（**不译**）  INFO/NAM3 = Edits（不译）
  INFO/RNAM  玩家选项 Prompt
  DIAL/FULL  话题文字（玩家看到并选择的那句）
  NOTE/TNAM  笔记/书本正文   NOTE/FULL 标题
  TERM/ITXT  终端菜单项      TERM/DESC 终端正文   TERM/RNAM 条目名   TERM/FULL 终端名
  MESG/DESC  弹出消息正文    MESG/ITXT 按钮文字   MESG/FULL 消息名
  LSCR/DESC  读屏提示        PERK/DESC Perk 描述   QUST/FULL 任务名
  GMST/DATA  界面 UI 字符串（仅 EDID 以 s 开头的；实测 sMorphine="Med-X"）
  <任意记录>/FULL  记录显示名（物品/NPC/地点/门/容器/派系/法术…）

明确不译：EDID/SCTB 编辑器 ID、SCTX/SCPT 脚本、MODL 模型路径、SNAM/WAV 声音路径。
"""
from __future__ import annotations

SPECIFIC = {
    ("INFO", "NAM1"): "对话正文",
    ("INFO", "RNAM"): "玩家选项",
    ("DIAL", "FULL"): "话题文字",
    ("NOTE", "TNAM"): "笔记正文",
    ("NOTE", "FULL"): "笔记标题",
    ("TERM", "ITXT"): "终端菜单项",
    ("TERM", "DESC"): "终端正文",
    ("TERM", "RNAM"): "终端条目名",
    ("TERM", "FULL"): "终端名",
    ("MESG", "DESC"): "消息正文",
    ("MESG", "ITXT"): "消息按钮",
    ("MESG", "FULL"): "消息名",
    ("LSCR", "DESC"): "读屏提示",
    ("PERK", "DESC"): "Perk 描述",
    ("QUST", "FULL"): "任务名",
    ("GMST", "DATA"): "界面字符串",
}

#: 这些记录的 FULL 已在 SPECIFIC 里单列，避免重复计数
FULL_OWN = {"QUST", "NOTE", "TERM", "MESG", "DIAL", "PERK", "LSCR"}

#: GMST 只有 EDID 以 s 开头的是字符串
GMST_PREFIX = "s"

#: 绝不翻译的编辑器 ID 前缀（辐射3 的内部编号，玩家看不到）
DROP_ENGLISH = (
    "AA", "B0", "B1", "B2", "B3", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
    "DLC01aa", "DLC02aa", "DLC03aa", "DLC04aa", "DLC05aa", "DLC05B0", "DLC05B1",
    "DLC04xBoxOnly", "xBoxOnly",
)


def classify(rectype: str, sub: str, edid: str = "") -> str | None:
    """返回字段含义；None = 这条不是要译的显示文本。"""
    key = (rectype, sub)
    if key in SPECIFIC:
        if rectype == "GMST" and not edid.startswith(GMST_PREFIX):
            return None
        return SPECIFIC[key]
    if sub == "FULL" and rectype not in FULL_OWN:
        return "显示名"
    return None


def looks_like_editor_id(edid: str) -> bool:
    """编辑器占位 ID（AA1234 / B0INT01 / DLC05aaTest…）——玩家看不到，不值得占译文表。"""
    if not edid:
        return False
    for p in DROP_ENGLISH:
        if edid.upper().startswith(p.upper()) and not edid[len(p):len(p) + 1].islower():
            return True
    return False
