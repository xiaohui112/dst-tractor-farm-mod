#!/usr/bin/env python3
"""
Tractor —— 静态自检

在没有 DST 客户端的机器上，尽可能提前发现会让 Mod 加载失败的问题：
1. 全部 Lua 文件语法可编译
2. modinfo.lua 字段齐全、configuration_options 结构正确
3. modmain / prefab 里引用的自定义 prefab、图集、动画文件真实存在
4. aom_common 能在桩环境下加载并导出常量（防止 nil 索引类崩溃）
5. 交叉引用：底盘用到的常量、动作、组件名都存在

用法：
    python3 tools/selfcheck.py
"""

import argparse
import json
from pathlib import Path
import glob
import os
import re
import sys
import struct
from zipfile import ZipFile, BadZipFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mod", "Tractor")

FAILS = []
WARNS = []


def fail(msg):
    FAILS.append(msg)


def warn(msg):
    WARNS.append(msg)


def read(rel):
    with open(os.path.join(MOD, rel), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. 语法检查
# ---------------------------------------------------------------------------

def check_syntax():
    try:
        from lupa.lua51 import LuaRuntime
    except ImportError:
        fail("缺少必需依赖 lupa.lua51，不能执行 Lua 语法检查；请安装 requirements-dev.txt")
        return
    L = LuaRuntime()
    chk = L.eval("function(src,name) local f,e=loadstring(src,name) return f~=nil, e end")
    files = sorted(glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True))
    for p in files:
        ok, err = chk(open(p, encoding="utf-8").read(), os.path.relpath(p, MOD))
        if not ok:
            fail("语法错误 %s: %s" % (os.path.relpath(p, MOD), err))


# ---------------------------------------------------------------------------
# 2. modinfo
# ---------------------------------------------------------------------------

REQUIRED_MODINFO = [
    "name", "description", "author", "version", "api_version", "priority",
    "dst_compatible", "all_clients_require_mod", "server_filter_tags",
]


def check_modinfo():
    src = read("modinfo.lua")
    for key in REQUIRED_MODINFO:
        if not re.search(r"^\s*%s\s*=" % re.escape(key), src, re.M):
            fail("modinfo.lua 缺少字段: %s" % key)

    # icon 引用的文件必须存在
    for m in re.finditer(r'^\s*(icon|icon_atlas)\s*=\s*"([^"]+)"', src, re.M):
        if not os.path.exists(os.path.join(MOD, m.group(2))):
            fail("modinfo 引用的文件不存在: %s" % m.group(2))

    # 每个配置项必须 name/label/options/default
    blocks = re.findall(r"\t\{\s*name\s*=\s*\"(\w+)\".*?\n\t\},", src, re.S)
    for name in blocks:
        seg = src[src.index('name = "%s"' % name):]
        seg = seg[:seg.index("\n\t},") + 4]
        for field in ("label", "options", "default"):
            if field + " = " not in seg:
                fail("配置项 %s 缺少 %s" % (name, field))


# ---------------------------------------------------------------------------
# 3. 资源引用
# ---------------------------------------------------------------------------

def check_recipe_ingredients():
    """配方里的 Ingredient 必须是真实存在的 prefab：写错名字时制作菜单只显示红方块，
    而且永远做不出来（v0.1.7 实机就是 electric_bt 不存在）。"""
    game = find_game_folder()
    if game is None:
        warn("未找到《饥荒联机版》安装目录，跳过配方材料核对（可设 DST_GAME）")
        return
    bundle = os.path.join(game, "data", "databundles", "scripts.zip")
    if not os.path.exists(bundle):
        warn("找不到 data/databundles/scripts.zip，跳过配方材料核对")
        return
    known = set()
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            if not name.endswith(".lua"):
                continue
            text = archive.read(name).decode("utf-8", "replace")
            known.update(re.findall(r'Prefab\(\s*"([a-z0-9_]+)"', text))
        known.update(re.findall(r'"([a-z0-9_]+)"',
                               archive.read("scripts/prefablist.lua").decode("utf-8", "replace")))
    for path in glob.glob(os.path.join(MOD, "scripts", "prefabs", "*.lua")):
        text = open(path, encoding="utf-8").read()
        known.update(re.findall(r'Prefab\(\s*"([a-z0-9_]+)"', text))
        known.update(re.findall(r'MakeAttachment\(\s*"([a-z0-9_]+)"', text))
    for name in sorted(set(re.findall(r'Ingredient\(\s*"([^"]+)"', read("modmain.lua")))):
        if name not in known:
            fail("配方材料 Ingredient(\"%s\") 在当前游戏版本里不存在" % name)


