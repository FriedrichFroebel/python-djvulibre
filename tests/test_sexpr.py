# encoding=UTF-8

# Copyright © 2007-2021 Jakub Wilk <jwilk@jwilk.net>
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
import copy
import errno
import io
import os
import pickle
import shutil
import sys
import tempfile
from collections import abc

from djvu.sexpr import (
    Expression,
    ExpressionSyntaxError,
    Symbol,
    _ExpressionIO,
    __version__,
)

from tools import TestCase, get_changelog_version, wildcard_import


class SexprTestCase(TestCase):
    def assertPickleEqual(self, obj):
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            pickled_obj = pickle.dumps(obj, protocol=protocol)
            repickled_obj = pickle.loads(pickled_obj)
            self.assertEqual(obj, repickled_obj)

class IntExpressionsTestCase(SexprTestCase):

    def check(self, n, x=None):
        if x is None:
            x = Expression(n)
        self.assertIs(x, Expression(x))
        # __repr__():
        self.assertRepr(x, 'Expression({n})'.format(n=int(n)))
        # value:
        v = x.value
        self.assertEqual(type(v), int)
        self.assertEqual(v, n)
        # lvalue:
        v = x.lvalue
        self.assertEqual(type(v), int)
        self.assertEqual(v, n)
        # __int__():
        i = int(x)
        self.assertEqual(type(i), int)
        self.assertEqual(i, n)
        # __long__():
        i = long(x)
        self.assertEqual(type(i), long)
        self.assertEqual(i, n)
        # __float__():
        i = float(x)
        self.assertEqual(type(i), float)
        self.assertEqual(i, n)
        # __str__():
        s = str(x)
        self.assertEqual(s, str(n))
        # __eq__(), __ne__():
        self.assertEqual(x, Expression(n))
        self.assertNotEqual(x, n)
        self.assertNotEqual(x, Expression(n + 37))
        # __hash__():
        self.assertEqual(hash(x), n)
        # __bool__() / __nonzero__():
        obj = object()
        if n:
            self.assertIs(x and obj, obj)
            self.assertIs(x or obj, x)
        else:
            self.assertIs(x and obj, x)
            self.assertIs(x or obj, obj)
        # pickle:
        self.assertPickleEqual(x)

    def test_int(self):
        self.check(42)

    def test_parse(self):
        self.check(42, Expression.from_string('42'))

    def test_unpickle(self):
        # pickle as generated by python-djvulibre 0.3.3:
        p = b"cdjvu.sexpr\n_expression_from_string\np0\n(S'42'\np1\ntp2\nRp3\n."
        x = pickle.loads(p)
        self.check(42, x)

    def test_0(self):
        self.check(0)

    def test_limits(self):
        self.assertEqual(Expression((1 << 29) - 1).value, (1 << 29) - 1)
        self.assertEqual(Expression(-1 << 29).value, -1 << 29)
        with self.assertRaisesString(ValueError, 'value not in range(-2 ** 29, 2 ** 29)'):
            Expression(1 << 29)
        with self.assertRaisesString(ValueError, 'value not in range(-2 ** 29, 2 ** 29)'):
            Expression((-1 << 29) - 1)

class FloatExpressionsTestCase(SexprTestCase):

    # TODO: float expressions are not implemented yet

    def test_parse(self):
        with self.assertRaises(ExpressionSyntaxError):
            x = Expression.from_string('3.14')
            if isinstance(x.value, Symbol):
                raise ExpressionSyntaxError

class SymbolsTestCase(SexprTestCase):

    def check(self, name, sname=None):
        if sname is None:
            sname = name
        [uname, bname] = [sname, sname.encode('UTF-8')]
        symbol = Symbol(name)
        self.assertEqual(type(symbol), Symbol)
        self.assertEqual(symbol, Symbol(name))
        self.assertIs(symbol, Symbol(name))
        self.assertEqual(str(symbol), sname)
        self.assertEqual(unicode(symbol), uname)
        self.assertNotEqual(symbol, bname)
        self.assertNotEqual(symbol, uname)
        self.assertEqual(hash(symbol), hash(bname))
        self.assertPickleEqual(symbol)
        return symbol

    def test_ascii(self):
        self.check('eggs')

    def test_nonascii(self):
        x = self.check('ветчина'.encode('UTF-8'), 'ветчина')
        y = self.check('ветчина', 'ветчина')
        self.assertIs(x, y)

    def test_inequality(self):
        self.assertLess(
            Symbol('eggs'),
            Symbol('ham'),
        )

