"""核对实际原版 UI 资源，防止控件方法正确但贴图/动画引用不存在。"""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import os
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=json.loads((ROOT/'tools/api-ref/native_ui_contract.json').read_text())


class DashboardAssetTests(unittest.TestCase):
    def test_widget_reference_files_match_recorded_native_sources(self):
        for name,digest in CONTRACT['widget_sources'].items():
            self.assertEqual(hashlib.sha256((ROOT/'tools/api-ref'/('widget_'+name+'.lua')).read_bytes()).hexdigest(),digest,name)
        for name,entry in CONTRACT['widget_methods'].items():
            source=(ROOT/'tools/api-ref'/entry['reference']).read_text()
            method=re.search(r'function Widget:'+name+r'\(\)\n.*?\nend',source,re.S).group()
            self.assertEqual(hashlib.sha256(method.encode()).hexdigest(),entry['sha256'],name)
        main=(ROOT/'mod/Tractor/scripts/widgets/aom_hud.lua').read_text()
        badge=(ROOT/'mod/Tractor/scripts/widgets/aom_badge.lua').read_text()
        for atlas,texture in re.findall(r'Image\("([^"]+)","([^"]+)"\)',main+badge):
            self.assertIn(texture,CONTRACT['native_atlases'][atlas])
        self.assertIn('widgets/badge',badge)
        self.assertIn('widgets/imagebutton',badge)

    def test_all_ui_textures_and_animation_banks_exist_in_installed_game(self):
        game=Path(os.environ.get('DST_GAME',str(Path.home()/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents")))
        images=game/'data/databundles/images.zip'
        if not images.is_file():self.skipTest('Native game assets not installed')
        with ZipFile(images) as archive:
            for atlas,textures in CONTRACT['native_atlases'].items():
                actual=set(re.findall(r'name="([^"]+)"',archive.read(atlas).decode()))
                self.assertTrue(set(textures)<=actual,atlas)
        for name in CONTRACT['native_animations']:
            with ZipFile(game/'data/anim'/name) as archive:
                self.assertIn('build.bin',archive.namelist())
                self.assertIn('anim.bin',archive.namelist())
        with ZipFile(game/'data/databundles/scripts.zip') as archive:
            for name,digest in CONTRACT['widget_sources'].items():
                self.assertEqual(hashlib.sha256(archive.read('scripts/widgets/'+name+'.lua')).hexdigest(),digest,name)
            for name,entry in CONTRACT['widget_methods'].items():
                source=archive.read(entry['source']).decode()
                method=re.search(r'function Widget:'+name+r'\(\)\n.*?\nend',source,re.S).group()
                self.assertEqual(hashlib.sha256(method.encode()).hexdigest(),entry['sha256'],name)
