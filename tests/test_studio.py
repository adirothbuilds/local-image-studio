import base64
import fcntl
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext

from fastapi.testclient import TestClient
from PIL import Image
from studio.printing import export_print
from studio.lettering import generation_prompt, print_text
from studio.styled_text import styled_banner
from studio import server

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).resolve().parents[1] / 'scripts/cleanup.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)

class LetteringTests(unittest.TestCase):
    def test_model_message_keeps_hebrew_and_never_adds_overlay(self):
        settings = dict(prompt='איש שלג חוגג יום הולדת',text='יום הולדת שמח 3',text_mode='integrated',text_style='ice',text_position='top')
        prompt = generation_prompt(settings)
        self.assertIn(settings['prompt'], prompt)
        self.assertIn('"יום הולדת שמח 3"', prompt)
        self.assertIn('sculpted ice', prompt)
        self.assertEqual(print_text(settings), '')
        settings['text_mode'] = 'styled'
        # Regression: asking the model to reserve a blank panel created a white rectangle.
        self.assertEqual(generation_prompt(settings), settings['prompt'])
        self.assertEqual(print_text(settings), 'יום הולדת שמח 3')
        settings['text_mode'] = 'overlay'
        self.assertEqual(generation_prompt(settings), settings['prompt'])
        self.assertEqual(print_text(settings), 'יום הולדת שמח 3')

