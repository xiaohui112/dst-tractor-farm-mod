"""安装包清单、源码一致性与篡改检测，避免再次交付旧脚本。"""
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_mod import build_archive,verify_archive


class InstallPackageTests(unittest.TestCase):
    def test_archive_includes_new_module_and_detects_stale_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'mod';(source/'scripts').mkdir(parents=True)
            (source/'modinfo.lua').write_text('version="test"')
            tool=source/'scripts/aom_harvester_tool.lua';tool.write_text('return {MAX_USES=40}')
            (source/'.DS_Store').write_text('excluded')
            archive=root/'mod.zip';build_archive(source,archive)
            self.assertEqual(len(verify_archive(source,archive)['files']),2)
            with ZipFile(archive) as z:
                self.assertIn('Tractor/scripts/aom_harvester_tool.lua',z.namelist())
                self.assertFalse(any('.DS_Store' in name for name in z.namelist()))
            tool.write_text('return {MAX_USES=99}')
            with self.assertRaises(ValueError):verify_archive(source,archive)

    def test_archive_build_is_reproducible_and_rejects_extra_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'mod';source.mkdir()
            (source/'modinfo.lua').write_text('version="test"')
            a=root/'a.zip';b=root/'b.zip';build_archive(source,a);build_archive(source,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            with ZipFile(a,'a') as z:z.writestr('Tractor/stale.lua','old')
            with self.assertRaises(ValueError):verify_archive(source,a)


if __name__=='__main__':unittest.main()
