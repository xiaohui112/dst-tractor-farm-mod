#!/usr/bin/env python3
"""
Tractor —— 占位动画包生成器

【重要】图标与封面已改用正式美术（见 tools/build_tex.py），本脚本不再生成它们。
本脚本现在只负责一件事：生成**占位 anim.zip**，让 Mod 在没有 ktech/ModTools
的情况下也能加载不报错。正式动画编译好之后，直接用正式文件覆盖 anim/ 即可。

原说明（历史）：
Tractor —— 占位美术资源生成器

DST 的 tex/zip 需要专用工具（ktech/TEXTool），本脚本生成的是**可被游戏识别的最小合法包**：
- images/*.xml + *.tex：TEXTool 2.5 图集格式（PNG 压缩块 + 逐图映射）
- anim/*.zip：把 BANK 名下的动画帧打成 DST 动画包格式（build + anim)

用途：提供占位素材让 Mod 能被加载、能在游戏里看到东西，
正式美术到位后直接替换同名文件即可。

用法：
    python3 tools/make_assets.py
"""

import io
import os
import struct
import zipfile
import zlib

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mod", "AgeOfMachines")
IMG = os.path.join(MOD, "images")
ANIM = os.path.join(MOD, "anim")

os.makedirs(IMG, exist_ok=True)
os.makedirs(ANIM, exist_ok=True)


# ---------------------------------------------------------------------------
# TEXTool 2.5 图集写入
# ---------------------------------------------------------------------------

def write_ktx_texatlas(path, atlas, image_size=(0, 0)):
    """写一个 TEXTool 2.5 格式的 .tex（内含 PNG 压缩块）。"""
    # 头部：4 字节 magic + 版本 + 图集尺寸与元素信息
    magic = b"\x01\x00\x00\x00"
    buf = io.BytesIO()
    # 简化实现：用 PNG 作为单块存储，附上 XML 级别的元数据
    png_path = path + ".png"
    # 这里由调用方提供 PNG，我们只把元数据写在 xml 里
    buf.write(magic)
    return buf.getvalue()


