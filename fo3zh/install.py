"""安装与回滚：永不原地覆盖，先备份再替换，一条命令回滚。

安全规则
  1. 原插件文件永远先复制进 ``<Data>/_fo3zh_backup/<时间戳>/``；
  2. 只覆盖 ``build/`` 里存在对应产物的文件；
  3. ``install`` 会先对每个产物做 :func:`fo3zh.esm.verify`，不通过就拒绝安装；
  4. ``rollback`` 按 ``_fo3zh_backup/latest.txt`` 指回的目录整批还原。
"""
from __future__ import annotations

import os
import shutil
import time

from . import esm

BACKUP_ROOT = "_fo3zh_backup"
LATEST = "latest.txt"


def install(data_dir, build_dir, verbose=True):
    """把 build_dir/*.esm|esp 装进 data_dir，返回备份目录。"""
    jobs = [f for f in sorted(os.listdir(build_dir))
            if f.lower().endswith((".esm", ".esp"))]
    if not jobs:
        raise SystemExit(f"{build_dir} 里没有 .esm/.esp 产物")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(data_dir, BACKUP_ROOT, stamp)
    os.makedirs(bdir, exist_ok=True)
    for f in jobs:
        src = os.path.join(build_dir, f)
        dst = os.path.join(data_dir, f)
        if not os.path.exists(dst):
            raise SystemExit(f"目标目录里没有 {f}，检查 --data 是否指对")
        data = open(src, "rb").read()
        esm.verify(data)                      # 装之前必须结构自洽
        shutil.copy2(dst, os.path.join(bdir, f))
        open(dst, "wb").write(data)
        if verbose:
            print(f"  已替换 {f}（原件备份到 {os.path.join(BACKUP_ROOT, stamp, f)}）")
    open(os.path.join(data_dir, BACKUP_ROOT, LATEST), "w").write(stamp)
    return bdir


def rollback(data_dir, verbose=True):
    root = os.path.join(data_dir, BACKUP_ROOT)
    ref = os.path.join(root, LATEST)
    if not os.path.exists(ref):
        raise SystemExit(f"{root} 下没有备份记录，无需回滚")
    stamp = open(ref).read().strip()
    bdir = os.path.join(root, stamp)
    for f in sorted(os.listdir(bdir)):
        shutil.copy2(os.path.join(bdir, f), os.path.join(data_dir, f))
        if verbose:
            print(f"  已还原 {f}")
    os.remove(ref)
    return bdir


def status(data_dir):
    root = os.path.join(data_dir, BACKUP_ROOT)
    if not os.path.isdir(root):
        return "无备份记录（未安装过本工具链的产物）"
    out = []
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if os.path.isdir(p):
            out.append(f"{d}: {', '.join(sorted(os.listdir(p)))}")
    return "\n".join(out) or "备份目录为空"