class StyledTextTests(unittest.TestCase):
    def test_font_size_and_outline_controls(self):
        from studio.styled_text import outline_width, font_points
        small=styled_banner('מזל טוב',1800,'ice',False,'#EFC5D5','handwritten',0,'',24)
        large=styled_banner('מזל טוב',1800,'ice',False,'#EFC5D5','handwritten',0,'',64)
        edged=styled_banner('מזל טוב',1800,'ice',False,'#EFC5D5','handwritten',8,'#FFFFFF',64)
        self.assertGreater(large.height,small.height)
        self.assertNotEqual(large.tobytes(),edged.tobytes())
        self.assertEqual(outline_width('0'),0)
        self.assertIsNone(outline_width(''))
        for value in (-1,13,'bad',float('nan'),True):
            with self.assertRaises(ValueError): outline_width(value)
        for value in (0,145,'bad',float('nan'),True):
            with self.assertRaises(ValueError): font_points(value)

    def test_hebrew_writing_fonts_are_distinct_and_validated(self):
        from studio.styled_text import FONT_CHOICES, lettering_font
        from fontTools.ttLib import TTFont
        text='יום הולדת שמח 3'
        samples=[styled_banner(text,1800,'ice',False,'#EFC5D5',choice) for choice in FONT_CHOICES]
        self.assertEqual(len({image.tobytes() for image in samples}),3)
        for choice in ('rounded','handwritten'):
            font=TTFont(FONT_CHOICES[choice])
            self.assertTrue(all(ord(ch) in font.getBestCmap() for ch in text))
            font.close()
        with self.assertRaises(ValueError): lettering_font('../../font.ttf')

    def test_custom_color_preserves_shape_and_transparency(self):
        from studio.styled_text import letter_color
        blue=styled_banner('יום הולדת שמח',1800,'ice',background=False)
        pink=styled_banner('יום הולדת שמח',1800,'ice',background=False,color='#e66ca6')
        self.assertEqual(blue.getchannel('A').tobytes(),pink.getchannel('A').tobytes())
        self.assertNotEqual(blue.tobytes(),pink.tobytes())
        self.assertEqual(letter_color('#e66ca6'),'#E66CA6')
        for invalid in ('pink','#123','url(test)',123,False):
            with self.assertRaises(ValueError): letter_color(invalid)

    def test_hebrew_banner_styles_and_deterministic_output(self):
        text='יום הולדת שמח 3'
        banners=[styled_banner(text,1800,style) for style in ('ice','ribbon','gold')]
        self.assertTrue(all(image.mode=='RGBA' and image.width==1800 for image in banners))
        self.assertEqual(banners[0].tobytes(),styled_banner(text,1800,'ice').tobytes())
        self.assertEqual(len({image.tobytes() for image in banners}),3)
        transparent=styled_banner(text,1800,'ice',background=False)
        self.assertEqual(transparent.getpixel((30,30))[3],0)
        self.assertGreater(banners[0].getpixel((30,banners[0].height//2))[3],0)
        self.assertTrue(transparent.getchannel('A').getbbox())
        self.assertNotEqual(banners[0].tobytes(),styled_banner('יום הולדת שמח 4',1800,'ice').tobytes())

class PrintingTests(unittest.TestCase):
    def test_twenty_centimeter_square_has_exact_physical_pdf_size(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            Image.new('RGB',(1024,1024),'blue').save(folder/'source.png')
            export_print(folder/'source.png',folder,'square20','יום הולדת שמח','top',0,text_mode='styled',text_background='none')
            with Image.open(folder/'a4.png') as image:
                self.assertEqual(image.size,(2362,2362))
                self.assertAlmostEqual(image.info['dpi'][0],300,delta=.1)
            pdf=(folder/'a4.pdf').read_bytes()
            box=re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)',pdf)
            self.assertIsNotNone(box)
            for value in box.groups():
                self.assertAlmostEqual(float(value),200/25.4*72,delta=.01)

    def test_a4_layout_and_pdf_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / 'source.png'
            Image.new('RGB', (512, 512), 'red').save(source)
            for orientation, pixels, points in [('portrait', (2480,3508), (595.28,841.89)), ('landscape', (3508,2480), (841.89,595.28))]:
                export_print(source, folder, orientation, 'Happy Birthday!', 'bottom', 5)
                with Image.open(folder/'a4.png') as page:
                    self.assertEqual(page.size, pixels)
                    self.assertAlmostEqual(page.info['dpi'][0], 300, delta=.1)
                    self.assertEqual(page.getpixel((0,0)), (255,255,255))
                    self.assertEqual(page.getpixel((pixels[0]//2,pixels[1]//2)), (255,0,0))
                pdf = (folder/'a4.pdf').read_bytes()
                box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', pdf)
                self.assertIsNotNone(box)
                for actual, expected in zip(map(float, box.groups()), points):
                    self.assertAlmostEqual(actual, expected, delta=.02)

class CleanupTests(unittest.TestCase):
    def test_preview_selective_delete_and_symlink_leaf(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            root = Path(temp)
            (root/'outputs').mkdir()
            (root/'outputs'/'keep.png').write_text('keep')
            (root/'models').mkdir()
            (root/'models'/'weights').write_text('weights')
            (root/'README.md').write_text('source')
            (root/'.cache').symlink_to(other, target_is_directory=True)
            (Path(other)/'keep').write_text('outside')
            cleanup.clean(root,'all')
            self.assertTrue((root/'models/weights').exists())
            cleanup.clean(root,'cache',True)
            self.assertTrue((Path(other)/'keep').exists())
            cleanup.clean(root,'models',True)
            self.assertTrue((root/'outputs/keep.png').exists())
            self.assertTrue((root/'README.md').exists())
    def test_full_cleanup_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in cleanup.GROUPS['all']:
                if name == '.env':
                    (root/name).write_text('STUDIO_PASSWORD=test')
                else:
                    (root/name).mkdir()
                    (root/name/'sample').write_text('data')
            (root/'WORK_LOG.md').write_text('source')
            cleanup.clean(root, 'all', True)
            self.assertTrue((root/'WORK_LOG.md').exists())
            self.assertFalse(any((root/name).exists() for name in cleanup.GROUPS['all']))

    def test_lock_and_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (root/'.operation.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                with self.assertRaises(RuntimeError): cleanup.clean(root,'all',True)
            (root/'.cache').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaises(RuntimeError): cleanup.clean(root,'models',True)

class ApiTests(unittest.TestCase):
    def test_phone_login_json_reports_errors_and_retains_session(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server,'LAN_PASSWORD','a-test-password-123456'), patch.object(server,'OUTPUTS',Path(temp)/'outputs'), patch.object(server,'operation_lock',nullcontext):
            with TestClient(server.app,base_url='http://127.0.0.1:7860') as client:
                headers={'accept':'application/json','origin':'null'}
                data={'username':'studio','password':'a-test-password-123456','csrf':server.TOKEN}
                wrong=client.post('/login',headers=headers,data={**data,'password':'wrong'})
                self.assertEqual(wrong.status_code,401)
                self.assertIn('incorrect',wrong.json()['detail'])
                expired=client.post('/login',headers=headers,data={**data,'csrf':'old-token'})
                self.assertEqual(expired.status_code,403)
                self.assertIn('expired',expired.json()['detail'])
                login=client.post('/login',headers=headers,data=data)
                self.assertEqual(login.status_code,200)
                self.assertEqual(login.json()['redirect'],'/')
                self.assertEqual(client.get('/api/status').status_code,200)

    def test_integrated_print_keeps_baked_letters_and_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root/'0e25dfc3-b329-432f-9816-39454fb0e1fe'
            folder.mkdir()
            Image.new('RGB',(128,128),'blue').save(folder/'original.png')
            (folder/'status.json').write_text('{"state":"complete"}')
            settings = dict(prompt='scene',seed=44,text='יום הולדת שמח 3',text_mode='integrated',text_style='ice',text_style_detail='',text_position='top')
            (folder/'settings.json').write_text(json.dumps(settings))
            with patch.object(server,'OUTPUTS',root), patch.object(server,'operation_lock',nullcontext), patch('studio.printing.export_print') as render:
                with TestClient(server.app,base_url='http://127.0.0.1:7860') as client:
                    headers={'x-studio-token':client.get('/api/status').json()['token']}
                    body={**settings,'orientation':'landscape','margin_mm':5}
                    response=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json=body)
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(render.call_args.args[3],'')
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={**body,'text':'different'}).status_code,409)
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={**body,'text_mode':'overlay'}).status_code,409)

    def test_form_login_session_and_csrf(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server,'LAN_PASSWORD','a-test-password-123456'), patch.object(server,'OUTPUTS',Path(temp)/'outputs'), patch.object(server,'operation_lock',nullcontext):
            with TestClient(server.app, base_url='http://127.0.0.1:7860') as client:
                page = client.get('/',headers={'accept':'text/html'})
                self.assertEqual(page.status_code,200)
                self.assertIn('Open studio',page.text)
                self.assertEqual(client.post('/login',headers={'origin':'null'},data={'username':'studio','password':'a-test-password-123456'}).status_code,403)
                self.assertEqual(client.post('/login',data={'csrf':server.TOKEN,'username':'studio','password':'wrong'}).status_code,401)
                response = client.post('/login',headers={'origin':'null'},data={'csrf':server.TOKEN,'username':'studio','password':'a-test-password-123456'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(client.get('/api/status').status_code,200)
                self.assertTrue(client.cookies.get('studio_session'))

    def test_lan_auth_covers_pages_api_and_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, 'LAN_PASSWORD', 'a-test-password-123456'), patch.object(server,'operation_lock',nullcontext), patch.object(server,'OUTPUTS',Path(temp)/'outputs'):
            with TestClient(server.app, base_url='http://127.0.0.1:7860') as client:
                for path in ('/', '/api/status', '/api/jobs', '/static/app.js', '/files/no/settings.json'):
                    self.assertEqual(client.get(path).status_code, 401)
                self.assertEqual(client.get('/api/status', auth=('studio','wrong')).status_code, 401)
                response = client.get('/api/status', auth=('studio','a-test-password-123456'))
                self.assertEqual(response.status_code, 200)
                self.assertIn('token', response.json())

    def test_update_print_preserves_art_and_records_message(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / '0e25dfc3-b329-432f-9816-39454fb0e1fe'
            folder.mkdir()
            Image.new('RGB', (128,128), 'blue').save(folder/'original.png')
            before = (folder/'original.png').read_bytes()
            (folder/'status.json').write_text('{"state":"complete"}')
            (folder/'settings.json').write_text('{"seed":42,"prompt":"test","text":""}')
            with patch.object(server,'OUTPUTS',root), patch.object(server,'operation_lock',nullcontext):
                with TestClient(server.app, base_url='http://127.0.0.1:7860') as client:
                    token = client.get('/api/status').json()['token']
                    headers = {'x-studio-token':token,'origin':'http://127.0.0.1:7860'}
                    response = client.post(f'/api/jobs/{folder.name}/print', headers=headers,
                                           json={'text':'יום הולדת שמח!', 'orientation':'portrait','text_position':'bottom','margin_mm':5})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(json.loads((folder/'settings.json').read_text())['text'], 'יום הולדת שמח!')
                    self.assertEqual((folder/'original.png').read_bytes(), before)
                    self.assertTrue((folder/'a4.pdf').exists())
                    styled=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'יום הולדת שמח 3','text_mode':'styled','text_style':'ice','text_position':'center'})
                    self.assertEqual(styled.status_code,200,styled.text)
                    saved=json.loads((folder/'settings.json').read_text())
                    self.assertEqual(saved['text_mode'],'styled')
                    self.assertEqual(saved['text'],'יום הולדת שמח 3')
                    no_panel=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'יום הולדת שמח 3','text_mode':'styled','text_style':'ice','text_background':'none'})
                    self.assertEqual(no_panel.status_code,200,no_panel.text)
                    self.assertEqual(json.loads((folder/'settings.json').read_text())['text_background'],'none')
                    pink=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'יום הולדת שמח','text_mode':'styled','text_style':'ice','text_background':'none','text_color':'#e66ca6'})
                    self.assertEqual(pink.status_code,200,pink.text)
                    self.assertEqual(json.loads((folder/'settings.json').read_text())['text_color'],'#E66CA6')
                    for font in ('rounded','handwritten'):
                        response=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'יום הולדת שמח','text_mode':'styled','text_font':font,'text_color':'#EFC5D5'})
                        self.assertEqual(response.status_code,200,response.text)
                        self.assertEqual(json.loads((folder/'settings.json').read_text())['text_font'],font)
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text_font':'missing-font'}).status_code,422)
                    response=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'מזל טוב','text_font':'handwritten','text_mode':'styled','text_font_size':40,'text_outline_width':1,'text_outline_color':'#ffffff'})
                    self.assertEqual(response.status_code,200,response.text)
                    saved=json.loads((folder/'settings.json').read_text())
                    self.assertEqual((saved['text_font_size'],saved['text_outline_width'],saved['text_outline_color']),(40,1,'#FFFFFF'))
                    for bad in ({'text_font_size':1000},{'text_outline_width':-1},{'text_outline_color':'white'}):
                        self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json=bad).status_code,422)
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text_color':'pink'}).status_code,422)
                    self.assertEqual((folder/'original.png').read_bytes(),before)
                    moved=client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'יום הולדת שמח 3','text_mode':'styled','text_style':'ice','text_background':'none','text_scale':.5,'text_x':.72,'text_y':.28})
                    self.assertEqual(moved.status_code,200,moved.text)
                    layout=client.get(f'/api/jobs/{folder.name}/layers').json()
                    self.assertTrue(layout['editable'])
                    self.assertAlmostEqual(layout['center_x'],.72,delta=.001)
                    self.assertAlmostEqual(layout['center_y'],.28,delta=.001)
                    self.assertEqual(client.get(f'/files/{folder.name}/lettering.png').status_code,200)
                    self.assertEqual(client.get(f'/files/{folder.name}/a4-base.png').status_code,200)
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text_scale':'nan'}).status_code,422)

                    self.assertEqual((folder/'original.png').read_bytes(), before)
                    self.assertEqual(client.post(f'/api/jobs/{folder.name}/print',headers=headers,json={'text':'x','margin_mm':-1}).status_code,422)

    def test_csrf_invalid_input_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = root/'model'
            model.mkdir()
            (model/'download.json').write_text('{"revision":"test"}')
            with patch.object(server,'OUTPUTS',root/'outputs'), patch.object(server,'MODEL',model), patch.object(server,'operation_lock',nullcontext):
                with TestClient(server.app, base_url='http://127.0.0.1:7860') as client:
                    info = client.get('/api/status').json()
                    headers = {'x-studio-token':info['token']}
                    self.assertEqual(client.post('/api/generate',data={'prompt':'test'}).status_code,403)
                    self.assertEqual(client.post('/api/generate',headers=headers,data={'prompt':'test','seed':'-1'}).status_code,422)
                    self.assertEqual(client.post('/api/generate',headers=headers,data={'prompt':'test','preset':'bad'}).status_code,422)
                    self.assertEqual(client.post('/api/generate',headers=headers,data={'prompt':'test'},files={'references':('bad.png',b'bad','image/png')}).status_code,422)
                    self.assertEqual(client.get('/files/not-a-uuid/settings.json').status_code,404)
                    self.assertEqual(client.post('/api/generate',headers={**headers,'origin':'https://example.com'},data={'prompt':'test'}).status_code,403)
                    self.assertEqual(client.get('/',headers={'host':'evil.example'}).status_code,400)

if __name__ == '__main__':
    unittest.main()
