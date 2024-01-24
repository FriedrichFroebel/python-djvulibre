import os
import subprocess

from tests.tools import EXAMPLES, IMAGES, TestCase


class DjvuDumpTextTestCase(TestCase):
    def test_djvu_dump_text(self):
        stdout = subprocess.check_output(
            [
                os.path.join(EXAMPLES, 'djvu-dump-text'),
                os.path.join(IMAGES, 'test0.djvu'),
            ]
        )
        with open(os.path.join(IMAGES, 'test0_dump-text.txt'), mode='rb') as fd:
            expected = fd.read()
        self.assertEqual(expected, stdout)
