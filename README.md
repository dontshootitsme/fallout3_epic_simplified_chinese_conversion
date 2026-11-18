# Fallout 3 Epic → 简体中文转换工具链

`fallout3_epic_simplified_chinese_conversion`

把 **Epic Games Store 版《辐射3 年度版》（Fallout 3 GOTY，英文原版）** 转换成简体中文的
完整工具链：文本抽取 → 译文工作台 → 字节级写回 → 结构自校验 → 漏译审计 → 安装/回滚。

Convert the Epic Games release of *Fallout 3: Game of the Year Edition* (English) into
Simplified Chinese: extract every player-visible string, translate in a spreadsheet-friendly
workbench, write it back byte-surgically into the masters, verify, audit, install, roll back.

> **当前决定（2026-11-18）**：显示层不走 FOSE/插件方案。等社区字节级反编译项目
> [f3decomp](https://f3decomp.com/)（Fallout 3 PC **1.7.0.3**，抓取时已 **99.1%** 完成）
> 放出重建源码后，从源码直接改出支持中文的引擎版本。
> 对接清单与已在真实 exe 上标好的靶点见 [docs/engine-cjk-plan.md](docs/engine-cjk-plan.md)。

> **重要 / IMPORTANT.** 游戏引擎是**单字节文本引擎**。只把汉字写进插件、不装双字节渲染运行时，
> 进游戏一定是乱码。文本层（本仓库）与显示层（注入代码 + 中文字库）缺一不可，
> 见 [`docs/runtime-cjk.md`](docs/runtime-cjk.md)。

---

## 30 秒上手

```bash
git clone https://github.com/dontshootitsme/fallout3_epic_simplified_chinese_conversion.git
cd fallout3_epic_simplified_chinese_conversion
export FO3_DATA="/mnt/d/EPIC/fallout3/Fallout 3 GOTY English/Data"     # 你的 Data 目录

python -m fo3zh census  "$FO3_DATA"          # 1) 待译普查：条数 / 字符数 / 分类
python -m fo3zh extract "$FO3_DATA" -o workbench.tsv                    # 2) 导出工作台
# 3) 在 workbench.tsv 的 zh 列里填译文（留空 = 跳过）
python -m fo3zh patch   "$FO3_DATA" workbench.tsv -o build --encoding gbk   # 4) 写回 + 自检
python -m fo3zh audit   build/Zeta.esm       # 5) 查漏译（仍是英文的显示文本）
python -m fo3zh install "$FO3_DATA" --build build    # 6) 备份后安装（--rollback 可还原）
```

只处理某些插件加 `--only Fallout3 Zeta`。全程只读原文件，产物一律写到 `build/`。

## 命令一览

| 命令 | 作用 |
|---|---|
| `census <Data>` | 待译文本普查（实测：64,535 条 / 3,790,075 个英文字符） |
| `extract <Data> -o workbench.tsv` | 导出译文工作台（UTF-8 BOM，Excel 可直接打开） |
| `patch <Data> <表> -o build` | 按 `(formid, rectype, sub, nth)` 定位写回，联动修正所有长度字段，写盘前自动结构校验 |
| `verify <插件>` | 只读结构自洽校验（GRUP/记录长度、zlib 记录可解压） |
| `audit <插件>` | 列出"仍是英文"的显示文本，用于查漏译 |
| `bsa <归档> [--carve 目录]` | 列 BSA 内容清单 / 雕出逐文件 zlib 载荷（已验证：文件名块是明文） |
| `ini <Fallout.ini>` | 生成 8 个中文字体槽位 + `bInvalidateOlderFiles=1` 的配置 |
| `install / --rollback / --status` | 备份→替换→回滚，永不原地覆盖 |

## 为什么这套工具长这样（关键实测结论）

详见 [`docs/format-notes.md`](docs/format-notes.md)。三条最要紧的：

1. **辐射3 的文本全在 6 个 ESM 主插件里**，行内、单字节、cp1252、NUL 结尾。
   没有 `.strings`／`.dlstrings` 外置表，没有 `.swf`/`.gfx`（18 个 BSA 全扫命中 0），
   菜单 XML 里**一个玩家可见文字都没有**（只有 `<!-- Replaced in code -->` 占位）
   → 所以汉化 UI 不需要动任何 UI 文件，UI 文案就在 `GMST/DATA`。
2. **约 4,200 条记录整体 zlib 压缩**（`flags & 0x00040000`），**2,282 个 NPC 显示名藏在压缩记录里**。
   普通文本工具/正则替换会整批漏掉它们。
3. **同一个 INFO 里可以有多条 `NAM1`**（同一句台词的多个变体）。
   定位必须带"记录内第 n 个同名子记录"这个下标，否则写错位置。

## 仓库结构

```
fo3zh/
  esm.py        ESM/ESP 结构层：分组/记录/压缩记录/子记录 + 写回 + 自校验
  textmap.py    “哪些 (记录类型, 子记录) 是玩家可见文本”的唯一一张表
  encoding.py   cp1252 ↔ GBK/Big5/cp932；缺字检查
  workbench.py  译文工作台读写（TSV/CSV 自动识别，Excel 友好）
  pipeline.py   抽取 / 普查 / 写回 / 回读 / 漏译审计
  bsa.py        BSA 只读探查（内容清单、压缩载荷雕取）
  install.py    备份 + 安装 + 回滚
  cli.py        python -m fo3zh ...
data/translations/
  Zeta.demo.csv 32 条演示译文（已验证可写回，含压缩记录里的 NPC 名）
docs/
  format-notes.md   字节级格式实测笔记
  runtime-cjk.md    汉字显示层：为什么必须有注入代码 + 三条路线
  legal.md          版权与分发须知
tests/
  test_roundtrip.py 用合成 ESM 跑「抽取→写回→校验→回读」闭环，不需要装游戏
```

## 状态

- [x] 结构解析：6 个主插件 100% 走通，0 解析错误（含压缩记录）
- [x] 文本抽取：64,535 条 / 3,790,075 字符，分类统计完成
- [x] 写回 + 结构自校验 + 回读一致（演示 32/32）
- [x] 漏译审计、安装/回滚、BSA 探查
- [ ] 全量译文（60–110 万汉字）：按 `data/translations/` 分批推进
      （第 1 批 UI/短字符串层已抽出 19,928 条：`tools/batch1_ui.py`）
- [ ] 字库生成（把 TTF 烘成 `.fnt` + 图集）与引擎侧字库格式对接
- [ ] **R0**：等 f3decomp 源码 → 从源码改出中文引擎（对接清单 `docs/engine-cjk-plan.md`）

## 许可

代码 MIT（见 `LICENSE`）。**游戏文本版权属于 Bethesda**：本仓库不分发任何从游戏里导出的
英文原文，也不含游戏资产；`data/translations/` 里只有本项目作者产出的中文译文与定位键。
自己发布译文包前请读 [`docs/legal.md`](docs/legal.md)。