def check_no_source_png():
    """Mod 目录里不能放 PNG：游戏启动会把 images/ 下的 PNG 自动编译成单元素图集，
    覆盖手工写的多图标 .xml（v0.1.5 实机就是因此丢了制作菜单图标）。"""
    for path in glob.glob(os.path.join(MOD, "images", "*.png")) + glob.glob(os.path.join(MOD, "*.png")):
        fail("%s 会让游戏自动重编译图集并覆盖同名 .xml；源 PNG 请放 assets/images/"
             % os.path.relpath(path, MOD).replace(os.sep, "/"))


def check_assets():
    main = read("modmain.lua")
    # Assets 里声明的文件
    for m in re.finditer(r'Asset\("(\w+)",\s*"([^"]+)"\)', main):
        kind, path = m.group(1), m.group(2)
        if not os.path.exists(os.path.join(MOD, path)):
            fail("Assets 声明但文件缺失: %s %s" % (kind, path))

    # PrefabFiles 里的文件
    m = re.search(r"PrefabFiles\s*=\s*\{(.*?)\}", main, re.S)
    if m:
        for name in re.findall(r'"([^"]+)"', m.group(1)):
            p = os.path.join(MOD, "scripts", "prefabs", name + ".lua")
            if not os.path.exists(p):
                fail("PrefabFiles 声明的文件不存在: scripts/prefabs/%s.lua" % name)

    # prefab 内设置 bank/build 的动画必须存在
    prefab_files = glob.glob(os.path.join(MOD, "scripts", "prefabs", "*.lua"))
    prefab_files += glob.glob(os.path.join(MOD, "modmain.lua"))
    for p in prefab_files:
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r'AnimState:Set(Build|Bank)\("([^"]+)"\)', src):
            # 原版 dirt_puff 的 bank/build 共享 smoke_puff_small.zip。
            native = {"small_puff": "smoke_puff_small", "smoke_puff_small": "smoke_puff_small"}
            if m.group(2) in native and re.search(
                r'Asset\("ANIM",\s*"anim/%s.zip"\)' % native[m.group(2)], src
            ):
                continue
            z = os.path.join(MOD, "anim", m.group(2) + ".zip")
            if not os.path.exists(z):
                fail("%s 引用了不存在的动画包 anim/%s.zip" % (os.path.basename(p), m.group(2)))


def check_animation_assets():
    expected = {
        "aom_tractor_chassis": ({"idle", "work", "death", "idle_packed"},
                                {"body", "attachment", "attachment_front"}),
        "aom_attachment_shared": ({"plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"},
                                   {"plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"}),
        "aom_attachment_symbols": ({"empty", "plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"},
                                    {"empty", "plow", "seeder", "irrigator", "fertilizer", "weeder", "harvester"}),
    }
    for name, (animations, symbols) in expected.items():
        try:
            with ZipFile(os.path.join(MOD, "anim", name + ".zip")) as archive:
                if archive.testzip() is not None:
                    raise ValueError("ZIP CRC 校验失败")
                build, anim = archive.read("build.bin"), archive.read("anim.bin")
                for data, signature, version in ((build, b"BILD", 6), (anim, b"ANIM", 4)):
                    if len(data) < 24 or data[:8] != signature + struct.pack("<I", version):
                        raise ValueError("缺少真实 " + signature.decode() + " 数据或版本不匹配")
                if name.encode() not in build:
                    raise ValueError("build 名称与 prefab 不匹配")
                for value in symbols:
                    encoded = value.encode()
                    if struct.pack("<I", len(encoded)) + encoded not in build:
                        raise ValueError("缺少挂件/车体符号：" + value)
                for value in animations:
                    encoded = value.encode()
                    if struct.pack("<I", len(encoded)) + encoded not in anim:
                        raise ValueError("缺少动画：" + value)
                atlases = [entry for entry in archive.namelist() if entry.endswith(".tex")]
                if not atlases:
                    raise ValueError("缺少贴图图集")
                for atlas in atlases:
                    data = archive.read(atlas)
                    if len(data) < 16 or data[:4] != b"KTEX":
                        raise ValueError("贴图图集无效：" + atlas)
        except (OSError, KeyError, BadZipFile, ValueError) as exc:
            fail(name + " 动画包校验失败：" + str(exc))


