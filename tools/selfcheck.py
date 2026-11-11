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

import glob
import os
import re
import sys
import struct
from zipfile import ZipFile, BadZipFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mod", "AgeOfMachines")

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
        warn("未安装 lupa，跳过 Lua 语法检查（pip install --target /tmp/pylua lupa）")
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
            build,symbols=build_symbols(archive.read("build.bin"))
            if build!="aom_tractor_cabin":
                raise ValueError("驾驶室 build 名称不匹配")
            bank=parse_anim(archive.read("anim.bin"))
            if not bank["animations"] or any(a["bank"]!=name_hash("aom_tractor_driver") for a in bank["animations"]):
                raise ValueError("驾驶动画 bank 名称不匹配")
            required={"mount","dismount","idle_loop","run_pre","run_loop","run_pst"}
            if not required.issubset({a["name"] for a in bank["animations"]}):
                raise ValueError("缺少原版骑乘所需动画")
            if not any(n.endswith(".tex") and archive.read(n)[:4]==b"KTEX" for n in archive.namelist()):
                raise ValueError("驾驶室图集缺失")
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
        src = open(path, encoding="utf-8").read()
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
        warn("缺少 lupa.lua51，跳过巨大化行为回归检查")
        return
    import io
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tools", "tests"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream).run(suite)
    if not result.wasSuccessful() or result.testsRun == 0:
        fail("行为回归失败：\n" + stream.getvalue())
    else:
        print("行为回归：%d 项通过（Lua 5.1）" % result.testsRun)


def main():
    check_syntax()
    check_modinfo()
    check_assets()
    check_animation_assets()
    check_driver_assets()
    check_music_assets()
    check_common_module()
    check_mod_environment()
    check_script_modules()
    check_cross_refs()
    check_local_functions_defined()
    check_bad_patterns()
    check_giant_farming()

    print("=" * 60)
    for w in WARNS:
        print("[警告]", w)
    for f in FAILS:
        print("[失败]", f)
    print("=" * 60)
    if FAILS:
        print("自检未通过：%d 个失败，%d 个警告" % (len(FAILS), len(WARNS)))
        return 1
    print("自检通过：0 个失败，%d 个警告" % len(WARNS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
