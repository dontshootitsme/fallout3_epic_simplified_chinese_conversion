"""抽取 + 写回 + 审计。三步共用同一套定位键，永不改原文件（写回只写到你指定的目标）。"""
from __future__ import annotations

import os

from . import esm, textmap
from .encoding import decode_game, encode, unmappable


def extract(path, plugin=None):
    """产出一行一条待译文本的 dict（供 workbench.writer 写盘）。"""
    plugin = plugin or os.path.basename(path)
    data = open(path, "rb").read()
    for rec in esm.iter_records(data):
        edid = ""
        for sub in rec.subs():
            if sub.sig == "EDID":
                edid = decode_game(sub.data)
                break
        if rec.sig == "GMST" and not edid.startswith(textmap.GMST_PREFIX):
            continue
        if textmap.looks_like_editor_id(edid) and rec.sig not in ("GMST",):
            # 编辑器占位 ID（AA1234…）玩家看不到，但仍可加 --keep-editorid 保留
            pass
        for sub in rec.subs():
            field = textmap.classify(rec.sig, sub.sig, edid)
            if not field:
                continue
            s = esm.cstring(sub.data)
            if not s or not s.strip():
                continue
            yield {
                "plugin": plugin,
                "formid": rec.formid_hex,
                "nth": sub.nth,
                "rectype": rec.sig,
                "sub": sub.sig,
                "field": field,
                "edid": edid,
                "offset": -(sub.off + esm.SUBHDR) if rec.compressed else rec.body_off + sub.off + esm.SUBHDR,
                "len": sub.length,
                "en_us": s,
                "zh": "",
                "meta": "",
            }


def census(path, plugin=None):
    """统计不写盘：条数、字符数、按 (rectype, sub) 分布。"""
    rows = list(extract(path, plugin))
    by = {}
    for r in rows:
        k = (r["rectype"], r["sub"], r["field"])
        a = by.get(k, (0, 0))
        by[k] = (a[0] + 1, a[1] + len(r["en_us"]))
    return rows, by


def patch_file(src, texts, enc="gbk", dst=None, report=None):
    """把 texts={key: 译文} 写回 src，返回 (bytes, 命中数, 未命中键集合)。

    定位键 = (formid, rectype, sub, nth)。命中后用 esm.rewrite_records 一次完成
    记录体重写 + 记录头 size + 全部父 GRUP size 的联动，最后 esm.verify 自检。
    """
    data = open(src, "rb").read()
    want = dict(texts)
    plans, hit = [], set()
    for rec in esm.iter_records(data):
        edits = []
        for sub in rec.subs():
            k = (rec.formid_hex, rec.sig, sub.sig, sub.nth)
            zh = want.get(k)
            if zh is None or sub.sig == "GRUP":
                continue
            new = encode(zh, enc) + b"\x00"
            if new == sub.data:
                hit.add(k)
                continue
            edits.append((sub, new))
            hit.add(k)
            if report is not None:
                bad = unmappable(zh, enc)
                if bad:
                    report.append(f"{rec.formid_hex} {rec.sig}/{sub.sig} 编码缺字: {''.join(sorted(set(bad)))}")
        if edits:
            plans.append((rec, edits))
    out = esm.rewrite_records(data, plans)
    esm.verify(out)
    if dst:
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        open(dst, "wb").write(out)
    return out, len(hit), set(want) - hit


def readback(path, keys):
    """从（已打补丁的）文件里把译文按原语言再解回来 → {key: 原文}。"""
    data = open(path, "rb").read()
    got = {}
    for rec in esm.iter_records(data):
        for sub in rec.subs():
            k = (rec.formid_hex, rec.sig, sub.sig, sub.nth)
            if k in keys:
                got[k] = sub.data
    return got


def audit_residual(path, min_len=4):
    """扫描"仍然像英文的显示文本"，用于查漏译。返回 [(formid, rectype, sub, text)]。"""
    import re
    wordy = re.compile(r"[A-Za-z]{3,}")
    out = []
    data = open(path, "rb").read()
    for rec in esm.iter_records(data):
        edid = ""
        for sub in rec.subs():
            if sub.sig == "EDID":
                edid = decode_game(sub.data)
                break
        for sub in rec.subs():
            if not textmap.classify(rec.sig, sub.sig, edid):
                continue
            s = esm.cstring(sub.data)
            if not s or len(s) < min_len:
                continue
            try:
                s.encode("ascii")
            except UnicodeEncodeError:
                continue          # 已有非 ASCII 字节 = 已译
            if wordy.search(s):
                out.append((rec.formid_hex, rec.sig, sub.sig, s))
    return out
