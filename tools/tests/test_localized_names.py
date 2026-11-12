"""核对实际 prefab、制作说明、旧 ID 及自动/手动语言选择的显示名称。"""
from pathlib import Path
import unittest
from lupa.lua51 import LuaRuntime

MOD = Path(__file__).resolve().parents[2] / 'mod/Tractor'
PREFABS = ('aom_tractor_chassis', 'aom_tractor_item', 'aom_landclearer',
           'aom_plow', 'aom_seeder', 'aom_irrigator', 'aom_fertilizer',
           'aom_weeder', 'aom_harvester')
EXPECTED = {
    'zh': ('拖拉机', '拖拉机', '开垦机', '开垦机', '播种机', '洒水机', '施肥机', '除草机', '收割机'),
    'en': ('Tractor', 'Tractor', 'Land Clearer', 'Land Clearer', 'Seeder',
           'Irrigator', 'Fertilizer Spreader', 'Weeder', 'Harvester'),
}


class LocalizedNameTests(unittest.TestCase):
    def test_required_module_does_not_need_mod_environment_global_alias(self):
        lua=LuaRuntime()
        lua.globals().SCRIPTS=str(MOD/'scripts')
        lua.execute('''
GLOBAL=nil;GetModConfigData=nil;STRINGS={NAMES={},RECIPE_DESC={}}
package.path=SCRIPTS..'/?.lua;'..package.path
local aom=require('aom_common')
assert(GLOBAL==nil and AOM_ATTACHMENT_TYPE.SEEDER=='seeder')
assert(STRINGS.NAMES.AOM_SEEDER=='播种机')
aom.SetLanguage('en');assert(STRINGS.NAMES.AOM_SEEDER=='Seeder')
''')

    def load(self, config, locale):
        lua = LuaRuntime()
        lua.globals().LOCALE = locale
        # modmain 把 GetModConfigData 的结果放进 GLOBAL.AOM_CONFIG 后再 require aom_common。
        lua.globals().AOM_CONFIG = lua.table(LANGUAGE=config) if config is not None else lua.table()
        lua.execute('''
GLOBAL={LOC={GetLocaleCode=function() return LOCALE end}}
STRINGS={NAMES={},RECIPE_DESC={}}
''')
        lua.execute((MOD / 'scripts/aom_common.lua').read_text())
        return lua

    def assert_names(self, lua, lang):
        for prefab, expected in zip(PREFABS, EXPECTED[lang]):
            with self.subTest(prefab=prefab, language=lang):
                self.assertEqual(lua.globals().STRINGS.NAMES[prefab.upper()], expected)
        self.assertEqual(lua.globals().STRINGS.RECIPE_DESC.AOM_TRACTOR_CHASSIS,
                         lua.globals().STRINGS.RECIPE_DESC.TRACTOR_CHASSIS)

    def test_explicit_chinese_overrides_english_game(self):
        self.assert_names(self.load('zh', 'en'), 'zh')

    def test_explicit_english_overrides_chinese_game(self):
        self.assert_names(self.load('en', 'zh'), 'en')

    def test_auto_follows_game_language(self):
        for locale, lang in (('zh', 'zh'), ('zhr', 'zh'), ('zht', 'zh'),
                             ('en', 'en'), ('', 'en'), ('fr', 'en')):
            with self.subTest(locale=locale):
                self.assert_names(self.load('auto', locale), lang)

    def test_missing_configuration_and_locale_are_safe(self):
        self.assert_names(self.load(None, 'en'), 'en')
        lua = self.load(None, None)
        lua.execute('GLOBAL.LOC=nil')
        lua.execute((MOD / 'scripts/aom_common.lua').read_text())
        self.assert_names(lua, 'zh')

    def test_mod_list_name_and_default_language(self):
        for locale, expected in ((None, 'tractor'), ('zh', 'tractor'),
                                 ('zhr', 'tractor'), ('zht', 'tractor'),
                                 ('en', 'tractor'), ('', 'tractor')):
            with self.subTest(locale=locale):
                lua = LuaRuntime()
                lua.globals().locale = locale
                lua.execute((MOD / 'modinfo.lua').read_text())
                self.assertEqual(lua.globals().name, expected)
                language = next(option for option in lua.globals().configuration_options.values()
                                if option.name == 'LANGUAGE')
                self.assertEqual(language.default, 'auto')
                self.assertEqual({option.data for option in language.options.values()},
                                 {'auto', 'zh', 'en'})