class SymbolExpressionsTestCase(SexprTestCase):

    def check(self, name, sname):
        if sname is None:
            sname = name
        [uname, bname] = [sname, sname.encode('UTF-8')]
        sym = Symbol(name)
        x = Expression(sym)
        self.assertIs(x, Expression(x))
        # __repr__(x)
        self.assertRepr(x, 'Expression({sym!r})'.format(sym=sym))
        # value:
        v = x.value
        self.assertEqual(type(v), Symbol)
        self.assertEqual(v, sym)
        # lvalue:
        v = x.lvalue
        self.assertEqual(type(v), Symbol)
        self.assertEqual(v, sym)
        # __str__():
        self.assertEqual(str(x), sname)
        self.assertRepr(x, repr(Expression.from_string(sname)))
        # __unicode__():
        self.assertEqual(unicode(x), uname)
        self.assertRepr(x, repr(Expression.from_string(uname)))
        # __eq__(), __ne__():
        self.assertEqual(x, Expression(sym))
        self.assertNotEqual(x, Expression(name))
        self.assertNotEqual(x, sym)
        # __hash__():
        self.assertEqual(
            hash(x),
            hash(bname.strip(b'|'))
        )
        # pickle:
        self.assertPickleEqual(x)
        return x

    def test_ascii(self):
        self.check('eggs', 'eggs')

    def test_nonascii(self):
        x = self.check('ветчина'.encode('UTF-8'), '|ветчина|')
        y = self.check('ветчина', '|ветчина|')
        self.assertEqual(x, y)
        self.assertEqual(hash(x), hash(y))


class StringExpressionsTestCase(SexprTestCase):
    def test_string_expressions(self):
        x = Expression('eggs')
        self.assertRepr(x, "Expression('eggs')")
        self.assertIs(x, Expression(x))
        self.assertEqual(x.value, 'eggs')
        self.assertEqual(x.lvalue, 'eggs')
        self.assertEqual(str(x), '"eggs"')
        self.assertRepr(x, repr(Expression.from_string(str(x))))
        self.assertEqual(x, Expression('eggs'))
        self.assertNotEqual(x, Expression(Symbol('eggs')))
        self.assertNotEqual(x, 'eggs')
        self.assertEqual(hash(x), hash('eggs'))
        self.assertPickleEqual(x)

class UnicodeExpressionsTestCase(SexprTestCase):

    def test1(self):
        x = Expression('eggs')
        self.assertRepr(x, "Expression('eggs')")
        self.assertIs(x, Expression(x))

    def test2(self):
        x = Expression('żółw')
        self.assertRepr(x, "Expression('żółw')")

