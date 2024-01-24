import os
import subprocess

from tests.tools import EXAMPLES, IMAGES, TestCase


class DjvuCropTextTestCase(TestCase):
    def test_djvu_dump_text(self):
        stdout = subprocess.check_output(
            [
                os.path.join(EXAMPLES, 'djvu-crop-text'),
                os.path.join(IMAGES, 'test0.djvu'),
            ],
            stderr=subprocess.PIPE,
        )
        with open(os.path.join(IMAGES, 'test0_crop-text.txt'), mode='rb') as fd:
            expected = fd.read()
        self.assertEqual(expected, stdout)
