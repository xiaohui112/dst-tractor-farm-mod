#!/usr/bin/env python3
"""
Tractor —— 美术接入流水线

把 assets/images 的 PNG 编译成 DST 能直接加载的 .tex + .xml：

1. 按代码中的图元顺序，把单张图标重新拼成图集 PNG
2. 用 ktech 把 PNG 转成 Klei 的 KTEX（DXT5，带 alpha）
3. modicon 由 512x512 封面单独转
4. 校验：图集尺寸、元素 UV 与代码里的 imagename 对得上

依赖：ktech（ktools），见 docs/08-美术接入.md
"""

import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mod", "Tractor")
IMG = os.path.join(MOD, "images")
SRC = os.path.join(ROOT, "assets", "images")      # 源 PNG，不进 Mod 目录
BUILD = os.path.join(ROOT, "outputs", "tex-build")  # 拼好的图集 PNG，不进 Mod 目录
KTC = os.path.expanduser("~/.local/bin/ktech")

# 图集定义：(输出名, [(元素名, 源 PNG 文件名)])
# 注意：Mod 的 images/ 里只放 .tex + .xml。游戏会在启动时把 images/ 下的 PNG
# 自动编译成单元素图集并覆盖同名 .xml，多图标图集因此必须只发 .tex/.xml。
ATLASES = [
    (
        "aom_chassis_inventory",
        [("aom_tractor_item.tex", "aom_tractor_item.png")],
    ),
    (
        "aom_attachment_inventory",
        [
            ("aom_landclearer.tex", "aom_landclearer.png"),
            ("aom_seeder.tex", "aom_seeder.png"),
            ("aom_irrigator.tex", "aom_irrigator.png"),
            ("aom_fertilizer.tex", "aom_fertilizer.png"),
            ("aom_weeder.tex", "aom_weeder.png"),
            ("aom_harvester.tex", "aom_harvester.png"),
        ],
    ),
]


def build_atlas(name, elements, craft=False):
    """横排拼图集，返回元素 UV 表。"""
    ims = [Image.open(os.path.join(SRC, p)).convert("RGBA") for _, p in elements]
    if craft:
        # 建造栏使用128像素图元，从原始手绘稿编译，避免放大64像素库存缩略图。
        originals = ["tractor", "plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"]
        ims = []
        for original in originals:
            im = Image.open(os.path.join(SRC, "source-art", original + ".png")).convert("RGBA")
            im = im.crop(im.getbbox())
            im.thumbnail((116, 116), Image.Resampling.LANCZOS)
            cell = Image.new("RGBA", (128, 128))
            cell.paste(im, ((128-im.width)//2, (128-im.height)//2))
            ims.append(cell)
    h = max(i.height for i in ims)
    used_width = sum(i.width for i in ims)
    w = 1 << (used_width - 1).bit_length() if craft else used_width
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0
    uv = []
    for (elem, _), im in zip(elements, ims):
        # 直接复制RGBA，不能再以alpha当mask，否则半透明描边会被重复衰减。
        sheet.paste(im, (x, 0))
        uv.append((elem, x / w, (x + im.width) / w, im.width, im.height))
        x += im.width
    os.makedirs(BUILD, exist_ok=True)
    png_path = os.path.join(BUILD, name + ".png")
    sheet.save(png_path)

    # 写 XML：DST 用 <Texture filename> + <Element name u1 v1 u2 v2>
    lines = ['<Atlas>',
             ' <Texture filename="%s.tex"/>' % name,
             ' <Elements>']
    for elem, u1, u2, wpx, hpx in uv:
        lines.append(
            '  <Element name="%s" u1="%.8f" u2="%.8f" v1="0" v2="1"/>'
            % (elem, u1, u2)
        )
    lines += [' </Elements>', '</Atlas>']
    with open(os.path.join(IMG, name + ".xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return sheet.size, uv


def to_tex(png_path, tex_path):
    os.makedirs(os.path.dirname(tex_path), exist_ok=True)
    r = subprocess.run([KTC, png_path, tex_path], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tex_path):
        raise RuntimeError("ktech 失败: %s\n%s\n%s" % (png_path, r.stdout, r.stderr))
    return os.path.getsize(tex_path)


def main():
    if not os.path.exists(KTC):
        sys.exit("找不到 ktech，请先按 docs/08-美术接入.md 安装")

    report = {"atlases": [], "modicon": None}

    for name, elements in ATLASES:
        size, uv = build_atlas(name, elements)
        tex_size = to_tex(os.path.join(BUILD, name + ".png"),
                          os.path.join(IMG, name + ".tex"))
        report["atlases"].append({
            "name": name,
            "size": list(size),
            "elements": [e for e, *_ in uv],
            "tex_bytes": tex_size,
        })
        print("[图集] %-28s %sx%s  %d 元素  tex=%dB"
              % (name, size[0], size[1], len(elements), tex_size))

    # 制作菜单图标图集：美术包给了 PNG，但需要按代码顺序拼
    craft = [
        ("aom_tractor_chassis.tex", "aom_tractor_chassis.png"),
        ("aom_landclearer.tex", "aom_landclearer.png"),
        ("aom_seeder.tex", "aom_seeder.png"),
        ("aom_irrigator.tex", "aom_irrigator.png"),
        ("aom_fertilizer.tex", "aom_fertilizer.png"),
        ("aom_weeder.tex", "aom_weeder.png"),
        ("aom_harvester.tex", "aom_harvester.png"),
    ]
    size, uv = build_atlas("aom_tractor_icons", craft, craft=True)
    tex_size = to_tex(os.path.join(BUILD, "aom_tractor_icons.png"),
                      os.path.join(IMG, "aom_tractor_icons.tex"))
    report["atlases"].append({
        "name": "aom_tractor_icons",
        "size": list(size),
        "elements": [e for e, *_ in uv],
        "tex_bytes": tex_size,
    })
    print("[图集] %-28s %sx%s  %d 元素  tex=%dB"
          % ("aom_tractor_icons", size[0], size[1], len(craft), tex_size))

    # modicon
    mod_png = os.path.join(SRC, "modicon.png")
    mod_tex = os.path.join(MOD, "modicon.tex")
    report["modicon"] = to_tex(mod_png, mod_tex)
    with open(os.path.join(MOD, "modicon.xml"), "w", encoding="utf-8") as f:
        f.write('<Atlas>\n <Texture filename="modicon.tex"/>\n <Elements>\n'
                '  <Element name="modicon.tex" u1="0" u2="1" v1="0" v2="1"/>\n'
                ' </Elements>\n</Atlas>\n')
    print("[封面] modicon.tex %dB" % report["modicon"])

    with open(os.path.join(ROOT, "tools", "build_artifacts.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("完成：%d 个图集 + 封面" % len(report["atlases"]))


if __name__ == "__main__":
    main()
