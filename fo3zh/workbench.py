"""译文工作台：TSV（推荐，可直接用支持 TSV 的编辑器/表格软件打开）。

表头（列序固定，写回时只认 formid/nth/rectype/sub/zh）：

  plugin   插件文件名
  formid   记录 FormID（8 位十六进制，插件内唯一）
  nth      同一条记录里第 n 个同名子记录（从 0 起）。**必须有**：一个 INFO 里会有多条
           NAM1（同一句台词的多个变体），少了这个下标就会写错位置。
  rectype  记录类型  sub 子记录类型  field 字段含义（中文，便于筛选）
  edid     EDID 编辑器 ID（仅供检索，不翻译）
  offset   字符串在原文件里的字节偏移；**负数表示该记录是 zlib 压缩记录**（|offset| 是
           解压体里的偏移）。写回不依赖它，只作调试用。
  len      原文载荷字节数
  en_us    原文（换行以 \\n 字面量保存）
  zh       ← 你要填的译文；留空 = 跳过
  meta     备注，可空
"""
from __future__ import annotations

import csv
import os

COLUMNS = ["plugin", "formid", "nth", "rectype", "sub", "field", "edid",
           "offset", "len", "en_us", "zh", "meta"]
KEY_FIELDS = ("formid", "rectype", "sub", "nth")


def _esc(t: str) -> str:
    return t.replace("\t", " ").replace("\r", " ").replace("\n", "\\n")


def _unesc(t: str) -> str:
    return t.replace("\\n", "\n").replace("\\r", "")


def _sniff(path):
    """自动识别分隔符：表头里有 Tab 就按 TSV，否则按 CSV（Excel 存出来就是逗号）。"""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        head = fh.readline()
    return "\t" if "\t" in head else ","


def writer(path, delimiter=None):
    """返回 (write(row)) 可调用对象与 close()。

    ``.csv`` 结尾用逗号，其它用 Tab；带 utf-8-sig BOM，Excel 直接双击能开。
    """
    delimiter = delimiter or ("," if path.lower().endswith(".csv") else "\t")
    fh = open(path, "w", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter=delimiter,
                       quoting=csv.QUOTE_MINIMAL, extrasaction="ignore")
    w.writeheader()

    def write(row: dict):
        out = dict(row)
        out["en_us"] = _esc(out.get("en_us", "") or "")
        out["zh"] = _esc(out.get("zh", "") or "")
        w.writerow({k: out.get(k, "") for k in COLUMNS})

    def close():
        fh.close()

    return write, close


class Workbench:
    """读译文表 → {(formid, rectype, sub, nth): 译文}。"""

    def __init__(self, path, encoding_hint: str = "gbk"):
        self.path = path
        self.encoding_hint = encoding_hint
        self.rows = []
        delim = _sniff(path)
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=delim):
                zh = (r.get("zh") or "").strip()
                if not zh:
                    continue
                try:
                    nth = int(r.get("nth") or 0)
                except ValueError:
                    nth = 0
                self.rows.append({
                    "key": (r["formid"].strip().lower(), r["rectype"].strip(),
                            r["sub"].strip(), nth),
                    "zh": _unesc(zh),
                    "plugin": (r.get("plugin") or "").strip(),
                    "meta": r.get("meta") or "",
                })

    def for_plugin(self, filename: str):
        """返回 {key: zh}，只含 plugin 列为空或等于该文件的行。"""
        base = os.path.basename(filename).lower()
        return {r["key"]: r["zh"] for r in self.rows
                if not r["plugin"] or r["plugin"].lower() == base}

    def __len__(self):
        return len(self.rows)
