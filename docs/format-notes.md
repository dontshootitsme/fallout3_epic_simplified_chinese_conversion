# 字节级格式实测笔记（辐射3 GOTY，Epic 版，exe 1.7.0.4）

全部结论都在 `Fallout 3 GOTY English`（Epic 版）上读出，不是转抄文档。

## 1. 安装目录与文本位置

```
D:\EPIC\fallout3\Fallout 3 GOTY English\
  Fallout3.exe                FileVersion 1.7.0.4   ← FOSE 不支持这个版本
  Fallout_default.ini         [Fonts] sFontFile_1..8、[Display] bInvalidateOlderFiles=0
  Data\
    Fallout3.esm   288,771,262     ← 本体
    Anchorage.esm   13,880,961     ThePitt.esm   8,728,496
    BrokenSteel.esm 11,015,915     PointLookout.esm 16,729,184
    Zeta.esm         4,950,331     ← 5 个 DLC，全部只到 .esm，没有 .esp
    *.bsa × 18                     Credits.txt  DLCList.txt  Music\  Shaders\  Video\
```

* **只有 6 个 ESM，没有任何 ESP/ESL**：DLC 内容直接写进各自的 ESM。
* `Data\` 下**没有散 `menus\` 或 `interface\`**（实测 `Test-Path` 为 False）。
* `launcher_settings.cfg` 里 `Languages=English, German, French, Italian, Spanish` —— 官方无中文。
* `My Games\Fallout3\Fallout.ini` 里 `sLanguage=ENGLISH`。

## 2. ESM 内部结构

```
记录：  签名(4)  数据长度 u32  标志 u32  FormID u32  编辑者容器码 u32  版本 u32   = 24 字节头
GRUP： 'GRUP'(4) 总长度 u32(含本头) 子记录数 u32 分组类型 u32 标签 u32 时间戳 u32 = 24 字节头
子记录：签名(4)  数据长度 u16  数据
```

* **子记录长度是 u16** → 单条字符串上限 65,535 字节（够长，但机翻长段要注意）。
* `GRUP` 的长度**包含自身 24 字节头**，记录的长度**不含**自身头 —— 两者不一样，写回时最容易搞错。
* 改一条文本 = 换子记录载荷 + 把差值累加到「记录头 size」和「**所有**父 GRUP size」。
  本工具的做法：把每条记录体当作等长区间替换，长度字段也做成等长区间，全部**按起点倒序**一次应用，
  避免前面的搬移让后面的绝对偏移失效。

## 3. zlib 压缩记录（**最容易漏的一类**）

`flags & 0x00040000` 置位 ⇒ 整条记录被压缩，记录体 = `解压后长度 u32 + zlib 流`。

| 插件 | 压缩记录数 | 其中 `NPC_` |
|---|---:|---:|
| Fallout3.esm | 41,903 | **1,411** |
| Anchorage | 1,849 | 74 |
| ThePitt | 525 | 14 |
| BrokenSteel | 1,107 | 73 |
| PointLookout | 795 | 60 |
| Zeta | 459 | 15 |

压缩记录里主要是 `LAND`（地形）和 **`NPC_`**。**`NPC_/FULL` 就是怪物的显示名**，实测 Zeta 里 25 个
（`Wastelander`、`Test Subject`、`Madeline Wallace`…）。不处理压缩记录，这些名字永远漏译，
而且用文本搜索根本搜不到。写回时要把解压体改完再重新压缩（本工具用 level 9）。

## 4. 哪些字段是玩家可见文本（实测 + xEdit fopdoc）

| 记录/子记录 | 含义 | 实测条数 |
|---|---|---:|
| `INFO/NAM1` | 对话正文（Response Text） | 37,556 |
| `INFO/RNAM` | 玩家选项（Prompt） | 2,841 |
| `DIAL/FULL` | 话题文字 | 8,496 |
| `NOTE/TNAM` + `FULL` | 笔记/书本正文 + 标题 | 1,023 + 793 |
| `TERM/ITXT,DESC,RNAM,FULL` | 终端菜单/正文/条目名/终端名 | 3,647 |
| `MESG/DESC,ITXT,FULL` | 弹出消息/按钮/消息名 | 1,235 |
| `GMST/DATA`（EDID 以 `s` 开头） | **界面 UI 文案** | 530 |
| `LSCR/DESC`、`PERK/DESC` | 读屏提示、Perk 描述 | 26 + 264 |
| 各类记录 `FULL` | 显示名（NPC/物品/地点/门/容器/派系/法术…） | ~12,000 |

**不译**：`EDID`（编辑器 ID）、`SCTX/SCPT`（脚本，实测 12,723 条 / 3,834,289 字符，比对话还长）、
`MODL/MOD2/ONAM`（模型与路径）、`SNAM`（声音路径）、`INFO/NAM2`（**Script Notes，注释**）、
`INFO/NAM3`（Edits）、`QUST/CNAM`（Comments）。

`GMST` 实测样本：`sDownloadsNotAvail = "View Downloadable Content"`、
`sMorphine = "Med-X"`、`sNoTalkUnConscious = "is unconscious."` —— 证明 UI 文案就在 ESM 里。

## 5. 字符串编码

行内、**单字节**、NUL 结尾、代码页 **cp1252**。没有长度前缀、没有 UTF-16、没有外置字符串表
（`Data\` 下无 `*.strings` / `*.dlstrings`）。德法意西版靠同一结构的 cp1252 高位区，
所以官方语言列表里只有这 5 种 + 英。

## 6. BSA（v104）

`magic "BSA\0"`、version **104**、flags 7。以 `Fallout - Misc.bsa`（1,793,843 字节）为例：
声明 10 个目录 / 127 个文件 / 名字块 2,203 字节。

* **文件名块是明文**（反斜杠、小写），不需要破哈希就能列全内容。枚举结果与头里的声明
  **逐个对上**：Textures 12,280/12,280、Sound 807/807、Voices 1,286/1,286、Misc 127/127。
* **文件载荷是逐文件 zlib 压缩**（`78 9c` 开头）。把 Misc.bsa 的 111 个流解出来共 2,785,512 字节，
  里面是 99 个 `menus\**\*.xml` + 几个 `.txt`/`.bat`（`falloutdict.txt`、`concat.bat`…）。
* **18 个 BSA 里 `.swf` 与 `.gfx` 命中数都是 0** —— 辐射3 不用 Flash，也不用 GFx。

## 7. 菜单 XML 里没有文字（重要）

解出的 `tutorial_menu.xml` 里长这样：

```xml
<text name="TM_title">
    <string> Title Text </string>   <!-- Replaced in code -->