def check_driver_assets():
    manifest=read("scripts/aom_driver_visual_bank.lua")
    if not re.search(r"(?m)^\s*return\s*\{\s*available\s*=\s*true\b",manifest):
        return
    from driver_animation import parse_anim,build_symbols,name_hash
    try:
        with ZipFile(os.path.join(MOD,"anim","aom_tractor_driver.zip")) as archive:
            if archive.testzip() is not None:
                raise ValueError("驾驶动画 ZIP CRC 失败")
            with ZipFile(os.path.join(MOD,"anim","aom_tractor_cabin.zip")) as shared:
                build,symbols=build_symbols(shared.read("build.bin"))
                atlases=[n for n in shared.namelist() if n.endswith(".tex")]
                if not atlases or any(shared.read(n)[:4]!=b"KTEX" for n in atlases):
                    raise ValueError("共享驾驶室图集缺失或无效")
            if build!="aom_tractor_cabin":
                raise ValueError("驾驶室 build 名称不匹配")
            owned={"aom_cabin_back","aom_cabin_front","aom_driver_attachment_rear","aom_driver_attachment_front"}
            if not {name_hash(name) for name in owned}.issubset(symbols):
                raise ValueError("驾驶室或前后挂件符号缺失")
            bank=parse_anim(archive.read("anim.bin"))
            if not bank["animations"] or any(a["bank"]!=name_hash("aom_tractor_driver") for a in bank["animations"]):
                raise ValueError("驾驶动画 bank 名称不匹配")
            required={"mount","dismount","idle_loop","run_pre","run_loop","run_pst"}
            if not required.issubset({a["name"] for a in bank["animations"]}):
                raise ValueError("缺少原版骑乘所需动画")
            keys=[(a["name"],a["facing"]) for a in bank["animations"]]
            if len(set(keys))!=len(keys):
                raise ValueError("驾驶动画包含重复动作/朝向")
            for name in required:
                if not {5,48,192,2,8}.issubset({a["facing"] for a in bank["animations"] if a["name"]==name}):
                    raise ValueError("驾驶动作八向不完整："+name)
            for filename,bankname in [("aom_tractor_driver_075.zip","aom_tractor_driver_075"),
                                      ("aom_tractor_driver_125.zip","aom_tractor_driver_125"),
                                      ("aom_tractor_driver_150.zip","aom_tractor_driver_150")]:
                with ZipFile(os.path.join(MOD,"anim",filename)) as variant:
                    if variant.testzip() is not None:raise ValueError("变体CRC错误："+filename)
                    data=parse_anim(variant.read("anim.bin"))
                    if {(a['name'],a['facing']) for a in data['animations']}!=set(keys):raise ValueError("变体动作/朝向缺失："+filename)
                    if any(a['bank']!=name_hash(bankname) for a in data['animations']):raise ValueError("变体bank错误："+filename)
    except (OSError,KeyError,BadZipFile,ValueError) as exc:
        fail("已启用驾驶坐姿但资源未准备好："+str(exc))


def check_music_assets():
    # 可选音频通过清单动态注册，静态 Asset 正则看不到；启用时必须检查实际导出文件。
    manifest = read("scripts/aom_irrigator_music_bank.lua")
    if not re.search(r"available\s*=\s*true", manifest):
        return
    from music_bank import inspect_pair
    try:
        with open(os.path.join(MOD, "sound", "aom_irrigator_music.fev"), "rb") as source:
            fev = source.read()
        with open(os.path.join(MOD, "sound", "aom_irrigator_music.fsb"), "rb") as source:
            fsb = source.read()
        inspect_pair(fev, fsb)
    except (OSError, ValueError) as exc:
        fail("已启用音乐但音频包校验失败: " + str(exc))


# ---------------------------------------------------------------------------
# 4. aom_common 桩加载
# ---------------------------------------------------------------------------

def check_common_module():
    try:
        from lupa.lua51 import LuaRuntime
    except ImportError:
        return
    for lang in ("zh", "en"):
        L = LuaRuntime()
        L.execute("GLOBAL = {}; STRINGS = {NAMES={}, RECIPE_DESC={}, ACTIONS={}}")
        L.execute('AOM_CONFIG = { LANGUAGE = "%s" }' % lang)
        try:
            L.execute(read("scripts/aom_common.lua"))
        except Exception as e:
            fail("aom_common.lua 在 %s 下加载失败: %s" % (lang, e))
            continue
        for const in ("PLOW", "SEEDER", "IRRIGATOR", "FERTILIZER", "WEEDER", "HARVESTER"):
            val = L.eval("GLOBAL.AOM_ATTACHMENT_TYPE.%s" % const)
            if val is None:
                fail("aom_common 未导出 AOM_ATTACHMENT_TYPE.%s" % const)
        for tag in ("TRACTOR", "ATTACHMENT"):
            if L.eval("GLOBAL.AOM_TAG.%s" % tag) is None:
                fail("aom_common 未导出 AOM_TAG.%s" % tag)
        if L.eval("GLOBAL.AOM_WORK_STEP") is None:
            fail("aom_common 未导出 AOM_WORK_STEP")
        if not L.eval("STRINGS.NAMES.AOM_LANDCLEARER"):
            fail("aom_common 未写入 STRINGS.NAMES（%s）" % lang)


