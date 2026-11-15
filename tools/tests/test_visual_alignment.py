"""验证实际编译bank中的人物方向、后挂件正面遮挡及资源报告一致性。"""
import hashlib
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

from driver_animation import name_hash, parse_anim
from build_directional_art import stable_driver

ROOT = Path(__file__).resolve().parents[2]
ANIM = ROOT / 'mod/Tractor/anim'


def animations(name):
    with ZipFile(ANIM / (name + '.zip')) as archive:
        return parse_anim(archive.read('anim.bin'))['animations']


class VisualAlignmentTests(unittest.TestCase):
    def test_stationary_and_driving_pose_faces_side_and_back_in_every_model_size(self):
        for suffix, scale in [('_075', 1.875), ('', 2.5), ('_125', 3.125), ('_150', 3.75)]:
            bank = animations('aom_tractor_driver' + suffix)
            checked = set()
            for a in bank:
                if not stable_driver(a['name']):
                    continue
                checked.add(a['name'])
                for frame in a['frames']:
                    head = next(e for e in frame['elements'] if e['symbol'] == name_hash('headbase'))
                    faces = [e['frame'] for e in frame['elements'] if e['symbol'] == name_hash('face')]
                    with self.subTest(size=scale, state=a['name'], facing=a['facing']):
                        if a['facing'] in (2, 48):
                            self.assertEqual(head['frame'], 2)
                            self.assertLess(head['matrix'][0], 0)
                            self.assertEqual(faces, [])
                        elif a['facing'] == 5:
                            self.assertEqual(head['frame'], 1)
                            self.assertEqual(faces, [4])  # 真正的侧脸，不用骑牛正脸或惊恐表情12。
                        else:
                            self.assertEqual(faces, [0])
                        self.assertAlmostEqual(abs(head['matrix'][0]) * scale, 1, places=4)
                        self.assertAlmostEqual(head['matrix'][1], 0, places=4)
            self.assertTrue({'idle_loop', 'run_loop', 'dial_loop', 'dialog_loop', 'idle_walk', 'alert_idle'} <= checked)

    def test_rear_implements_are_occluded_frontally_only_while_mounted_in_all_work_states(self):
        bank = animations('aom_attachment_shared')
        for kind in ['weeder', 'plow', 'seeder', 'irrigator', 'fertilizer']:
            for state in ['', '_work_pre', '_work_loop', '_work_pst']:
                variants = [a for a in bank if a['name'] == kind + state]
                self.assertEqual(len(variants), 10)
                for a in variants:
                    hidden = a['bank'] == name_hash('aom_attachment_mounted') and a['facing'] == 8
                    for frame in a['frames']:
                        self.assertEqual(bool(frame['elements']), not hidden, (kind, state, a['facing']))

    def test_harvester_remains_visible_in_all_five_views_and_work_states(self):
        bank = animations('aom_attachment_shared')
        for state in ['', '_work_pre', '_work_loop', '_work_pst']:
            variants = [a for a in bank if a['name'] == 'harvester' + state]
            self.assertEqual(len(variants), 10)
            for a in variants:
                self.assertTrue(all(frame['elements'] for frame in a['frames']))

    def test_mounted_water_and_fertilizer_cannot_leak_through_front_of_tractor(self):
        for package, base, name in [('aom_attachment_water', 'aom_attachment_water', 'spray'),
                                    ('aom_attachment_fx', 'aom_attachment_fx', 'fertilizer')]:
            variants = [a for a in animations(package) if a['name'] == name]
            self.assertEqual(len(variants), 10)
            for a in variants:
                hidden = a['bank'] == name_hash(base + '_mounted') and a['facing'] == 8
                self.assertTrue(all(bool(frame['elements']) != hidden for frame in a['frames']))

    def test_all_rebuilt_archives_match_both_build_reports(self):
        for path in ['Driver-Build-Report.json', 'Attachment-Build-Report.json']:
            report = json.loads((ROOT / 'mod/Tractor' / path).read_text())
            for name, digest in report['sha256'].items():
                self.assertEqual(hashlib.sha256((ANIM / (name + '.zip')).read_bytes()).hexdigest(), digest)
        report = json.loads((ROOT / 'mod/Tractor/Driver-Build-Report.json').read_text())
        self.assertEqual(report['driver_facing'], 'directional_side_pose_and_rear_pose_with_upright_head')
        self.assertFalse(report['game_validation'])


if __name__ == '__main__':
    unittest.main()
