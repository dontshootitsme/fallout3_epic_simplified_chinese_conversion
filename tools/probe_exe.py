"""只读分析 Fallout3.exe：为「魔改出支持中文的版本」标靶。

不修改任何文件。产出四类线索：
  1) PE 段布局 + 导入表里与文本/字体/GDI 相关的 API
  2) 关键字符串（.fnt / FSH / Fonts / sFontFile / 文本渲染相关）及其虚拟地址
  3) MSVC RTTI 类名（.?AV…）里含 Font / Text / Menu / Char / Glyph 的类
  4) 对上述字符串做「立即数引用」扫描，在 .text 里找引用点（=候选函数入口）
"""
import re
import struct
import sys

EXE = sys.argv[1] if len(sys.argv) > 1 else r"D:\EPIC\fallout3\Fallout 3 GOTY English\Fallout3.exe"
data = open(EXE, "rb").read()
print(f"{EXE}\n{len(data):,} 字节")

# ---------- PE 头 ----------
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0"
nsec, = struct.unpack_from("<H", data, e_lfanew + 6)
opt_off = e_lfanew + 24
magic, = struct.unpack_from("<H", data, opt_off)
image_base, = struct.unpack_from("<Q" if magic == 0x20B else "<I", data, opt_off + (24 if magic == 0x20B else 28))
print(f"PE32{'+' if magic == 0x20B else ''}  ImageBase=0x{image_base:08X}  节数={nsec}")

secs = []
so = opt_off + struct.unpack_from("<H", data, e_lfanew + 20)[0]
for i in range(nsec):
    b = data[so + i * 40:so + (i + 1) * 40]
    name = b[:8].rstrip(b"\0").decode("latin1")
    vsz, vaddr, rawsz, praw = struct.unpack_from("<IIII", b, 8)
    chars, = struct.unpack_from("<I", b, 36)
    secs.append({"name": name, "va": image_base + vaddr, "vsz": vsz,
                 "raw": praw, "rawsz": rawsz, "chars": chars})
    print(f"  {name:8} VA=0x{image_base + vaddr:08X} vsize={vsz:9,} raw={praw:9,} "
          f"rawsize={rawsz:9,} {'EXEC' if chars & 0x20000000 else ''}")

text = next(s for s in secs if s["name"] == ".text")
text_bytes = data[text["raw"]:text["raw"] + text["rawsz"]]


def off_to_va(off):
    for s in secs:
        if s["raw"] <= off < s["raw"] + max(s["rawsz"], 1):
            return s["va"] + (off - s["raw"])
    return None


def va_to_off(va):
    for s in secs:
        if s["va"] <= va < s["va"] + max(s["rawsz"], 1):
            return s["raw"] + (va - s["va"])
    return None


# ---------- 导入表 ----------
dir_off = opt_off + (112 if magic == 0x20B else 96)
nimps, ioff = struct.unpack_from("<II", data, dir_off + 8 * 1)
imports = {}
p = ioff
while True:
    name_rva, _, _, fn_rva, orig_rva = struct.unpack_from("<IIIII", data, p)
    if not (name_rva or fn_rva or orig_rva):
        break
    dll_off = va_to_off(image_base + (name_rva or orig_rva))
    dll = data[dll_off:data.index(b"\0", dll_off)].decode("latin1") if dll_off else "?"
    thunk = fn_rva or orig_rva
    t = va_to_off(image_base + thunk)
    names = []
    if t is not None:
        k = t
        while True:
            hint = struct.unpack_from("<I", data, k)[0]
            if hint & 0x80000000:
                break
            noff = va_to_off(image_base + (hint & 0x7FFFFFFF))
            if noff is None:
                break
            names.append(data[noff + 2:data.index(b"\0", noff + 2)].decode("latin1"))
            k += 4
    imports[dll.lower()] = names
    p += 20
KEY = re.compile(r"(char|text|font|glyph|string|wide|multi|unicode|cp\d|strlen|wcst|lstrlen)", re.I)
print("\n== 与文本/字符相关的导入 API ==")
for dll, names in sorted(imports.items()):
    hits = [n for n in names if KEY.search(n)]
    if hits:
        print(f"  {dll}: {', '.join(sorted(set(hits))[:14])}")

# ---------- 关键字符串 ----------
STRINGS = [b".fnt", b"FSH2", b"FSH3", b"FSH", b"Fonts\\", b"sFontFile", b"Texture Set",
           b"GetText", b"text", b"RenderedText", b"Menu", b"char", b"BSFaceGen",
           b"Calibri", b"Monofonto", b"FixedSys", b"glow_", b"width", b"space"]
print("\n== 关键 ASCII 字符串（前若干处）==")
found = {}
for pat in STRINGS:
    hits = [m.start() for m in re.finditer(re.escape(pat), data)][:3]
    if hits:
        found[pat] = [off_to_va(h) for h in hits]
        print(f"  {pat.decode():14} {len([1 for m in re.finditer(re.escape(pat), data)]):5,} 处，"
              f"首个 VA={[hex(v) if v else '?' for v in found[pat][:1]]}")

# ---------- RTTI 类名 ----------
rtti = sorted(set(m.group(1).decode("latin1") for m in
                  re.finditer(rb"\.\?AV([A-Za-z_][\w@<>$]{2,60})@@", data)))
sel = [n for n in rtti if re.search(r"(Font|Glyph|Render|Menu|Text|Char|String|UI)", n, re.I)]
print(f"\n== RTTI 类名共 {len(rtti)} 个，与文字/UI 相关 {len(sel)} 个 ==")
for n in sel[:70]:
    print("   ", n)

# ---------- 字符串 → 代码引用（立即数） ----------
def xrefs(va, limit=12):
    pat = struct.pack("<I", va)
    out = []
    for m in re.finditer(re.escape(pat), text_bytes):
        vo = text["va"] + m.start()
        # 往前找函数序章，粗略给出函数起点
        st = text_bytes.rfind(b"\x55\x8b\xec", max(0, m.start() - 0x400), m.start())
        out.append((hex(vo), hex(text["va"] + st + 1) if st >= 0 else "?"))
        if len(out) >= limit:
            break
    return out

print("\n== 关键字符串在 .text 里的引用点（含粗略函数起点）==")
for pat in (b"FSH2", b"FSH3", b".fnt", b"sFontFile", b"Fonts\\"):
    for va in (found.get(pat) or [])[:2]:
        if not va:
            continue
        xr = xrefs(va)
        print(f"  {pat.decode():12} @0x{va:08X} → {len(xr)} 处引用")
        for site, fn in xr[:6]:
            print(f"      引用 {site}  函数≈{fn}")