# ---------------------------------------------------------------------------
# 4.5 modmain 的受限全局环境
# ---------------------------------------------------------------------------

# 与官方 scripts/mods.lua 的 CreateEnvironment + modutil.InsertPostInitFunctions 对应。
# modmain.lua 不在全局环境里执行：没有 pcall / assert / Vector3 / TheWorld 等，
# 必须写成 GLOBAL.pcall / GLOBAL.Vector3，否则加载即报
# "attempt to call global 'x' (a nil value)" 并整只 Mod 被禁用。
MOD_ENV_GLOBALS = set("""
pairs ipairs print math table type string tostring require Class
TUNING LEVELCATEGORY GROUND WORLD_TILES LOCKS KEYS LEVELTYPE GLOBAL modname MODROOT CHARACTERLIST
self arg
AddAction AddBrainPostInit AddCharacterRecipe AddClassPostConstruct AddClientModRPCHandler
AddComponentAction AddComponentPostInit AddCookerRecipe AddCustomizeGroup AddCustomizeItem
AddDeconstructRecipe AddFalloffTexture AddGameMode AddGamePostInit AddGlobalClassPostConstruct
AddIngredientValues AddLevel AddLevelPreInit AddLevelPreInitAny AddLoadingTip AddLocation
AddMinimapAtlas AddModCharacter AddModRPCHandler AddModShadersInit AddModShadersSortAndEnable
AddPlayerPostInit AddPopup AddPrefabPostInit AddPrefabPostInitAny AddPrototyperDef AddRecipe
AddRecipe2 AddRecipeFilter AddRecipePostInit AddRecipePostInitAny AddRecipeTab AddRecipeToFilter
AddReplicableComponent AddRoom AddRoomPreInit AddShardModRPCHandler AddSimPostInit
AddStartLocation AddStategraphActionHandler AddStategraphEvent AddStategraphPostInit
AddStategraphState AddTask AddTaskPreInit AddTaskSet AddTaskSetPreInit AddTaskSetPreInitAny
AddTile AddUserCommand AddVoteCommand Asset ExcludeClothingSymbolForModCharacter
GetClientModRPC GetClientModRPCHandler GetCustomizeDescription GetModConfigData GetModRPC
GetModRPCHandler GetShardModRPC GetShardModRPCHandler Ingredient LoadPOFile Prefab Recipe
RegisterInventoryItemAtlas RegisterScrapbookIconAtlas RegisterSkilltreeBGForCharacter
RegisterSkilltreeIconsAtlas RegisterTileRange ReleaseID ReloadFrontEndAssets ReloadPreloadAssets
RemapSoundEvent RemoveCustomizeGroup RemoveCustomizeItem RemoveDefaultCharacter RemoveLoadingTip
RemoveRecipeFromFilter RemoveRemapSoundEvent SendModRPCToClient SendModRPCToServer SendModRPCToShard
SetFalloffProperty SetLoadingTipCategoryIcon SetLoadingTipCategoryWeights SetMiniMapTileProperty
SetModHUDFocus SetTileProperty modassert moderror modimport CurrentRelease
""".split())

MOD_ENV_RESTRICTED = set("""
pcall xpcall error assert setmetatable getmetatable rawget rawset next select unpack tonumber
os io debug loadstring loadfile dofile collectgarbage coroutine
Vector3 TheWorld TheSim TheNet TheInput TheFrontEnd ThePlayer ActionHandler State Time
STRINGS ACTIONS RECIPES
""".split())

# 这些名字是模块（require 才能拿到），_G 里没有，写成 GLOBAL.xxx 会被 strict.lua 拦下。
GLOBAL_MODULE_NAMES = {"containers"}

LUA_KEYWORDS = set("""
and break do else elseif end false for function goto if in local nil not or repeat return then
true until while
""".split())


def _strip_lua_literals(src):
    src = re.sub(r"--\[(=*)\[.*?\]\1\]", "", src, flags=re.S)
    src = re.sub(r"\[(=*)\[.*?\]\1\]", "", src, flags=re.S)
    src = re.sub(r"--[^\n]*", "", src)
    src = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", src)
    return src