def make_atlas_xml(name, elements):
    """
    elements: [(elem_name, x, y, w, h), ...]
    DST 认的 .xml 结构（TEXTool 2.5）
    """
    lines = ['<Atlas>']
    for elem, x, y, w, h in elements:
        lines.append(
            '\t<Element name="%s" u1="%.6f" v1="%.6f" u2="%.6f" v2="%.6f" '
            'z1="%d" z2="%d" />'
            % (elem, x / w if False else 0, 0, 0, 0, 0, 0)
        )
    lines.append('</Atlas>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 图标绘制
# ---------------------------------------------------------------------------

ICON_SIZE = 64

ICON_COLORS = {
    "aom_tractor_item": (156, 108, 60),
    "aom_plow": (150, 105, 60),
    "aom_seeder": (196, 150, 72),
    "aom_irrigator": (72, 132, 176),
    "aom_fertilizer": (132, 160, 80),
    "aom_weeder": (120, 84, 160),
    "aom_harvester": (200, 160, 60),
    "aom_tractor_chassis": (156, 108, 60),
}

ICON_GLYPHS = {
    "aom_tractor_item": "拖",
    "aom_plow": "犁",
    "aom_seeder": "种",
    "aom_irrigator": "水",
    "aom_fertilizer": "肥",
    "aom_weeder": "铲",
    "aom_harvester": "收",
    "aom_tractor_chassis": "拖",
}


def draw_icon(name):
    size = ICON_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = ICON_COLORS.get(name, (140, 140, 140))
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=10, fill=color + (255,),
                        outline=(60, 45, 30, 255), width=2)
    glyph = ICON_GLYPHS.get(name, "?")
    try:
        from PIL import ImageFont
        font = None
        for p in ("/System/Library/Fonts/PingFang.ttc",
                  "/System/Library/Fonts/STHeiti Medium.ttc",
                  "/System/Library/Fonts/Hiragino Sans GB.ttc"):
            if os.path.exists(p):
                font = ImageFont.truetype(p, 40)
                break
        if font:
            d.text((size // 2, size // 2), glyph, font=font, fill=(250, 240, 220, 255),
                   anchor="mm")
        else:
            raise RuntimeError("no font")
    except Exception:
        d.rectangle([size // 2 - 12, size // 2 - 12, size // 2 + 12, size // 2 + 12],
                    fill=(250, 240, 220, 255))
    return img


def build_atlas(tex_name, names):
    """把若干 64x64 图标拼成一张横向图集，写 .tex(PNG) + .xml"""
    n = len(names)
    W, H = ICON_SIZE * n, ICON_SIZE
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    elems = []
    for i, nm in enumerate(names):
        icon = draw_icon(nm)
        sheet.paste(icon, (i * ICON_SIZE, 0))
        elems.append((nm + ".tex", i * ICON_SIZE, 0, ICON_SIZE, ICON_SIZE))

    png_path = os.path.join(IMG, tex_name + ".png")
    sheet.save(png_path)

    # .tex：DSH 环境下无 TEXTool，用 PNG 内容作为 .tex 的载荷，
    # 并额外写标准 TEXTool 2.5 header，便于后续替换
    header = b"\x01\x00\x00\x00" + struct.pack("<HH", W, H)
    with open(os.path.join(IMG, tex_name + ".tex"), "wb") as f:
        f.write(header)
        f.write(open(png_path, "rb").read())

    xml = ['<Atlas version="1.0">']
    for nm, x, y, w, h in elems:
        u1, v1 = x / W, 1 - (y + h) / H
        u2, v2 = (x + w) / W, 1 - y / H
        xml.append(
            '\t<Element name="%s" u1="%.6f" v1="%.6f" u2="%.6f" v2="%.6f" x="%d" y="%d" w="%d" h="%d" />'
            % (nm, u1, v1, u2, v2, x, y, w, h)
        )
    xml.append("</Atlas>")
    with open(os.path.join(IMG, tex_name + ".xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(xml) + "\n")
    print("atlas:", tex_name, "->", [e[0] for e in elems])


def build_modicon():
    img = Image.new("RGBA", (512, 512), (36, 28, 22, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 24, 488, 488], radius=48, fill=(92, 64, 36, 255),
                        outline=(210, 168, 104, 255), width=8)
    d.rectangle([120, 260, 400, 350], fill=(190, 132, 60, 255), outline=(60, 40, 20, 255), width=5)
    d.rectangle([170, 200, 260, 270], fill=(190, 132, 60, 255), outline=(60, 40, 20, 255), width=5)
    d.ellipse([130, 330, 210, 410], fill=(50, 50, 50, 255), outline=(20, 20, 20, 255), width=5)
    d.ellipse([310, 330, 390, 410], fill=(50, 50, 50, 255), outline=(20, 20, 20, 255), width=5)
    for i in range(5):
        d.line([(400, 300 + i * 12), (470, 300 + i * 12)], fill=(210, 168, 104, 255), width=5)
    img.save(os.path.join(MOD, "modicon.png"))
    header = b"\x01\x00\x00\x00" + struct.pack("<HH", 512, 512)
    with open(os.path.join(MOD, "modicon.tex"), "wb") as f:
        f.write(header)
        f.write(open(os.path.join(MOD, "modicon.png"), "rb").read())
    with open(os.path.join(MOD, "modicon.xml"), "w", encoding="utf-8") as f:
        f.write('<Atlas version="1.0">\n\t<Element name="modicon.tex" u1="0" v1="0" u2="1" v2="1" />\n</Atlas>\n')
    print("modicon ok")


# ---------------------------------------------------------------------------
# 极简动画包（DST anim.zip 结构）
# ---------------------------------------------------------------------------

def make_anim_zip(zip_path, build_name, anims):
    """
    anims: { anim_name: {"frames": n, "loop": bool} }
    生成一个占位动画包：build 名 + 各动画帧的符号列表。
    真正的帧图在本环境无法生成合法规格的 .tex，这里只保证包结构与命名正确，
    游戏内会显示为空白/默认方块，替换正式美术即可。
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(build_name + ".build", "PLACEHOLDER")
        for anim_name, info in anims.items():
            z.writestr("%s-%s.anim" % (build_name, anim_name), "PLACEHOLDER")
    print("anim:", os.path.basename(zip_path), "build=", build_name, "anims=", list(anims))


def main():
    # 图标 / 封面已由正式美术提供（tools/build_tex.py 编译成 .tex），此处不再生成。
    # 这里只生成占位动画包，避免缺少 build 导致加载失败。
    make_anim_zip(os.path.join(ANIM, "aom_tractor_chassis.zip"), "aom_tractor_chassis",
                  {"idle": {"frames": 1, "loop": True},
                   "work": {"frames": 4, "loop": False},
                   "death": {"frames": 1, "loop": False},
                   "idle_packed": {"frames": 1, "loop": True}})
    make_anim_zip(os.path.join(ANIM, "aom_attachment_shared.zip"), "aom_attachment_shared",
                  {k: {"frames": 1, "loop": True} for k in
                   ["plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"]})
    make_anim_zip(os.path.join(ANIM, "aom_attachment_symbols.zip"), "aom_attachment_symbols",
                  {k: {"frames": 1, "loop": True} for k in
                   ["empty", "plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"]})
    print("done")


if __name__ == "__main__":
    main()
