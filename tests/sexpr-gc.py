# encoding=UTF-8

# Copyright © 2007-2015 Jakub Wilk <jwilk@jwilk.net>
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

if __name__ != '__main__':
    raise ImportError('This module is not intended for import')

import djvu.sexpr
import os

proc_status = f'/proc/{os.getpid()}/status'
scale = dict(kB=1024)


def mem_info(key='VmSize'):
    try:
        fd = open(proc_status)
        for line in fd.readlines():
            if line.startswith(f'{key}:'):
                _, value, unit = line.split(None, 3)
                return int(value) * scale[unit]
    finally:
        fd.close()


step = 1 << 17
while True:
    mb = mem_info() / (1 << 20)
    print(f'{mb:.2f}M')
    [djvu.sexpr.Expression(4) for i in range(step)]

# vim:ts=4 sts=4 sw=4 et