class ListExpressionsTestCase(SexprTestCase):

    def test1(self):
        x = Expression(())
        self.assertRepr(x, "Expression([])")
        y = Expression(x)
        self.assertIs(x, y)
        self.assertEqual(x.value, ())
        self.assertEqual(x.lvalue, [])
        self.assertEqual(len(x), 0)
        self.assertEqual(bool(x), False)
        self.assertEqual(list(x), [])

    def test2(self):
        x = Expression([[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])
        self.assertRepr(x, "Expression([[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])")
        y = Expression(x)
        self.assertRepr(y, repr(x))
        assert_false(x is y)
        self.assertEqual(x.value, ((1, 2), 3, (4, 5, Symbol('baz')), ('quux',)))
        self.assertEqual(x.lvalue, [[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])
        self.assertEqual(str(x), '((1 2) 3 (4 5 baz) ("quux"))')
        self.assertRepr(x, repr(Expression.from_string(str(x))))
        self.assertEqual(len(x), 4)
        self.assertEqual(bool(x), True)
        self.assertEqual(tuple(x), (Expression((1, 2)), Expression(3), Expression((4, 5, Symbol('baz'))), Expression(('quux',))))
        with self.assertRaisesString(TypeError, 'key must be an integer or a slice'):
            x[object()]
        self.assertEqual(x[1], Expression(3))
        self.assertEqual(x[-1][0], Expression('quux'))
        with self.assertRaisesString(IndexError, 'list index of out range'):
            x[6]
        with self.assertRaisesString(IndexError, 'list index of out range'):
            x[-6]
        self.assertEqual(x[:].value, x.value)
        self.assertEqual(x[:].lvalue, x.lvalue)
        self.assertRepr(x[1:], "Expression([3, [4, 5, Symbol('baz')], ['quux']])")
        self.assertRepr(x[-2:], "Expression([[4, 5, Symbol('baz')], ['quux']])")
        x[-2:] = 4, 5, 6
        self.assertRepr(x, 'Expression([[1, 2], 3, 4, 5, 6])')
        x[0] = 2
        self.assertRepr(x, 'Expression([2, 3, 4, 5, 6])')
        x[:] = (1, 3, 5)
        self.assertRepr(x, 'Expression([1, 3, 5])')
        x[3:] = 7,
        self.assertRepr(x, 'Expression([1, 3, 5, 7])')
        with self.assertRaisesString(NotImplementedError, 'only [n:] slices are supported'):
            x[object():]
        with self.assertRaisesString(NotImplementedError, 'only [n:] slices are supported'):
            x[:2]
        with self.assertRaisesString(NotImplementedError, 'only [n:] slices are supported'):
            x[object():] = []
        with self.assertRaisesString(NotImplementedError, 'only [n:] slices are supported'):
            x[:2] = []
        with self.assertRaisesString(TypeError, 'can only assign a list expression'):
            x[:] = 0
        self.assertEqual(x, Expression((1, 3, 5, 7)))
        self.assertNotEqual(x, Expression((2, 4, 6)))
        self.assertNotEqual(x, (1, 3, 5, 7))
        with self.assertRaisesString(TypeError, "unhashable type: 'ListExpression'"):
            hash(x)

    def test_insert(self):
        lst = []
        expr = Expression(())
        for pos in [-8, 4, 6, -5, -7, 5, 7, 2, -3, 8, 10, -2, 1, -9, -10, -4, -6, 0, 9, 3, -1]:
            lst.insert(pos, pos)
            self.assertIs(expr.insert(pos, pos), None)
            self.assertEqual(expr, Expression(lst))
            self.assertEqual(expr.lvalue, lst)

    def test_append(self):
        expr = Expression(())
        for i in range(10):
            self.assertIs(expr.append(i), None)
            self.assertEqual(expr, Expression(range(i + 1)))
            self.assertEqual(expr.lvalue, list(range(i + 1)))

    def test_extend(self):
        lst = []
        expr = Expression(())
        for ext in [1], [], [2, 3]:
            lst.extend(ext)
            expr.extend(ext)
            self.assertEqual(expr, Expression(lst))
            self.assertEqual(expr.lvalue, lst)
        with self.assertRaisesString(TypeError, "'int' object is not iterable"):
            expr.extend(0)

    def test_inplace_add(self):
        lst = []
        expr0 = expr = Expression(())
        for ext in [], [1], [], [2, 3]:
            lst += ext
            expr += ext
            self.assertEqual(expr, Expression(lst))
            self.assertEqual(expr.lvalue, lst)
        self.assertIs(expr, expr0)
        with self.assertRaisesString(TypeError, "'int' object is not iterable"):
            expr += 0

    def test_pop(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(expr.pop(0), Expression(0))
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5, 6]))
        with self.assertRaisesString(IndexError, 'pop index of out range'):
            expr.pop(6)
        self.assertEqual(expr.pop(5), Expression(6))
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5]))
        self.assertEqual(expr.pop(-1), Expression(5))
        self.assertEqual(expr, Expression([1, 2, 3, 4]))
        self.assertEqual(expr.pop(-2), Expression(3))
        self.assertEqual(expr, Expression([1, 2, 4]))
        self.assertEqual(expr.pop(1), Expression(2))
        self.assertEqual(expr, Expression([1, 4]))
        expr.pop()
        expr.pop()
        with self.assertRaisesString(IndexError, 'pop from empty list'):
            expr.pop()
        for i in range(-2, 3):
            with self.assertRaisesString(IndexError, 'pop from empty list'):
                expr.pop(i)

    def test_delitem(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        del expr[0]
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5, 6]))
        with self.assertRaisesString(IndexError, 'pop index of out range'):
            expr.pop(6)
        del expr[5]
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5]))
        del expr[-1]
        self.assertEqual(expr, Expression([1, 2, 3, 4]))
        del expr[-2]
        self.assertEqual(expr, Expression([1, 2, 4]))
        del expr[1]
        self.assertEqual(expr, Expression([1, 4]))
        del expr[1:]
        self.assertEqual(expr, Expression([1]))
        del expr[:]
        self.assertEqual(expr, Expression([]))
        for i in range(-2, 3):
            with self.assertRaisesString(IndexError, 'pop from empty list'):
                del expr[i]

    def test_remove(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        expr.remove(Expression(0))
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5, 6]))
        with self.assertRaisesString(IndexError, 'item not in list'):
            expr.remove(Expression(0))
        expr.remove(Expression(6))
        self.assertEqual(expr, Expression([1, 2, 3, 4, 5]))
        expr.remove(Expression(5))
        self.assertEqual(expr, Expression([1, 2, 3, 4]))
        expr.remove(Expression(3))
        self.assertEqual(expr, Expression([1, 2, 4]))
        expr.remove(Expression(2))
        self.assertEqual(expr, Expression([1, 4]))
        expr.remove(Expression(4))
        expr.remove(Expression(1))
        with self.assertRaisesString(IndexError, 'item not in list'):
            expr.remove(Expression(-1))

    def test_contains(self):
        expr = Expression(())
        self.assertNotIn(Expression(42), expr)
        lst = (1, 2, 3)
        expr = Expression(lst)
        for x in lst:
            self.assertNotIn(x, expr)
            self.assertIn(Expression(x), expr)
        self.assertNotIn(Expression(max(lst) + 1), expr)

    def test_index(self):
        expr = Expression(())
        with self.assertRaisesString(ValueError, 'value not in list'):
            expr.index(Expression(42))
        lst = [1, 2, 3]
        expr = Expression(lst)
        for x in lst:
            i = lst.index(x)
            j = expr.index(Expression(x))
            self.assertEqual(i, j)
        with self.assertRaisesString(ValueError, 'value not in list'):
            expr.index(Expression(max(lst) + 1))

    def test_count(self):
        lst = [1, 2, 2, 3, 2]
        expr = Expression(lst)
        for x in lst + [max(lst) + 1]:
            i = lst.count(x)
            j = expr.count(Expression(x))
            self.assertEqual(i, j)

    def test_reverse(self):
        for lst in (), (1, 2, 3):
            expr = Expression(lst)
            self.assertEqual(
                Expression(reversed(expr)),
                Expression(reversed(lst))
            )
            self.assertEqual(
                Expression(reversed(expr)).value,
                tuple(reversed(lst))
            )
            self.assertIs(expr.reverse(), None)
            self.assertEqual(
                expr,
                Expression(reversed(lst))
            )
            self.assertEqual(
                expr.value,
                tuple(reversed(lst))
            )

    def test_copy1(self):
        x = Expression([1, [2], 3])
        y = Expression(x)
        x[1][0] = 0
        self.assertRepr(x, 'Expression([1, [0], 3])')
        self.assertRepr(y, 'Expression([1, [0], 3])')
        x[1] = 0
        self.assertRepr(x, 'Expression([1, 0, 3])')
        self.assertRepr(y, 'Expression([1, [0], 3])')

    def test_copy2(self):
        x = Expression([1, [2], 3])
        y = copy.copy(x)
        x[1][0] = 0
        self.assertRepr(x, 'Expression([1, [0], 3])')
        self.assertRepr(y, 'Expression([1, [0], 3])')
        x[1] = 0
        self.assertRepr(x, 'Expression([1, 0, 3])')
        self.assertRepr(y, 'Expression([1, [0], 3])')

    def test_copy3(self):
        x = Expression([1, [2], 3])
        y = copy.deepcopy(x)
        x[1][0] = 0
        self.assertRepr(x, 'Expression([1, [0], 3])')
        self.assertRepr(y, 'Expression([1, [2], 3])')
        x[1] = 0
        self.assertRepr(x, 'Expression([1, 0, 3])')
        self.assertRepr(y, 'Expression([1, [2], 3])')

    def test_abc(self):
        x = Expression(())
        self.assertIsInstance(x, collections_abc.MutableSequence)
        self.assertIsInstance(iter(x), collections_abc.Iterator)

    def test_pickle(self):
        for lst in (), (1, 2, 3), (1, (2, 3)):
            x = Expression(lst)
            self.assertPickleEqual(x)

