# Copyright © 2024 FriedrichFroebel
#
# This file is part of python-djvulibre.
#
# python-djvulibre is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# python-djvulibre is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.

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
