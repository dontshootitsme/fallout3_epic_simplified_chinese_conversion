"""fo3zh —— 把 Epic 版《辐射3 年度版》英文原版转换成简体中文的工具链。

子模块：
  esm        ESM/ESP 结构层（分组、记录、zlib 压缩记录、子记录、写回、自校验）
  textmap    「哪些子记录是玩家可见文本」的唯一一张表
  encoding   cp1252 ↔ GBK/Big5/cp932 转换与缺字检查
  workbench  译文工作台（TSV）读写
  pipeline   抽取 / 普查 / 写回 / 回读 / 漏译审计
  bsa        BSA 归档只读探查（内容清单、压缩载荷雕取）
  install    备份 + 安装 + 回滚
  cli        python -m fo3zh ...
"""
from . import bsa, encoding, esm, install, pipeline, textmap, workbench  # noqa: F401

__version__ = "0.1.0"
__all__ = ["bsa", "encoding", "esm", "install", "pipeline", "textmap", "workbench"]
