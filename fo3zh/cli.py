"""fo3zh 命令行。

  python -m fo3zh census   <Data目录>              待译普查（条数/字符数/分类）
  python -m fo3zh extract  <Data目录> -o work.tsv   导出译文工作台
  python -m fo3zh patch    <Data目录> work.tsv -o build/   按工作台写回 + 自检
  python -m fo3zh verify   <插件文件>                结构自洽校验
  python -m fo3zh audit    <插件文件>                列出仍是英文的显示文本（查漏译）
  python -m fo3zh bsa      <bsa文件> [--carve dir]   列 BSA 内容 / 雕出压缩载荷
  python -m fo3zh ini      <Fallout.ini> --fonts-dir Textures\\Fonts   生成中文字体槽位配置
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from . import bsa as bsa_mod
from . import encoding, esm, install, pipeline


def _masters(data_dir, only=None):
    ext = (".esm", ".esp")
    out = []
    for f in sorted(os.listdir(data_dir)):
        if f.lower().endswith(ext):
            if only and not any(f.lower().startswith(o.lower()) for o in only):
                continue
            out.append(os.path.join(data_dir, f))
    return out


def cmd_census(a):
    tot = ch = 0
    per = {}
    for p in _masters(a.data, a.only):
        rows, by = pipeline.census(p)
        tot += len(rows)
        c = sum(len(r["en_us"]) for r in rows)
        ch += c
        print(f"  {os.path.basename(p):24} {len(rows):7,} 条  {c:10,} 字符")
        for k, v in by.items():
            x = per.get(k, (0, 0))
            per[k] = (x[0] + v[0], x[1] + v[1])
    print(f"\n合计 {tot:,} 条待译文本 / {ch:,} 个英文字符")
    print("\n分类:")
    for (rt, sb, fld), (n, c) in sorted(per.items(), key=lambda kv: -kv[1][0])[:30]:
        print(f"  {rt:6}{sb:6} {fld:10} {n:7,} 条 {c:10,} 字符")
    return 0


def cmd_extract(a):
    write, close = None, None
    from .workbench import writer
    write, close = writer(a.out)
    n = 0
    for p in _masters(a.data, a.only):
        rows = list(pipeline.extract(p))
        for r in rows:
            write(r)
        n += len(rows)
        print(f"  {os.path.basename(p):24} {len(rows):7,} → {a.out}")
    close()
    print(f"\n工作台已写出 {a.out}（{n:,} 行）；填 zh 列后运行 patch 子命令")
    return 0


def cmd_patch(a):
    from .workbench import Workbench
    wb = Workbench(a.table)
    os.makedirs(a.out, exist_ok=True)
    print(f"译文表 {a.table}: {len(wb)} 条已填 zh，编码 {a.encoding}")
    grand_hit = 0
    for p in _masters(a.data, a.only):
        texts = wb.for_plugin(p)
        if not texts:
            continue
        rep = []
        dst = os.path.join(a.out, os.path.basename(p))
        out, hit, missing = pipeline.patch_file(p, texts, a.encoding, dst, rep)
        enc = encoding.resolve(a.encoding)
        got = pipeline.readback(dst, set(texts))
        ok = sum(1 for k, v in got.items()
                 if v == texts[k].encode(enc, "replace") + b"\x00")
        size0 = os.path.getsize(p)
        print(f"  {os.path.basename(p):24} 命中 {hit}/{len(texts)}（未命中 {len(missing)}）"
              f" 回读一致 {ok}  {size0:,} → {len(out):,} 字节  → {dst}")
        if rep:
            print(f"    编码缺字警告 {len(rep)} 处，例如 {rep[0]}")
        grand_hit += hit
    print(f"\n共写回 {grand_hit} 处；每个产物都通过了结构自洽校验（esm.verify）")
    return 0


def cmd_verify(a):
    data = open(a.plugin, "rb").read()
    try:
        esm.verify(data)
    except esm.Broken as ex:
        print(f"结构不自洽: {ex}")
        return 1
    n = sum(1 for _ in esm.iter_records(data))
    print(f"{os.path.basename(a.plugin)}: 结构自洽，{n:,} 条记录，{len(data):,} 字节")
    return 0


def cmd_audit(a):
    rows = pipeline.audit_residual(a.plugin, a.min_len)
    for fid, rt, sb, s in rows[: a.limit]:
        print(f"  {fid} {rt}/{sb}: {s[:88]}")
    print(f"\n{os.path.basename(a.plugin)}: 仍是英文的显示文本 {len(rows):,} 条")
    return 0


def cmd_bsa(a):
    h, ns = bsa_mod.names(a.archive)
    print(f"{os.path.basename(a.archive)}: v{h['version']} flags={h['flags']} "
          f"目录{h['folders']} 文件{h['files']} 名字块{h['name_block_size']} 共 {h['size']:,} 字节")
    files = [n for n in ns if "\\" in n or "." in n]
    for n in files[: a.limit]:
        print("   ", n)
    exts = {}
    for n in files:
        e = os.path.splitext(n)[1].lower()
        exts[e] = exts.get(e, 0) + 1
    print("扩展名统计:", dict(sorted(exts.items(), key=lambda kv: -kv[1])[:12]))
    if a.carve:
        found = bsa_mod.carve_zlib(a.archive, a.carve)
        print(f"雕出 zlib 流 {len(found)} 个 → {a.carve}")
    return 0


def cmd_ini(a):
    """把 8 个 sFontFile_* 指向中文字库，并打开归档失效。"""
    txt = open(a.ini, encoding="utf-8-sig", errors="replace").read()
    fonts = a.fonts or ["GB_Glow_Monofonto_Large.fnt", "GB_Glow_Monofonto_Medium.fnt",
                        "GB_Fixedsys_Comp_Uniform_Width.fnt", "GB_Glow_Futura_Caps_Large.fnt",
                        "GB_Glow_Monofonto_VeryLarge.fnt", "GB_Glow_Monofonto_VeryLarge02_Dialogs2.fnt",
                        "GB_Glow_Monofonto_Medium_Dialogs.fnt", "GB_Glow_Monofonto_Large_Dialogs.fnt"]
    i = -1

    def repl(m):
        nonlocal i
        f = fonts[i % len(fonts)]
        i += 1
        return f'sFontFile_{i}={m.group(1)}{f}'

    new = re.sub(r"sFontFile_\d+=(\s*)", lambda m: repl(m), txt)
    new = re.sub(r"^bInvalidateOlderFiles=.*$", "bInvalidateOlderFiles=1", new, flags=re.M)
    new = re.sub(r"^sLanguage=.*$", "sLanguage=ENGLISH", new, flags=re.M)
    out = a.write or (a.ini + ".zh")
    open(out, "w", encoding="utf-8-sig", newline="\r\n").write(new)
    print(f"已写出 {out}")
    for line in new.splitlines():
        if line.startswith(("sFontFile_", "bInvalidateOlderFiles", "sLanguage", "iConsoleFont")):
            print("   ", line)
    return 0


def cmd_install(a):
    if a.rollback:
        d = install.rollback(a.data)
        print(f"已从 {d} 还原全部插件")
        return 0
    if a.status:
        print(install.status(a.data))
        return 0
    bdir = install.install(a.data, a.build)
    print(f"\n安装完成，备份目录：{bdir}")
    print("进游戏前请确认已装双字节渲染运行时（见 docs/RUNTIME.md），否则汉字一定乱码。")
    return 0


def build(argv=None):
    ap = argparse.ArgumentParser(prog="fo3zh", description="辐射3 Epic 版 → 简体中文 转换工具链")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p, data=True):
        if data:
            p.add_argument("data", help="游戏 Data 目录")
            p.add_argument("--only", nargs="*", help="只处理这些前缀的插件，如 Fallout3 Zeta")

    p = sp.add_parser("census"); common(p); p.set_defaults(fn=cmd_census)
    p = sp.add_parser("extract"); common(p)
    p.add_argument("-o", "--out", default="workbench.tsv"); p.set_defaults(fn=cmd_extract)
    p = sp.add_parser("patch"); common(p)
    p.add_argument("table"); p.add_argument("-o", "--out", default="build")
    p.add_argument("--encoding", default="gbk"); p.set_defaults(fn=cmd_patch)
    p = sp.add_parser("verify")
    p.add_argument("plugin"); p.set_defaults(fn=cmd_verify)
    p = sp.add_parser("audit")
    p.add_argument("plugin"); p.add_argument("--min-len", type=int, default=4)
    p.add_argument("--limit", type=int, default=60); p.set_defaults(fn=cmd_audit)
    p = sp.add_parser("bsa")
    p.add_argument("archive"); p.add_argument("--carve")
    p.add_argument("--limit", type=int, default=25); p.set_defaults(fn=cmd_bsa)
    p = sp.add_parser("ini")
    p.add_argument("ini"); p.add_argument("--fonts", nargs="*")
    p.add_argument("--write"); p.set_defaults(fn=cmd_ini)
    p = sp.add_parser("install")
    p.add_argument("data", help="游戏 Data 目录")
    p.add_argument("--build", default="build", help="产物目录（默认 ./build）")
    p.add_argument("--rollback", action="store_true", help="还原到上次安装前的原件")
    p.add_argument("--status", action="store_true", help="只看备份清单，不做任何修改")
    p.set_defaults(fn=cmd_install)
    return ap.parse_args(argv)


def main(argv=None):
    a = build(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