def check_mod_environment():
    for name in ("modmain.lua", "modworldgenmain.lua"):
        if not os.path.exists(os.path.join(MOD, name)):
            continue
        text = _strip_lua_literals(read(name))
        defined = set(MOD_ENV_GLOBALS) | LUA_KEYWORDS
        defined.update(re.findall(r"\blocal\s+([A-Za-z_]\w*)", text))
        defined.update(re.findall(r"\blocal\s+function\s+([A-Za-z_]\w*)", text))
        for m in re.finditer(r"\blocal\s+([A-Za-z_][\w\s,]*?)\s*=", text):
            defined.update(n.strip() for n in m.group(1).split(",") if re.match(r"^\w+$", n.strip()))
        for m in re.finditer(r"function[^(]*\(([^)]*)\)", text):
            defined.update(n.strip() for n in m.group(1).split(",") if re.match(r"^\w+$", n.strip()))
        for m in re.finditer(r"\bfor\s+([\w\s,]+?)\s+(?:in|=)", text):
            defined.update(n.strip() for n in m.group(1).split(",") if re.match(r"^\w+$", n.strip()))
        # 顶层赋值会在 env 里创建字段（Assets / PrefabFiles 等）
        defined.update(re.findall(r"(?m)^\s*([A-Za-z_]\w*)\s*=[^=]", text))

        missing = {}
        for lineno, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(r"(?<![\w.:])([A-Za-z_]\w*)\s*[.(\[:]", line):
                identifier = m.group(1)
                if identifier not in defined:
                    missing.setdefault(identifier, []).append(lineno)
            for identifier in MOD_ENV_RESTRICTED - defined:
                if re.search(r"(?<![\w.:])%s\b" % identifier, line):
                    missing.setdefault(identifier, []).append(lineno)
        if missing:
            detail = ", ".join("%s:%s" % (n, ",".join(str(v) for v in sorted(set(lines))))
                               for n, lines in sorted(missing.items()))
            fail("%s 用了 Mod 受限环境里没有的全局：%s（改用 GLOBAL.xxx 或 local 别名）"
                 % (name, detail))
        for lineno, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(r"GLOBAL\.([A-Za-z_]\w*)", line):
                if m.group(1) in GLOBAL_MODULE_NAMES:
                    fail("%s:%d 写了 GLOBAL.%s：它是模块不是全局，改成 require(\"%s\")"
                         % (name, lineno, m.group(1), m.group(1)))


def check_script_modules():
    """scripts/ 下的模块由 require 加载进游戏主环境，不能引用只有 modmain 环境才有的名字。"""
    blocked = {
        "GLOBAL": "主环境没有 GLOBAL，scripts/strict.lua 会报 variable 'GLOBAL' is not declared",
        "MODROOT": "主环境没有 MODROOT，strict.lua 会报变量未声明",
        "modimport": "主环境没有 modimport，strict.lua 会报变量未声明",
        "modname": "主环境没有 modname，strict.lua 会报变量未声明",
        "GetModConfigData": "主环境的 GetModConfigData 必须显式传 modname，模块里没有绑定，"
                            "改由 modmain 放进 GLOBAL.AOM_CONFIG",
        "MOD_RPC": "主环境没有 MOD_RPC（只在 modmain 环境里），RPC 句柄改由 modmain 放进 GLOBAL.AOM_RPC",
    }
    for path in sorted(glob.glob(os.path.join(MOD, "scripts", "**", "*.lua"), recursive=True)):
        rel = os.path.relpath(path, MOD).replace(os.sep, "/")
        text = _strip_lua_literals(open(path, encoding="utf-8").read())
        for name, reason in blocked.items():
            if not re.search(r"(?<![\w.:])%s\b" % name, text):
                continue
            if re.search(r"\blocal\s+%s\s*=" % name, text):
                continue
            fail("%s 在游戏主环境里引用了 %s：%s" % (rel, name, reason))
        for module in GLOBAL_MODULE_NAMES:
            if re.search(r"GLOBAL\.%s\b" % module, text):
                fail("%s 写了 GLOBAL.%s：它是模块不是全局，改成 require(\"%s\")"
                     % (rel, module, module))


def find_game_folder():
    """开发机装了游戏时，直接用游戏脚本核对 require / 类路径；找不到就跳过。"""
    candidates = [os.environ.get("DST_GAME")]
    steam_roots = [Path.home()/"Library/Application Support/Steam",
                   Path.home()/".steam/steam",Path.home()/".local/share/Steam"]
    for steam_root in steam_roots:
        libraries=[steam_root]
        vdf=steam_root/"steamapps/libraryfolders.vdf"
        if vdf.is_file():
            libraries += [Path(p.replace("\\\\","\\")) for p in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text())]
        for library in libraries:
            root=library/"steamapps/common/Don't Starve Together"
            candidates.extend([str(root),str(root/"dontstarve_steam.app/Contents")])
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = winreg.QueryValueEx(key, "SteamPath")[0]
        libraries = [steam]
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            with open(vdf, encoding="utf-8", errors="replace") as source:
                libraries += re.findall(r'"path"\s+"([^"]+)"', source.read())
        for library in libraries:
            candidates.append(os.path.join(library.replace("\\\\", "\\"), "steamapps", "common",
                                           "Don't Starve Together"))
    except Exception:
        pass
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "data", "databundles")):
            return path
    return None


