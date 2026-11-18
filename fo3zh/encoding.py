"""文本编解码：插件里是 cp1252 单字节；写回时按目标语言选代码页。

辐射3 是单字节文本引擎。汉化的通行做法（F3DC 内核）是让引擎按 **936/GBK** 读取，
所以写回简体中文用 GBK 字节；繁体用 Big5；日文 cp932。UTF-8 仅用于自查/校对产物，
游戏内不认（除非你用的运行时明确按 UTF-8 解析）。
"""
from __future__ import annotations

GAME_DECODER = "cp1252"

ALIASES = {
    "gbk": "gbk", "gb2312": "gbk", "gb18030": "gb18030", "936": "gbk",
    "big5": "big5", "950": "big5",
    "sjis": "cp932", "cp932": "cp932", "932": "cp932",
    "utf8": "utf-8", "utf-8": "utf-8",
    "latin1": "cp1252", "cp1252": "cp1252",
}


def resolve(name: str) -> str:
    key = (name or "gbk").lower().replace("_", "-")
    if key not in ALIASES:
        raise ValueError(f"不支持的编码 {name!r}，可选: {', '.join(sorted(set(ALIASES)))}")
    return ALIASES[key]


def encode(text: str, enc: str) -> bytes:
    return text.encode(resolve(enc), "replace")


def decode_game(data: bytes) -> str:
    return data.split(b"\x00", 1)[0].decode(GAME_DECODER, "replace")


def unmappable(text: str, enc: str) -> list[str]:
    """列出在目标编码里编不出的字符（生僻字、特殊标点），供译文校对。"""
    e = resolve(enc)
    bad = []
    for ch in text:
        try:
            ch.encode(e)
        except UnicodeEncodeError:
            bad.append(ch)
    return bad
