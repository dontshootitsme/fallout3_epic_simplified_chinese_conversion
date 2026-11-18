"""第 1 批：把「UI 与短字符串层」从 6 个主插件里抽出来单独成表。

范围：GMST/DATA（界面文案）、MESG（弹窗正文+按钮）、LSCR/DESC（读屏提示）、
PERK/DESC（技能描述）、QUST/FULL（任务名）、各类记录的 FULL（显示名）。
这批共约 1.6 万条，是"进游戏满眼都是"的部分，先译它性价比最高。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fo3zh import pipeline                              # noqa: E402
from fo3zh.workbench import COLUMNS, writer             # noqa: E402

DATA = r"D:\EPIC\fallout3\Fallout 3 GOTY English\Data"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "workbench-ui.tsv")

WANT_SUB = {"DATA", "DESC", "ITXT", "FULL", "TNAM"}
WANT_REC = {"GMST", "MESG", "LSCR", "PERK", "QUST"}


def keep(r):
    return r["rectype"] in WANT_REC or r["sub"] == "FULL"


def main():
    write, close = writer(OUT)
    n = 0
    for f in sorted(os.listdir(DATA)):
        if not f.lower().endswith(".esm"):
            continue
        p = os.path.join(DATA, f)
        rows = [r for r in pipeline.extract(p) if keep(r)]
        rows.sort(key=lambda r: (r["field"], r["rectype"], r["formid"], r["nth"]))
        for r in rows:
            write(r)
        n += len(rows)
        print(f"  {f:22} {len(rows):6,}", flush=True)
    close()
    print(f"\n→ {OUT}  共 {n:,} 条")


if __name__ == "__main__":
    main()