BASE_LIBRARY = set("""
pairs ipairs print math table type string tostring tonumber next select unpack require Class
pcall xpcall error assert rawget rawset setmetatable getmetatable coroutine os io debug loadstring
""".split())

ENGINE_GLOBALS = set("""
Vector3 TheSim TheNet TheWorld ThePlayer TheFrontEnd TheInput TheCamera AllPlayers CWD
net_float net_bool net_string net_entity net_vector3 kleifileexists
""".split())


def check_game_globals():
    """Mod 里调用的全局函数必须在当前游戏版本里存在：写错就是运行时
    "variable 'x' is not declared"（v0.1.8 实机的 SetPhysicsAttacker 就是这样）。"""
    game = find_game_folder()
    if game is None:
        warn("未找到《饥荒联机版》安装目录，跳过全局函数核对（可设 DST_GAME）")
        return
    bundle = os.path.join(game, "data", "databundles", "scripts.zip")
    if not os.path.exists(bundle):
        warn("找不到 data/databundles/scripts.zip，跳过全局函数核对")
        return
    known = set(BASE_LIBRARY) | set(ENGINE_GLOBALS)
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            if not name.endswith(".lua"):
                continue
            text = archive.read(name).decode("utf-8", "replace")
            known.update(re.findall(r"(?m)^\s*function\s+([A-Za-z_]\w*)", text))
            known.update(re.findall(r"(?m)^\s*([A-Za-z_]\w*)\s*=", text))
            known.update(re.findall(r"global\(\s*\"([A-Za-z_]\w*)\"", text))
    mod_files = sorted(glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True))
    # 模块写到 GLOBAL 上的常量（AOM_TAG 等）也算已知名字。
    for path in mod_files:
        known.update(re.findall(r"GLOBAL\.([A-Za-z_]\w*)\s*=", open(path, encoding="utf-8").read()))
    for path in mod_files:
        rel = os.path.relpath(path, MOD).replace(os.sep, "/")
        text = _strip_lua_literals(open(path, encoding="utf-8").read())
        defined = set(known) | LUA_KEYWORDS
        if rel == "modmain.lua":
            defined |= MOD_ENV_GLOBALS
        defined.update(re.findall(r"\blocal\s+([A-Za-z_]\w*)", text))
        defined.update(re.findall(r"\blocal\s+function\s+([A-Za-z_]\w*)", text))
        for m in re.finditer(r"\blocal\s+([A-Za-z_][\w\s,]*?)\s*=", text):
            defined.update(x.strip() for x in m.group(1).split(",") if re.match(r"^\w+$", x.strip()))
        for m in re.finditer(r"function[^(]*\(([^)]*)\)", text):
            defined.update(x.strip() for x in m.group(1).split(",") if re.match(r"^\w+$", x.strip()))
        for m in re.finditer(r"\bfor\s+([\w\s,]+?)\s+(?:in|=)", text):
            defined.update(x.strip() for x in m.group(1).split(",") if re.match(r"^\w+$", x.strip()))
        defined.update(re.findall(r"(?m)^\s*([A-Za-z_]\w*)\s*=[^=]", text))
        for lineno, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(r"(?<![\w.:])([A-Za-z_]\w*)\s*\(", line):
                name = m.group(1)
                if name not in defined:
                    fail("%s:%d 调用的 %s() 在当前游戏版本里不存在" % (rel, lineno, name))


def check_game_paths():
    """require 与 AddClassPostConstruct 的路径必须真实存在（跨版本改名会直接崩加载）。"""
    game = find_game_folder()
    if game is None:
        warn("未找到《饥荒联机版》安装目录，跳过 require/类路径核对（可设 DST_GAME）")
        return
    bundle = os.path.join(game, "data", "databundles", "scripts.zip")
    if not os.path.exists(bundle):
        warn("找不到 data/databundles/scripts.zip，跳过 require/类路径核对")
        return
    with ZipFile(bundle) as archive:
        entries = {name[len("scripts/"):-4] for name in archive.namelist()
                   if name.startswith("scripts/") and name.endswith(".lua")}
    local = {os.path.relpath(path, os.path.join(MOD, "scripts")).replace(os.sep, "/")[:-4]
             for path in glob.glob(os.path.join(MOD, "scripts", "**", "*.lua"), recursive=True)}
    for path in sorted(glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True)):
        rel = os.path.relpath(path, MOD).replace(os.sep, "/")
        text = _strip_lua_literals(open(path, encoding="utf-8").read())
        for match in re.finditer(r'require\s*\(?\s*"([^"]+)"', text):
            name = match.group(1)
            if name not in local and name not in entries:
                fail("%s 引用的 require(\"%s\") 在 Mod 与游戏脚本里都找不到" % (rel, name))
        for match in re.finditer(r'Add(?:Global)?ClassPostConstruct\s*\(\s*"([^"]+)"', text):
            name = match.group(1)
            if name not in entries:
                fail("%s 的 AddClassPostConstruct(\"%s\") 在当前游戏版本里不存在" % (rel, name))


