"""Portable checks with synthetic fixtures; does not start Blender or Unreal."""
import ast,csv,json,math,sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode=True
from panorama_sun import sun_direction,panorama_uv
from prepare_collections import prepare
from verify_catalogue import verify,contained_file
from summarize_csv import summarize

ROOT=Path(__file__).resolve().parents[1]
class MuseumSkillChecks(unittest.TestCase):
    def test_projection_direction_and_roundtrip(self):
        basis=[[100,0,0],[0,-100,0],[0,0,100]]
        self.assertAlmostEqual(sun_direction(basis,[.75,.5],0)[1],-1)
        for yaw in (-140,-35,0,35,180):
            for u,v in ((.01,.1),(.2,.4),(.5,.5),(.9,.8)):
                direction=sun_direction(basis,[u,v],yaw)
                uv=panorama_uv(direction,basis,yaw)
                self.assertAlmostEqual(uv[0],u,places=8);self.assertAlmostEqual(uv[1],v,places=8)
        with self.assertRaises(ValueError): sun_direction([[1,0,0],[0,1,0],[0,0,1]],[.2,.4],0)
        with self.assertRaises(ValueError): sun_direction(basis,[float('nan'),.4],0)

    def test_approved_copy_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);source=base/'source';source.mkdir()
            # JPEG header fixture; full decoding is explicitly outside these checks.
            (source/'one.jpg').write_bytes(b'\xff\xd8\xff\xe0synthetic-header-fixture')
            manifest=base/'approved.json'
            manifest.write_text(json.dumps({'albums':[{'id':'demo','title':'Demo','folder':'private-metadata',
                'photos':[{'id':'photo_01','name':'One','hires_file':'one.jpg','source_path':'private-metadata'}]}]}),encoding='utf-8')
            output=base/'Collections';report=prepare(manifest,source,output)
            self.assertEqual(report['unique_jpegs'],1)
            self.assertEqual((output/'Photos'/'photo_01.jpg').read_bytes(),(source/'one.jpg').read_bytes())
            self.assertNotIn('private-metadata',(output/'catalogue.json').read_text())
            self.assertEqual(verify(output)['albums'],1)
            for name in ('../one.jpg','C:/one.jpg','..\\one.jpg','/one.jpg'):
                with self.assertRaises(ValueError): contained_file(source,name)
            with self.assertRaises(ValueError): prepare(manifest,source,output)

    def test_actual_csv_retains_stalls(self):
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/'fixture.csv'
            file.write_text('EVENTS,FrameTime,GPUTime,GameThreadTime,GPUMem/LocalUsedMB\n,16,5,2,100\n,100,6,90,101\n[Metadata],ignored,,,\n',encoding='utf-8')
            report=summarize(file)
            self.assertEqual(report['frames_above_50ms'],1)
            self.assertEqual(report['captured_frames'],2)
            self.assertEqual(report['frames_above_16_667ms'],1)
            self.assertAlmostEqual(report['average_fps'],1000/58)
            self.assertEqual(report['counters']['FrameTime']['p95'],100)
            self.assertEqual(report['counters']['FrameTime']['max'],100)
            self.assertEqual(report['counters']['GPUTime']['mean'],5.5)

    def test_python_sources_and_template_projection_match(self):
        for file in ROOT.rglob('*.py'): ast.parse(file.read_text(encoding='utf-8'),filename=str(file.relative_to(ROOT)))
        self.assertEqual((ROOT/'scripts'/'panorama_sun.py').read_bytes(),
            (ROOT/'assets'/'unreal-runtime-template'/'Tools'/'panorama_projection.py').read_bytes())
        settings=json.loads((ROOT/'assets'/'scene_settings.example.json').read_text())
        direction=sun_direction([[100,0,0],[0,-100,0],[0,0,100]],settings['sun_uv'],settings['panorama_lookup_yaw_degrees'])
        self.assertGreater(direction[2],0)

if __name__=='__main__': unittest.main(verbosity=2)
