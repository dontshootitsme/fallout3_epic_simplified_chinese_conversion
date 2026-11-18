"""不装游戏也能跑的闭环测试：合成一个微型 ESM → 抽取 → GBK 写回 → 结构校验 → 回读比对。

跑法： python tests/test_roundtrip.py     （也兼容 pytest）
"""
import os
import shutil
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fo3zh import esm, pipeline  # noqa: E402

GRUP = b"GRUP"
# 用仓库内的临时目录：沙箱环境可能不允许写系统 TEMP
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")


class tmpdir:
    """with tmpdir() as d: …  用完即删。

    注意：不要用 tempfile.mkdtemp —— 它在 Windows 上给目录加私有 DACL，
    会让沙箱内的后续写入被拒。
    """

    _n = 0

    def __enter__(self):
        os.makedirs(TMP, exist_ok=True)
        tmpdir._n += 1
        self.d = os.path.join(TMP, f"d{os.getpid()}_{tmpdir._n}")
        shutil.rmtree(self.d, ignore_errors=True)
        os.makedirs(self.d)
        return self.d

    def __exit__(self, *a):
        shutil.rmtree(self.d, ignore_errors=True)
        return False


def rec(sig, formid, body, flags=0, compress=False):
    if compress:
        body = struct.pack("<I", len(body)) + zlib.compress(body, 9)
        flags |= esm.COMP_FLAG
    return (sig.encode("latin1") + struct.pack("<III", len(body), flags, formid)
            + b"\x00" * 8 + body)


def sub(sig, payload):
    return sig.encode("latin1") + struct.pack("<H", len(payload)) + payload


def fourcc(s):
    b = s.encode("ascii")
    assert len(b) <= 4, s
    return int.from_bytes(b.ljust(4, b"\x00"), "little")


def grup(rtype, label, children):
    body = b"".join(children)
    return (GRUP + struct.pack("<IIII", 24 + len(body), len(children),
                               fourcc(rtype), label)
            + b"\x00" * 4 + body)


def cstr(s):
    return s.encode("cp1252") + b"\x00"


def build():
    """一个够用的最小插件：TES4 头 + TOP 分组 + 一条 INFO（两条 NAM1 + 一条 NAM2 注释）
    + 一条 zlib 压缩的 NPC_（显示名 Wastelander）。"""
    info = rec("INFO", 0x0000D1B2,
               sub("EDID", cstr("DIT01QuestGiverHello"))
               + sub("NAM0", b"\x00" * 4)
               + sub("NAM1", cstr("You shouldn't be out here, stranger."))
               + sub("NAM1", cstr("The radscorpions got two traders last week."))
               + sub("NAM2", cstr("SCRIPT NOTE: do not translate me")))
    npc = rec("NPC_", 0x0100B27D,
              sub("EDID", cstr("DLC05AlienMutant01"))
              + sub("FULL", cstr("Wastelander")), compress=True)
    tree = grup("TOP", 0, [grup("INFO", 0, [info]), grup("NPC_", 0, [npc])])
    head = rec("TES4", 0, sub("HEDR", struct.pack("<fII", 0.94, 64, 0))
               + sub("CNAM", cstr("Fallout3.esm")))
    return head + tree


def test_roundtrip():
    data = build()
    esm.verify(data)                                  # 合成文件自己必须先自洽
    recs = list(esm.iter_records(data))
    assert [r.sig for r in recs] == ["TES4", "INFO", "NPC_"], [r.sig for r in recs]
    info = next(r for r in recs if r.sig == "INFO")
    npc = next(r for r in recs if r.sig == "NPC_")
    assert npc.compressed, "压缩记录标志没认出来"

    # 同一个 INFO 里的两条 NAM1 必须按 nth=0/1 区分；NAM2 是脚本注释，不该进译文表
    nam1 = [s for s in info.subs() if s.sig == "NAM1"]
    assert [s.nth for s in nam1] == [0, 1], nam1

    with tmpdir() as td:
        src, dst = os.path.join(td, "t.esm"), os.path.join(td, "out.esm")
        open(src, "wb").write(data)
        texts = {(info.formid_hex, "INFO", "NAM1", 1): "上周辐射蝎拖走了两个商人。",
                 (npc.formid_hex, "NPC_", "FULL", 0): "废土客"}
        out, hit, missing = pipeline.patch_file(src, texts, "gbk", dst)
        assert hit == 2 and not missing, (hit, missing)
        esm.verify(out)                               # 写回后必须仍自洽

        got = pipeline.readback(dst, set(texts))
        for k, zh in texts.items():
            assert got[k] == zh.encode("gbk") + b"\x00", (k, got.get(k))

        keep = pipeline.readback(dst, {(info.formid_hex, "INFO", "NAM1", 0),
                                       (info.formid_hex, "INFO", "NAM2", 0)})
        assert keep[(info.formid_hex, "INFO", "NAM1", 0)] == \
            cstr("You shouldn't be out here, stranger."), "没给译文的条目被改动了"
        assert keep[(info.formid_hex, "INFO", "NAM2", 0)] == \
            cstr("SCRIPT NOTE: do not translate me"), "脚本注释被误改"

        npc2 = next(r for r in esm.iter_records(out) if r.sig == "NPC_")
        assert [s for s in npc2.subs() if s.sig == "FULL"][0].data == "废土客".encode("gbk") + b"\x00"
    print("test_roundtrip 通过")


def test_extract_skips_non_display_text():
    """NAM2 / EDID 不该出现在待译清单里。"""
    with tmpdir() as td:
        p = os.path.join(td, "t.esm")
        open(p, "wb").write(build())
        keys = {(r["formid"], r["rectype"], r["sub"], r["nth"]) for r in pipeline.extract(p)}
        assert ("0000d1b2", "INFO", "NAM2", 0) not in keys
        assert ("0000d1b2", "INFO", "EDID", 0) not in keys
        assert ("0000d1b2", "INFO", "NAM1", 1) in keys
        assert ("0100b27d", "NPC_", "FULL", 0) in keys
    print("test_extract_skips_non_display_text 通过")


def test_verify_detects_corruption():
    data = bytearray(build())
    i = data.find(GRUP)
    assert i >= 0
    data[i + 4:i + 8] = b"\xff\xff\xff\xff"           # 把第一条 GRUP 的长度改成 4GB
    try:
        esm.verify(bytes(data))
    except esm.Broken:
        print("test_verify_detects_corruption 通过")
        return
    raise AssertionError("被破坏的文件竟然通过了校验")


if __name__ == "__main__":
    test_roundtrip()
    test_extract_skips_non_display_text()
    test_verify_detects_corruption()
    print("全部通过")