# ---------------------------------------------------------------------------
# 5. 交叉引用
# ---------------------------------------------------------------------------

def check_cross_refs():
    chassis = read("scripts/prefabs/aom_tractor_chassis.lua")
    work = read("scripts/aom_farm_work.lua")
    main = read("modmain.lua")

    # 底盘调用的 farm work 方法必须真实存在
    for m in re.finditer(r"AOMFarmWork\.(\w+)", chassis):
        fn = m.group(1)
        if not re.search(r"function AOMFarmWork\.%s\(" % fn, work):
            fail("底盘调用了不存在的 AOMFarmWork.%s" % fn)

    # 底盘使用的自定义组件必须存在于 scripts/components
    for comp in re.findall(r'AddComponent\("(aom_\w+)"\)', chassis + main):
        p = os.path.join(MOD, "scripts", "components", comp + ".lua")
        if not os.path.exists(p):
            fail("使用了不存在的中自定义组件: %s" % comp)
        else:
            # 必须 return Class
            if "return" not in open(p, encoding="utf-8").read().splitlines()[-1]:
                warn("组件文件 %s 最后一行不是 return，可能无法注册" % comp)

    # 配方产物必须有对应 prefab
    for m in re.finditer(r'AddMachineRecipe\("(\w+)"', main):
        name = m.group(1)
        found = any(
            'MakeAttachment("%s"' % name in open(p, encoding="utf-8").read()
            or 'Prefab("%s"' % name in open(p, encoding="utf-8").read()
            for p in glob.glob(os.path.join(MOD, "scripts", "prefabs", "*.lua"))
        )
        if not found:
            fail("配方产物没有对应 prefab: %s" % name)

    # 配方图标
    for m in re.finditer(r'AddMachineRecipe\("(\w+)"', main):
        name = m.group(1)
        icon = os.path.join(MOD, "images", "aom_tractor_icons.xml")
        if not os.path.exists(icon):
            fail("配方图标图集缺失 images/aom_tractor_icons.xml")
        else:
            xml = open(icon, encoding="utf-8").read()
            if name + ".tex" not in xml:
                fail("配方图集里没有 %s.tex 这个元素" % name)

    # 挂件图标
    att_xml = os.path.join(MOD, "images", "aom_attachment_icons.xml")
    if os.path.exists(att_xml):
        xml = open(att_xml, encoding="utf-8").read()
        for name in ("aom_plow", "aom_seeder", "aom_irrigator",
                     "aom_fertilizer", "aom_weeder", "aom_harvester"):
            if name + ".tex" not in xml:
                fail("挂件图集里没有 %s.tex" % name)


# ---------------------------------------------------------------------------
# 6. 反模式：常见会导致运行时报错的写法
# ---------------------------------------------------------------------------

BAD_PATTERNS = [
    (r"\bGetAimAngle\s*\(", "GetAimAngle 不是 DST 的 API（EntityScript 无此方法）"),
    (r"SetMaxFuel\s*\(", "原版 fuel 组件没有 SetMaxFuel"),
    (r"loadstring\s*\(", "DST 运行环境禁止 loadstring"),
    (r"SGwilson_attacked", "SGwilson_attacked 不是真实函数名"),
    (r"AddRecipe2\([^)]*\bTECH\.ALCHEMY_TWO", "TECH.ALCHEMY_TWO 不存在，应为 TECH.SCIENCE_TWO"),
]


def check_bad_patterns():
    for p in sorted(glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True)):
        src = open(p, encoding="utf-8").read()
        for pat, why in BAD_PATTERNS:
            if re.search(pat, src):
                fail("%s 中存在无效写法：%s" % (os.path.relpath(p, MOD), why))


