"""依赖/跳过/原版路径和发布阻断；不触碰真实安装包。"""
from contextlib import ExitStack,redirect_stdout
import io
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import selfcheck
import package_mod
from optimize_driver_assets import optimize,DRIVERS

class ReleaseCheckTests(unittest.TestCase):
    def test_missing_lua_dependency_fails_instead_of_passing_without_tests(self):
        selfcheck.FAILS.clear();selfcheck.WARNS.clear()
        with mock.patch.dict(sys.modules,{'lupa.lua51':None}):
            selfcheck.check_syntax();selfcheck.check_giant_farming()
        self.assertEqual(len(selfcheck.FAILS),2)
        self.assertFalse(selfcheck.WARNS)

    def test_macos_app_bundle_is_found_without_environment_override(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);game=home/"Library/Application Support/Steam/steamapps/common/Don't Starve Together/dontstarve_steam.app/Contents"
            (game/'data/databundles').mkdir(parents=True)
            with mock.patch.object(selfcheck.Path,'home',return_value=home),mock.patch.dict('os.environ',{'DST_GAME':''}):
                self.assertEqual(selfcheck.find_game_folder(),str(game))

    def test_release_rejects_skipped_check_and_writes_explicit_failure_report(self):
        import json
        names=[n for n in vars(selfcheck) if n.startswith('check_')]
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            for n in names:
                patched=stack.enter_context(mock.patch.object(selfcheck,n,return_value=None));patched.__name__=n
            patched=stack.enter_context(mock.patch.object(selfcheck,'check_syntax',side_effect=lambda:selfcheck.warn('skipped native check')));patched.__name__='check_syntax'
            report=Path(temp)/'report.json'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(selfcheck.main(['--release','--report',str(report)]),1)
            data=json.loads(report.read_text());self.assertFalse(data['success'])
            self.assertEqual(data['checks'][0]['status'],'warning')

    def test_failed_release_check_never_replaces_existing_package(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'Tractor.zip';archive.write_bytes(b'previous package')
            with mock.patch.object(package_mod,'ARCHIVE',archive),mock.patch.object(sys,'argv',['package_mod.py']),\
                 mock.patch.object(package_mod.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'check')) as run,\
                 mock.patch.object(package_mod,'build_archive') as build:
                with self.assertRaises(subprocess.CalledProcessError):package_mod.main()
                self.assertIn('--release',run.call_args.args[0]);build.assert_not_called()
            self.assertEqual(archive.read_bytes(),b'previous package')

class SharedAssetTests(unittest.TestCase):
    def fixture(self,folder):
        common={'build.bin':b'BILD shared','atlas-0.tex':b'KTEX shared'}
        with ZipFile(folder/'aom_tractor_cabin.zip','w') as z:
            for n,raw in common.items():z.writestr(n,raw)
        for name in DRIVERS:
            with ZipFile(folder/(name+'.zip'),'w') as z:
                for n,raw in common.items():z.writestr(n,raw)
                z.writestr('anim.bin',('ANIM '+name).encode())

    def test_dedup_preserves_all_animation_bytes_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.fixture(folder)
            result=optimize(folder);before={}
            for name in DRIVERS:
                with ZipFile(folder/(name+'.zip')) as z:
                    self.assertEqual(z.namelist(),['anim.bin'])
                    self.assertEqual(z.read('anim.bin'),('ANIM '+name).encode())
                before[name]=(folder/(name+'.zip')).read_bytes()
            optimize(folder)
            self.assertEqual(before,{n:(folder/(n+'.zip')).read_bytes() for n in DRIVERS})
            self.assertGreater(result['saved_bytes'],0)

    def test_mismatched_build_is_rejected_before_any_output_is_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.fixture(folder)
            bad=folder/(DRIVERS[-1]+'.zip')
            with ZipFile(bad,'w') as z:z.writestr('build.bin',b'other');z.writestr('anim.bin',b'ANIM')
            before={n:(folder/(n+'.zip')).read_bytes() for n in DRIVERS}
            with self.assertRaises(ValueError):optimize(folder)
            self.assertEqual(before,{n:(folder/(n+'.zip')).read_bytes() for n in DRIVERS})

if __name__=='__main__':unittest.main()