class ExpressionParserTestCase(SexprTestCase):

    def test_badstring(self):
        with self.assertRaises(ExpressionSyntaxError):
            Expression.from_string('(1')

    def test_attr_from_file(self):
        self.assertIs(getattr(Expression, 'from_file', None), None)

    def test_bad_io(self):
        with self.assertRaisesString(AttributeError, "'int' object has no attribute 'read'"):
            Expression.from_stream(42)

    def test_bad_file_io(self):
        if os.name == 'nt':
            raise self.SkipTest('not implemented on Windows')
        path = '/proc/self/mem'
        try:
            os.stat(path)
        except OSError as exc:
            raise SkipTest('{exc.filename}: {exc.strerror}'.format(exc=exc))
        with open('/proc/self/mem') as fp:
            with self.assertRaises(IOError) as ecm:
                Expression.from_stream(fp)
        self.assertIn(
            ecm.exception.errno,
            (errno.EIO, errno.EFAULT)
        )

    def test_bad_unicode_io(self):
        fp = StringIO(chr(0xD800))
        with self.assertRaises(UnicodeEncodeError):
            Expression.from_stream(fp)

class ExpressionParserAsciiTestCase(SexprTestCase):

    expr = '(eggs) (ham)'
    repr = ["Expression([Symbol('eggs')])", "Expression([Symbol('ham')])"]

    def check(self, fp):
        def read():
            return Expression.from_stream(fp)
        x = read()
        self.assertRepr(x, self.repr[0])
        x = read()
        self.assertRepr(x, self.repr[1])
        with self.assertRaises(ExpressionSyntaxError):
            x = read()

    def test_stringio(self):
        fp = io.StringIO(self.expr)
        self.check(fp)

    def test_bytesio(self):
        fp = io.BytesIO(self.expr.encode('UTF-8'))
        self.check(fp)

    def test_file_io_text(self):
        fp = tempfile.TemporaryFile(mode='w+t', encoding='UTF-16-LE')
        with fp:
            fp.write(self.expr)
            fp.flush()
            fp.seek(0)
            self.check(fp)

    def test_codecs_io(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'tmp')
            with codecs.open(path, mode='w+', encoding='UTF-16-LE') as fp:
                fp.write(self.expr)
                fp.seek(0)
                self.check(fp)
        finally:
            shutil.rmtree(tmpdir)

    def test_file_io_binary(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            fp.write(self.expr.encode('UTF-8'))
            fp.flush()
            fp.seek(0)
            self.t(fp)

class ExpressionParserNonAsciiTestCase(ExpressionParserAsciiTestCase):

    expr = '"jeż" "żółw"'
    repr = [r"Expression('jeż')", r"Expression('żółw')"]


class ExpressionWriterTestCase(SexprTestCase):

    def test_bad_io(self):
        expr = Expression(23)
        with self.assertRaisesString(AttributeError, "'int' object has no attribute 'write'"):
            expr.print_into(42)

    def test_bad_file_io(self):
        ecm = None
        path = '/dev/full'
        try:
            os.stat(path)
        except OSError as exc:
            raise self.SkipTest('{exc.filename}: {exc.strerror}'.format(exc=exc))
        fp = open(path, 'w', buffering=2)
        expr = Expression(23)
        try:
            with self.assertRaises(IOError) as ecm:
                for i in range(10000):
                    expr.print_into(fp)
        finally:
            try:
                fp.close()
            except IOError:
                if ecm is None:
                    raise
        self.assertEqual(ecm.exception.errno, errno.ENOSPC)

    def test_reentrant(self):
        if not _ExpressionIO._reentrant:
            raise self.SkipTest('this test requires DjVuLibre >= 3.5.26')
        class File(object):
            def write(self, s):
                expr.as_string()
        expr = Expression(23)
        fp = File()
        expr.print_into(fp)

    def test_escape_unicode_type(self):
        expr = Expression(23)
        fp = StringIO()
        for v in True, False, 1, 0, 'yes', '':
            expr.print_into(fp, escape_unicode=v)
            expr.as_string(escape_unicode=v)

class ExpressionWriterAsciiTestCase(SexprTestCase):

    expr = Expression([Symbol('eggs'), Symbol('ham')])
    repr = urepr = '(eggs ham)'

    def test_stringio_7(self):
        fp = io.StringIO()
        self.expr.print_into(fp)
        self.assertEqual(fp.getvalue(), self.repr)

    def test_stringio_8(self):
        fp = io.StringIO()
        self.expr.print_into(fp, escape_unicode=False)
        self.assertEqual(fp.getvalue(), self.urepr)

    def test_bytesio_7(self):
        fp = io.BytesIO()
        self.expr.print_into(fp)
        self.assertEqual(fp.getvalue(), self.repr.encode('UTF-8'))

    def test_bytesio_8(self):
        fp = io.BytesIO()
        self.expr.print_into(fp, escape_unicode=False)
        self.assertEqual(fp.getvalue(), self.urepr.encode('UTF-8'))

    def test_file_io_text_7(self):
        with tempfile.TemporaryFile(mode='w+t') as fp:
            self.expr.print_into(fp)
            fp.seek(0)
            self.assertEqual(fp.read(), self.repr)

    def test_file_io_text_8(self):
        fp = tempfile.TemporaryFile(mode='w+t', encoding='UTF-16-LE')
        with fp:
            self.expr.print_into(fp, escape_unicode=False)
            fp.seek(0)
            self.assertEqual(fp.read(), self.urepr)

    def test_codecs_io_text_7(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'tmp')
            with codecs.open(path, mode='w+', encoding='UTF-16-LE') as fp:
                self.expr.print_into(fp)
                fp.seek(0)
                self.assertEqual(fp.read(), self.repr)
        finally:
            shutil.rmtree(tmpdir)

    def test_codecs_io_text_8(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'tmp')
            with codecs.open(path, mode='w+', encoding='UTF-16-LE') as fp:
                self.expr.print_into(fp, escape_unicode=False)
                fp.seek(0)
                self.assertEqual(fp.read(), self.urepr)
        finally:
            shutil.rmtree(tmpdir)

    def test_file_io_binary_7(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            self.expr.print_into(fp)
            fp.seek(0)
            self.assertEqual(fp.read(), self.repr.encode('UTF-8'))

    def test_file_io_binary_8(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            self.expr.print_into(fp, escape_unicode=False)
            fp.seek(0)
            self.assertEqual(fp.read(), self.urepr.encode('UTF-8'))

    def test_as_string_7(self):
        s = self.expr.as_string()
        self.assertEqual(s, self.repr)

    def test_as_string_8(self):
        s = self.expr.as_string(escape_unicode=False)
        self.assertEqual(s, self.urepr)

class ExpressionWriterNonAsciiTestCase(ExpressionWriterAsciiTestCase):

    expr = Expression('żółw')
    repr = r'"\305\274\303\263\305\202w"'
    urepr = r'"żółw"'

class VersionTestCase(TestCase):
    def test_version(self):
        self.assertIsInstance(__version__, str)
        self.assertEqual(__version__, get_changelog_version())

class WildcardImportTestCase(TestCase):
    def test_wildcard_import(self):
        namespace = wildcard_import('djvu.sexpr')
        self.assertListEqual(
            sorted(namespace.keys()), [
                'Expression',
                'ExpressionSyntaxError',
                'IntExpression',
                'InvalidExpression',
                'ListExpression',
                'StringExpression',
                'Symbol',
                'SymbolExpression'
            ]
        )

# vim:ts=4 sts=4 sw=4 et