def check_local_functions_defined():
    """
    抓"调用了但没定义"的局部函数。
    只检查形如 `local function Foo(` 定义的、且在文件内以 `Foo(` 调用的名字。
    """
    import re
    for path in sorted(glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True)):
        # 去掉字符串和注释，避免把提示文字/标签里的 "scale (" 当成函数调用
        src = _strip_lua_literals(open(path, encoding="utf-8").read())
        defined = set(re.findall(r"^\s*local function (\w+)\s*\(", src, re.M))
        defined |= set(re.findall(r"^\s*local (\w+)\s*=\s*function", src, re.M))
        # `local x = ...` 的任何赋值也算定义（闭包捕获的变量合法）
        defined |= set(re.findall(r"^\s*local (\w+)\s*=", src, re.M))
        # 函数参数名（local function foo(a, b) / function T:m(a, b)）
        for params in re.findall(r"function[^(]*\(([^)]*)\)", src):
            for pname in params.split(","):
                pname = pname.strip()
                if pname and re.match(r"^\w+$", pname):
                    defined.add(pname)
        defined |= set(re.findall(r"for\s+([\w\s,]+)\s+in\s", src))
        # 所有 `名字(` 调用（排除方法调用 x:name()
        called = set(re.findall(r"(?<![:\w.])(\w+)\s*\(", src))
        # 已知的合法全局
        ok = defined | {
            "if","while","for","return","print","type","pairs","ipairs","tostring",
            "tonumber","require","assert","error","math","table","string","Vector3",
            "pcall","xpcall","select","next","rawget","rawset","setmetatable","getmetatable",
            "CreateEntity","Prefab","MakePlacer","SpawnPrefab","GetModConfigData",
            "net_float","net_entity","net_bool","net_string","net_vector3",
            "AddComponentAction","AddAction","AddRecipe2","AddDeconstructRecipe",
            "AddModRPCHandler","AddPrefabPostInit","MakeInventoryPhysics",
            "MakeObstaclePhysics","MakeInventoryFloatable","SetPhysicsAttacker",
            "MakeHauntableLaunch","MakeMediumBurnable","MakeSmallBurnable",
            "MakeSmallPropagator","MakeLargePropagator","IsFuel","TUNING","TheWorld",
            "TheSim","TheInput","STRINGS","ACTIONS","TECH","Ingredient","Class",
            "function","elseif","and","or","not","local","end","do","then",
        }
        suspended = set(re.findall(r"^local (\w+)\s*$", src, re.M))
        # 只报"看起来像自己定义却没定义"的名字：小写开头、且不在任何 required 模块里
        missing = {n for n in called - ok
                   if re.match(r"^[a-z]\w*$", n)
                   and n not in suspended
                   and not n.startswith(("self", "inst", "The"))}
        # 白名单：Lua 标准库和常见 DST 全局
        missing -= {
            "clamp","floor","ceil","abs","max","min","sqrt","cos","sin","random",
            "atan","hypot","pi","huge","insert","remove","concat","find","sub",
            "format","rep","gmatch","sort","unpack","fmod","pow","exp","log",
        }
        if missing:
            fail("%s 可能调用了未定义的函数: %s"
                 % (os.path.relpath(path, MOD), sorted(missing)))


def check_giant_farming():
    """语法和文件存在性不能代替播种行为检查。"""
    try:
        from lupa.lua51 import LuaRuntime
    except ImportError:
        fail("缺少必需依赖 lupa.lua51，不能执行行为回归")
        return
    import io
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tools", "tests"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,buffer=True).run(suite)
    if not result.wasSuccessful() or result.testsRun == 0:
        fail("行为回归失败：\n" + stream.getvalue())
    elif result.skipped:
        warn("行为回归跳过 %d 项：%s" % (len(result.skipped), "; ".join(str(t)+": "+why for t,why in result.skipped)))
    else:
        print("行为回归：%d 项通过（Lua 5.1）" % result.testsRun)
    return {"run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',action='store_true',help='发布检查：警告或跳过也阻止打包')
    parser.add_argument('--report',type=Path,default=Path(ROOT)/'outputs/selfcheck-validation.json')
    args=parser.parse_args(argv)
    FAILS.clear();WARNS.clear()
    checks=[]
    functions=[check_syntax,check_modinfo,check_no_source_png,check_assets,check_animation_assets,
               check_driver_assets,check_music_assets,check_common_module,check_mod_environment,
               check_script_modules,check_game_paths,check_game_globals,check_recipe_ingredients,
               check_cross_refs,check_local_functions_defined,check_bad_patterns,check_giant_farming]
    for fn in functions:
        failures,warnings=len(FAILS),len(WARNS)
        details=None
        try:details=fn()
        except Exception as exc:fail(fn.__name__+': '+str(exc))
        checks.append({'name':fn.__name__,'status':'failed' if len(FAILS)>failures else 'warning' if len(WARNS)>warnings else 'passed',
                       'details':details})
    if args.release and WARNS:fail('发布检查要求所有必要检查执行且无跳过/警告')
    report={'mode':'release' if args.release else 'development','success':not FAILS,
            'game':find_game_folder(),'checks':checks,'failures':FAILS,'warnings':WARNS}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('='*60)
    for w in WARNS:print('[警告]',w)
    for f in FAILS:print('[失败]',f)
    print('='*60)
    print(('自检未通过' if FAILS else '自检通过')+'：%d 个失败，%d 个警告'%(len(FAILS),len(WARNS)))
    return 1 if FAILS else 0


if __name__=='__main__':sys.exit(main())