</text>
```

`text="..."` 属性 **0 个**、`<text>…</text>` 文字节点 **0 个**。也就是说
**菜单 XML 只是布局，玩家看到的每个字都是引擎运行时注入的**（来自 GMST 与记录文本）。
→ 汉化 UI 不需要碰 BSA、不需要重打包、不需要动 XML。字库用散文件覆盖 + `bInvalidateOlderFiles=1` 即可。

## 8. 字体

`[Fonts]` 的 8 个槽位（`sFontFile_1..8`）指向 `Data\Textures\Fonts\*.fnt`，配套图集
`*_0_lod_a.tex/.dds`，**全部在 `Fallout - Textures.bsa` 里**（8 个 `.fnt` + 8 个 `.tex` + 10 个 `.dds`），
名字逐个对得上 ini。`iConsoleFont=2`、`iDebugTextFont=3` 说明控制台/调试文字走的是槽位号。
**没有任何 CJK 字库**。

## 9. 全量待译普查

| 插件 | 待译条数 |
|---|---:|
| Fallout3.esm | 49,104 |
| BrokenSteel | 4,018 |
| ThePitt | 3,428 |
| PointLookout | 3,387 |
| Anchorage | 2,209 |
| Zeta | 2,389 |
| **合计** | **64,535 条 / 3,790,075 个英文字符** |

对话（`INFO/NAM1`）2,629,527 字符占 69%。粗估成稿 **60–110 万汉字**。
