# 参与翻译

## 工作流

```bash
python -m fo3zh census  "$FO3_DATA"                 # 先看工作量分布
python -m fo3zh extract "$FO3_DATA" -o workbench.tsv
# 用表格软件打开 workbench.tsv，在 zh 列填译文
python -m fo3zh patch   "$FO3_DATA" workbench.tsv -o build --encoding gbk
python -m fo3zh audit   build/Zeta.esm               # 查漏译
python -m fo3zh verify  build/Zeta.esm
```

提交时**只提交填了 `zh` 的行**（工具会自动跳过空行），不要把英文原文列一起 PR：

```bash
python - <<'PY'
# 生成只含定位键 + 译文的精简表（英文留在本地）
import csv
src, dst = "workbench.tsv", "data/translations/Fallout3.part01.tsv"
cols = ["formid", "nth", "rectype", "sub", "plugin", "field", "zh", "meta"]
with open(src, encoding="utf-8-sig", newline="") as fi, \
     open(dst, "w", encoding="utf-8-sig", newline="") as fo:
    r = csv.DictReader(fi, delimiter="\t"); w = csv.DictWriter(fo, cols, delimiter="\t")
    w.writeheader()
    for x in r:
        if (x.get("zh") or "").strip():
            w.writerow({k: x.get(k, "") for k in cols})
PY
```

按插件分文件放 `data/translations/`，一个文件不超过几千行，方便分批评审与合并。

## 定位键为什么必须有 `nth`

同一条 `INFO` 里可以有多条 `NAM1`（同一句台词的多个变体）。只按 FormID 定位会写错位置，
所以每条译文都要带 `nth`（记录内第 n 个同名子记录，从 0 起）。
工具在 `extract` 时已经算好，**不要手改这一列**。

## 术语表（先统一，再动笔）

同一英文在不同地方必须同一译法。新词请先加进 `data/glossary.csv`（`en,zh,备注`）：

| 英文 | 译法 | 备注 |
|---|---|---|
| Vault / Vault-Tec | 避难所 / 避难所科技 | 不要「金库」 |
| Pip-Boy | Pip-Boy | 保留原文 |
| V.A.T.S. | V.A.T.S. | 保留原文，别翻成「原子反应战斗系统」 |
| Cap / Caps | 瓶盖 | 货币 |
| Nuka-Cola | 核子可乐 | |
| Rad / Radiation | 辐 rad / 辐射 | 「Rad-X / RadAway」→「抗辐宁 / 辐射清除剂」按现有社区约定 |
| Super Mutant | 超级变种人 | |
| Feral Ghoul | 野鬼 | 「Ghoul」= 鬼 |
| Brotherhood of Steel | 钢铁兄弟会 | |
| Enclave | 英克雷 | |
| Liberty Prime | 自由至尊 | |
| Chinese / PLA | 中国 / 解放军 | 101 号避难所开场台词涉及，按上下文 |
| Wasteland | 废土 | |

## 风格约定

1. **口语优先**：对话是配音稿，念出来要像人话；宁可短一点，别书面腔。
2. **废土味**：50 年代美国复古 + 末世粗粝。老辐射中译的传统是稍微痞一点，别太现代网络语。
3. **保留控制符**：`%s`、`%.1f`、`%d`、`\n`、`<RGB:…>`、`<PIC:…>` 一律原样保留，数量与顺序不能变。
4. **长度**：菜单/按钮类（`MESG/ITXT`、`TERM/ITXT`）尽量短，超出会截断；正文不受限（单条上限 65,535 字节）。
5. **繁简**：本项目以简体（GBK）为准。若做繁体，另建 `--encoding big5` 的分支表，别混在一张表里。
6. **别译**：编辑器 ID（`AA1234`、`DLC05aa…`）、脚本、声音/模型路径、`INFO/NAM2` 脚本注释。

## 提交前自查

* `patch` 输出里「未命中」应为 0；不为 0 说明 FormID/nth 被改坏了，别硬提。
* `patch` 会打印「编码缺字警告」—— GBK 编不出的字要换字（多为生僻字/奇异标点）。
* 出现 `esm.Broken` 就是结构问题，直接报错给维护者，不要绕过校验。
* `verify` 每个产物都要跑一遍；`audit` 的残留英文条数应当随翻译推进而下降。
