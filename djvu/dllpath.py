# encoding=UTF-8

# Copyright © 2011-2017 Jakub Wilk <jwilk@jwilk.net>
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

"""
Ease finding DjVuLibre DLLs in non-standard locations.
"""

import ctypes
import os

if os.name != 'nt':
    raise ImportError('This module is for Windows only')

import winreg


def _get(key, subkey):
    with winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE) as registry:
        with winreg.OpenKey(registry, key) as regkey:
            value, tp = winreg.QueryValueEx(regkey, subkey)
            del tp
            if not isinstance(value, str):
                raise TypeError
            return value


_DJVULIBRE_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\DjVuLibre+DjView'


def guess_dll_path():
    try:
        path = _get(_DJVULIBRE_KEY, 'UninstallString')
    except (TypeError, WindowsError):
        return
    path = os.path.dirname(path)
    if os.path.isfile(os.path.join(path, 'libdjvulibre.dll')):
        return path


def _guess_dll_version():
    try:
        version = _get(_DJVULIBRE_KEY, 'DisplayVersion')
    except (TypeError, WindowsError):
        return
    return version.split('+')[0]


def set_dll_search_path(path=None):
    if path is None:
        path = guess_dll_path()
    if path is None:
        return
    if not isinstance(path, str):
        raise TypeError
    ctypes.windll.kernel32.SetDllDirectoryW(path)
    return path


__all__ = [
    'guess_dll_path',
    'set_dll_search_path'
]

# vim:ts=4 sts=4 sw=4 et
