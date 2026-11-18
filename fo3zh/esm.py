"""FO3 ESM/ESP 结构层：分组与记录遍历、zlib 压缩记录、子记录迭代、外科手术式写回。

实测依据（辐射3 GOTY，Epic 版，exe 1.7.0.4）：
  * 文件 = TES4 头记录 + 若干 GRUP / 记录；无文件级索引。
  * 记录头 24 字节：签名(4) + 数据长度 u32 + 标志 u32 + FormID u32 + 编辑者容器码 u32 + 版本 u32
  * GRUP 头 24 字节：'GRUP'(4) + 总长度 u32(含本头) + 子记录数 u32 + 分组类型 u32 + 标签 u32 + 时间戳 u32
  * 子记录 = 签名(4) + 数据长度 u16 + 数据
  * 标志位 0x00040000 置位 ⇒ 该记录被整体 zlib 压缩：
    记录体 = 解压后长度 u32 + zlib 流。辐射3 用它在 LAND 和 **NPC_**（怪物/NPC 显示名）上。
  * 记录长度 = 记录头之后的字节数；GRUP 长度 = 含自身头的字节数。改文本必须把长度
    变化量累加到「记录头 size」和「所有父 GRUP size」。
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

COMP_FLAG = 0x00040000
HDR = 24
SUBHDR = 6
GRUP = "GRUP"


@dataclass
class Sub:
    """一条子记录。``off`` 是子记录头在记录体（压缩记录为解压后记录体）内的偏移。"""

    sig: str
    off: int
    length: int
    data: bytes
    nth: int = 0

    @property
    def text(self) -> str:
        return self.data.split(b"\x00", 1)[0].decode("cp1252", "replace")


@dataclass
class Record:
    sig: str
    off: int
    size: int
    flags: int
    formid: int
    grup_ats: tuple
    compressed: bool
    body: bytes

    @property
    def body_off(self) -> int:
        return self.off + HDR

    @property
    def formid_hex(self) -> str:
        return f"{self.formid:08x}"

    def subs(self):
        body = self.body
        n = {}
        o = 0
        end = len(body)
        while o + SUBHDR <= end:
            sig = bytes(body[o:o + 4]).decode("latin1", "?")
            ln = struct.unpack_from("<H", body, o + 4)[0]
            if o + SUBHDR + ln > end:
                return
            nth = n.get(sig, 0)
            n[sig] = nth + 1
            yield Sub(sig, o, ln, bytes(body[o + 6:o + 6 + ln]), nth)
            o += SUBHDR + ln


def iter_records(data, start=0, end=None, grup_ats=()):
    """深度遍历：逐个产出 Record。损坏/越界即停止该层遍历（不抛异常）。"""
    if end is None:
        end = len(data)
    off = start
    while off + HDR <= end:
        sig = bytes(data[off:off + 4]).decode("latin1", "?")
        size, flags, formid = struct.unpack_from("<III", data, off + 4)
        if sig == GRUP:
            if size < HDR or off + size > end + 1:
                return
            yield from iter_records(data, off + HDR, off + size, grup_ats + (off + 4,))
            off += size
            continue
        if size < 6 or off + HDR + size > end + 1:
            return
        comp = bool(flags & COMP_FLAG)
        body_off = off + HDR
        if comp:
            try:
                body = zlib.decompress(bytes(data[body_off + 4:body_off + size]))
            except zlib.error:
                body = b""
        else:
            body = bytes(data[body_off:body_off + size])
        yield Record(sig, off, size, flags, formid, tuple(grup_ats), comp, body)
        off += HDR + size


def cstring(b) -> str | None:
    """把子记录载荷当单字符串取；空/内嵌 NUL/非文本 → None。"""
    i = b.find(b"\x00")
    if i == 0:
        return None
    body = bytes(b if i < 0 else b[:i])
    if not body or b"\x00" in body:
        return None
    try:
        return body.decode("cp1252")
    except UnicodeDecodeError:
        return None


class Broken(Exception):
    """结构不自洽。"""


def verify(data, deep_zlib=True) -> None:
    """重走一遍：分组/记录长度必须自洽，压缩记录必须能解压。失败抛 Broken。"""
    def walk(s, e, depth):
        off = s
        while off + HDR <= e:
            sig = bytes(data[off:off + 4]).decode("latin1", "?")
            size, flags, _ = struct.unpack_from("<III", data, off + 4)
            if sig == GRUP:
                if size < HDR or off + size > e:
                    raise Broken(f"GRUP 长度异常 @{off} size={size}")
                walk(off + HDR, off + size, depth + 1)
                off += size
                continue
            if size < 6 or off + HDR + size > e:
                raise Broken(f"{sig} 越界 @{off} size={size} 剩余={e - off - HDR}")
            if deep_zlib and flags & COMP_FLAG:
                try:
                    zlib.decompress(bytes(data[off + 28:off + HDR + size]))
                except zlib.error as ex:
                    raise Broken(f"{sig} zlib 失败 @{off}: {ex}") from None
            off += HDR + size
        if e - off >= SUBHDR:
            raise Broken(f"分组尾部残留 {e - off} 字节 @{off}")

    walk(0, len(data), 0)


def apply_splices(data: bytes, splices) -> bytes:
    """splices: [(start, end, payload)]，按起点倒序应用，互不干扰。"""
    buf = bytearray(data)
    for s, e, payload in sorted(splices, key=lambda x: -x[0]):
        buf[s:e] = payload
    return bytes(buf)


def rewrite_records(data: bytes, plans) -> bytes:
    """按记录重写记录体并联动所有长度字段。

    plans: [(Record, [(Sub, new_bytes), ...]), ...]
    同一条记录内的多处修改会一次完成；长度变化量累加到记录头 size 与全部父 GRUP size。
    """
    splices = []
    size_add = {}
    for rec, edits in plans:
        if not edits:
            continue
        seg = bytearray(rec.body)
        for sub, new in sorted(edits, key=lambda x: -x[0].off):
            if len(new) > 0xFFFF:
                raise Broken(f"{rec.sig} {rec.formid_hex} 文本超过 65535 字节: {len(new)}")
            seg[sub.off:sub.off + SUBHDR + sub.length] = \
                sub.sig.encode("latin1") + struct.pack("<H", len(new)) + new
        payload = bytes(seg)
        if rec.compressed:
            payload = struct.pack("<I", len(seg)) + zlib.compress(payload, 9)
        splices.append((rec.body_off, rec.body_off + rec.size, payload))
        delta = len(payload) - rec.size
        if delta:
            for pos in (rec.off + 4,) + rec.grup_ats:
                size_add[pos] = size_add.get(pos, 0) + delta
    for pos, delta in size_add.items():
        cur = struct.unpack_from("<I", data, pos)[0]
        if not 0 <= cur + delta <= 0xFFFFFFFF:
            raise Broken(f"长度字段溢出 @{pos}: {cur}+{delta}")
        splices.append((pos, pos + 4, struct.pack("<I", cur + delta)))
    return apply_splices(data, splices)
