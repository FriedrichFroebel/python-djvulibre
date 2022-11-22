# encoding=UTF-8

# Copyright © 2010-2021 Jakub Wilk <jwilk@jwilk.net>
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

import codecs
import contextlib
import locale
import os
import shutil
from io import StringIO
from unittest import SkipTest, TestCase as _TestCase


try:
    locale.LC_MESSAGES
except AttributeError:
    # A non-POSIX system.
    locale.LC_MESSAGES = locale.LC_ALL

locale_encoding = locale.getpreferredencoding()
if codecs.lookup(locale_encoding) == codecs.lookup('US-ASCII'):
    locale_encoding = 'UTF-8'


def get_changelog_version():
    here = os.path.dirname(__file__)
    path = os.path.join(here, '../doc/changelog')
    with open(path, encoding='UTF-8') as fd:
        line = fd.readline()
    return line.split()[1].strip('()')


class TestCase(_TestCase):
    SkipTest = SkipTest
    maxDiff = None

    @contextlib.contextmanager
    def assertRaisesString(self, exception_type, expected_string):  # noqa: N802
        with self.assertRaises(exception_type) as ecm:
            yield
        self.assertEqual(str(ecm.exception), expected_string)

    def assertRepr(self, obj, expected):  # noqa: N802
        self.assertEqual(repr(obj), expected)

    @classmethod
    def compare(cls, x, y):
        if x == y:
            return 0
        if x < y:
            return -1
        if x > y:
            return 1
        assert False


@contextlib.contextmanager
def interim(obj, **override):
    copy = {key: getattr(obj, key) for key in override}
    for key, value in override.items():
        setattr(obj, key, value)
    try:
        yield
    finally:
        for key, value in copy.items():
            setattr(obj, key, value)


@contextlib.contextmanager
def interim_locale(**kwargs):
    old_locale = locale.setlocale(locale.LC_ALL)
    try:
        for category, value in kwargs.items():
            category = getattr(locale, category)
            try:
                locale.setlocale(category, value)
            except locale.Error as exception:
                raise SkipTest(exception)
        yield
    finally:
        locale.setlocale(locale.LC_ALL, old_locale)


def skip_unless_c_messages():
    if locale.setlocale(locale.LC_MESSAGES) not in {'C', 'POSIX'}:
        raise SkipTest('you need to run this test with LC_MESSAGES=C')
    if os.getenv('LANGUAGE', '') != '':
        raise SkipTest('you need to run this test with LANGUAGE unset')


def skip_unless_translation_exists(lang):
    messages = {}
    langs = ['C', lang]
    for lang in langs:
        with interim_locale(LC_ALL=lang):
            try:
                open(__file__ + '/')
            except EnvironmentError as exc:
                messages[lang] = str(exc)
    messages = set(messages.values())
    assert 1 <= len(messages) <= 2, messages
    if len(messages) == 1:
        raise SkipTest('libc translation not found: ' + lang)


def skip_unless_command_exists(command):
    if shutil.which(command):
        return
    raise SkipTest('command not found: ' + command)


def wildcard_import(mod):
    namespace = {}
    exec(f'from {mod} import *', {}, namespace)
    return namespace


__all__ = [
    'StringIO',
    'SkipTest',
    'TestCase',
    # misc
    'get_changelog_version',
    'interim',
    'interim_locale',
    'locale_encoding',
    'skip_unless_c_messages',
    'skip_unless_command_exists',
    'skip_unless_translation_exists',
    'wildcard_import',
]

# vim:ts=4 sts=4 sw=4 et
