import json
import tempfile
import unittest
from pathlib import Path
from ui.colab_runner import parse_folder_id, run_research
from tests.test_smoke import Client

class Tests(unittest.TestCase):
    def test_folder_url_and_id(self):
        folder_id='test_folder_12345'
        self.assertEqual(parse_folder_id(folder_id),folder_id)
        self.assertEqual(parse_folder_id('https://drive.google.com/drive/folders/'+folder_id+'?usp=drive_link'),folder_id)
        with self.assertRaises(ValueError):parse_folder_id('https://other.test/drive/folders/'+folder_id)
        with self.assertRaises(ValueError):parse_folder_id('')

    def test_other_manufacturer_local_save_and_report(self):
        client=Client([{'products':[{'asin':'A','eanList':['12345678'],'stats':{'current':[-1,1980]}}]}])
        with tempfile.TemporaryDirectory() as directory:
            path,diagnostic,report=run_research([{'jan':'12345678','manufacturer':'別メーカー'}],
                'private_key','別メーカー',output_dir=directory,client_factory=lambda _:client)
            self.assertTrue(path.name.startswith('別メーカー_'))
            self.assertTrue(path.is_file())
            self.assertEqual(report['matched_source_products'],1)
            self.assertNotIn('private_key',diagnostic.read_text())
            self.assertEqual(report['drive_status'],'NOT_UPLOADED')

    def test_invalid_settings_before_client(self):
        def forbidden(_):raise AssertionError('client must not be created')
        with self.assertRaises(ValueError):run_research([{'jan':'12345678'}],'k','GEX',bb_limit=-1,client_factory=forbidden)
        with self.assertRaises(ValueError):run_research([],'k','GEX',client_factory=forbidden)
