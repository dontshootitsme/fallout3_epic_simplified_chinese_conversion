"""BSA（Bethesda 归档）只读探查。

辐射3 GOTY（Epic 版）实测：magic ``BSA\\0``、version **104**、flags 7、
10 个目录、127 个文件、名字块 2203 字节；**文件名在名字块里是明文**（反斜杠分隔，
小写），所以不需要破解哈希就能列全目录内容——本项目据此核对过
「声明文件数 == 实际枚举数」（Textures 12280/12280、Sound 807/807、Voices 1286/1286）。

v104 的 ``name→data offset`` 映射没有实现（社区工具 BSAopt / gibbed.Bethesda 已能解）。
本模块提供：
  * :func:`header` / :func:`names`  —— 列内容（已验证）
  * :func:`carve_zlib` —— 按 zlib 流头把逐文件压缩的载荷雕出来（Misc.bsa 里的
    99 个 ``menus\\*.xml`` 就是这么解出来的，实测 111 个流 / 2,785,512 字节）

**结论**：辐射3 没有 .swf/.gfx，菜单文字全部由引擎注入（XML 里只有
``<string>Title Text</string> <!-- Replaced in code -->`` 占位），
所以汉化**不需要**动 BSA；字库用散文件 + ``bInvalidateOlderFiles=1`` 覆盖即可。
"""
from __future__ import annotations

import os
import re
import struct
import zlib

MAGIC = b"BSA\x00"


def header(path):
    with open(path, "rb") as f:
        blob = f.read(36)
    if blob[:4] != MAGIC:
        raise ValueError(f"{path} 不是 BSA（magic={blob[:4]!r}）")
    ver, f2, flags, folders, files, f6, namesz, f8 = struct.unpack("<8I", blob[4:36])
    return {"path": path, "version": ver, "flags": flags, "folders": folders,
            "files": files, "name_block_size": namesz, "size": os.path.getsize(path),
            "raw": (ver, f2, flags, folders, files, f6, namesz, f8)}


def names(path, max_scan=None):
    """枚举名字块里的明文名字（目录/文件，小写，反斜杠分隔）。"""
    h = header(path)
    with open(path, "rb") as f:
        blob = f.read(min(h["size"], max_scan or 1 << 20))
    out = [m.group()[:-1].decode("latin1")
           for m in re.finditer(rb"[\x20-\x7e]{3,120}\x00", blob)]
    return h, out


def carve_zlib(path, outdir=None, min_bytes=64, limit=None):
    """把归档里逐文件 zlib 压缩的载荷雕出来。

    返回 [(归档内偏移, 解压后字节数, bytes)]。不保证与文件名一一对应（v104 索引未解），
    用于**读**内容与做汉化可行性判断；要打回去请用散文件覆盖 + 归档失效。
    """
    data = open(path, "rb").read()
    found = []
    pos = 0
    while True:
        i = data.find(b"\x78\x9c", pos)
        if i < 0:
            break
        pos = i + 2
        try:
            d = zlib.decompressobj()
            out = d.decompress(data[i:])
            used = len(data[i:]) - len(d.unused_data)
        except zlib.error:
            continue
        if len(out) >= min_bytes:
            found.append((i, len(out), out))
            pos = max(pos, i + used)
            if limit and len(found) >= limit:
                break
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        for n, (i, size, out) in enumerate(found):
            with open(os.path.join(outdir, f"{n:04d}_@{i}.bin"), "wb") as f:
                f.write(out)
    return found
