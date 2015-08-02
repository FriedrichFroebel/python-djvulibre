# encoding=UTF-8

# Copyright © 2007-2015 Jakub Wilk <jwilk@jwilk.net>
#
# This package is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 dated June, 1991.
#
# This package is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

import collections
import copy
import errno
import io
import os
import re
import tempfile

import pickle
try:
    import cPickle as cpickle
except ImportError:
    cpickle = None

from djvu.sexpr import *
from djvu.sexpr import __version__
from djvu.sexpr import _ExpressionIO

from common import *

def assert_pickle_equal(obj):
    for pickle_module in pickle, cpickle:
        if pickle_module is None:
            continue
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            pickled_obj = pickle_module.dumps(obj, protocol=protocol)
            repickled_obj = pickle_module.loads(pickled_obj)
            assert_equal(obj, repickled_obj)

class test_int_expressions():

    def test_short(self):
        x = Expression(3)
        assert_repr(x, 'Expression(3)')
        assert_is(x, Expression(x))
        assert_equal(x.value, 3)
        assert_equal(x.lvalue, 3)
        assert_equal(str(x), '3')
        assert_repr(x, repr(Expression.from_string(str(x))))
        assert_equal(int(x), 3)
        if not py3k:
            long_x = long(x)
            assert_equal(type(long_x), long)
            assert_equal(long_x, L(3))
        assert_equal(x, Expression(3))
        assert_not_equal(x, Expression(-3))
        assert_equal(hash(x), x.value)
        assert_not_equal(x, 3)

    def test_long(self):
        x = Expression(L(42))
        assert_repr(x, 'Expression(42)')

    def test_limits(self):
        assert_equal(Expression((1 << 29) - 1).value, (1 << 29) - 1)
        assert_equal(Expression(-1 << 29).value, -1 << 29)
        with assert_raises_str(ValueError, 'value not in range(-2 ** 29, 2 ** 29)'):
            Expression(1 << 29)
        with assert_raises_str(ValueError, 'value not in range(-2 ** 29, 2 ** 29)'):
            Expression((-1 << 29) - 1)

    def test_bool(self):
        assert_equal(Expression(1) and 42, 42)
        assert_equal(Expression(0) or 42, 42)

    def test_pickle(self):
        x = Expression(42)
        assert_pickle_equal(x)

class test_float_expressions():

    # TODO: float expressions are not implemented yet

    def test_parse(self):
        with assert_raises(ExpressionSyntaxError):
            x = Expression.from_string('3.14')
            if isinstance(x.value, Symbol):
                raise ExpressionSyntaxError

class test_symbols():

    def t(self, name):
        symbol = Symbol(name)
        assert_equal(type(symbol), Symbol)
        assert_equal(symbol, Symbol(name))
        assert_is(symbol, Symbol(name))
        if py3k:
            assert_equal(str(symbol), name)
        else:
            assert_equal(str(symbol), name.encode('UTF-8'))
            assert_equal(unicode(symbol), name)
        assert_not_equal(symbol, name)
        assert_not_equal(symbol, name.encode('UTF-8'))
        assert_equal(hash(symbol), hash(name.encode('UTF-8')))
        assert_pickle_equal(symbol)

    def test_ascii(self):
        self.t('eggs')

    def test_nonascii(self):
        self.t(u('ветчина'))

    def test_inequality(self):
        assert_less(
            Symbol('eggs'),
            Symbol('ham'),
        )

def test_expressions():
    x = Expression(Symbol('eggs'))
    assert_repr(x, "Expression(Symbol('eggs'))")
    assert_is(x, Expression(x))
    assert_equal(x.value, Symbol('eggs'))
    assert_equal(x.lvalue, Symbol('eggs'))
    assert_equal(str(x), 'eggs')
    assert_repr(x, repr(Expression.from_string(str(x))))
    assert_equal(x, Expression(Symbol('eggs')))
    assert_not_equal(x, Expression('eggs'))
    assert_not_equal(x, Symbol('eggs'))
    assert_equal(hash(x), hash('eggs'))
    assert_pickle_equal(x)

def test_string_expressions():
    x = Expression('eggs')
    assert_repr(x, "Expression('eggs')")
    assert_is(x, Expression(x))
    assert_equal(x.value, 'eggs')
    assert_equal(x.lvalue, 'eggs')
    assert_equal(str(x), '"eggs"')
    assert_repr(x, repr(Expression.from_string(str(x))))
    assert_equal(x, Expression('eggs'))
    assert_not_equal(x, Expression(Symbol('eggs')))
    assert_not_equal(x, 'eggs')
    assert_equal(hash(x), hash('eggs'))
    assert_pickle_equal(x)

class test_unicode_expressions():

    def test1(self):
        x = Expression(u('eggs'))
        assert_repr(x, "Expression('eggs')")
        assert_is(x, Expression(x))

    def test2(self):
        x = Expression(u('żółw'))
        if py3k:
            assert_repr(x, "Expression('żółw')")
        else:
            assert_repr(x, r"Expression('\xc5\xbc\xc3\xb3\xc5\x82w')")

class test_list_expressions():

    def test1(self):
        x = Expression(())
        assert_repr(x, "Expression([])")
        y = Expression(x)
        assert_is(x, y)
        assert_equal(x.value, ())
        assert_equal(x.lvalue, [])
        assert_equal(len(x), 0)
        assert_equal(bool(x), False)
        assert_equal(list(x), [])

    def test2(self):
        x = Expression([[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])
        assert_repr(x, "Expression([[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])")
        y = Expression(x)
        assert_repr(y, repr(x))
        assert_false(x is y)
        assert_equal(x.value, ((1, 2), 3, (4, 5, Symbol('baz')), ('quux',)))
        assert_equal(x.lvalue, [[1, 2], 3, [4, 5, Symbol('baz')], ['quux']])
        assert_equal(str(x), '((1 2) 3 (4 5 baz) ("quux"))')
        assert_repr(x, repr(Expression.from_string(str(x))))
        assert_equal(len(x), 4)
        assert_equal(bool(x), True)
        assert_equal(tuple(x), (Expression((1, 2)), Expression(3), Expression((4, 5, Symbol('baz'))), Expression(('quux',))))
        with assert_raises_str(TypeError, 'key must be an integer or a slice'):
            x[object()]
        assert_equal(x[1], Expression(3))
        assert_equal(x[-1][0], Expression('quux'))
        with assert_raises_str(IndexError, 'list index of out range'):
            x[6]
        with assert_raises_str(IndexError, 'list index of out range'):
            x[-6]
        assert_equal(x[:].value, x.value)
        assert_equal(x[:].lvalue, x.lvalue)
        assert_repr(x[1:], "Expression([3, [4, 5, Symbol('baz')], ['quux']])")
        assert_repr(x[-2:], "Expression([[4, 5, Symbol('baz')], ['quux']])")
        x[-2:] = 4, 5, 6
        assert_repr(x, 'Expression([[1, 2], 3, 4, 5, 6])')
        x[0] = 2
        assert_repr(x, 'Expression([2, 3, 4, 5, 6])')
        x[:] = (1, 3, 5)
        assert_repr(x, 'Expression([1, 3, 5])')
        x[3:] = 7,
        assert_repr(x, 'Expression([1, 3, 5, 7])')
        with assert_raises_str(NotImplementedError, 'only [n:] slices are supported'):
            x[object():]
        with assert_raises_str(NotImplementedError, 'only [n:] slices are supported'):
            x[:2]
        with assert_raises_str(NotImplementedError, 'only [n:] slices are supported'):
            x[object():] = []
        with assert_raises_str(NotImplementedError, 'only [n:] slices are supported'):
            x[:2] = []
        with assert_raises_str(TypeError, 'can only assign a list expression'):
            x[:] = 0
        assert_equal(x, Expression((1, 3, 5, 7)))
        assert_not_equal(x, Expression((2, 4, 6)))
        assert_not_equal(x, (1, 3, 5, 7))
        with assert_raises_str(TypeError, "unhashable type: 'ListExpression'"):
            hash(x)

    def test_insert(self):
        lst = []
        expr = Expression(())
        for pos in [-8, 4, 6, -5, -7, 5, 7, 2, -3, 8, 10, -2, 1, -9, -10, -4, -6, 0, 9, 3, -1]:
            lst.insert(pos, pos)
            assert_is(expr.insert(pos, pos), None)
            assert_equal(expr, Expression(lst))
            assert_equal(expr.lvalue, lst)

    def test_append(self):
        expr = Expression(())
        for i in range(10):
            assert_is(expr.append(i), None)
            assert_equal(expr, Expression(range(i + 1)))
            assert_equal(expr.lvalue, list(range(i + 1)))

    def test_extend(self):
        lst = []
        expr = Expression(())
        for ext in [1], [], [2, 3]:
            lst.extend(ext)
            expr.extend(ext)
            assert_equal(expr, Expression(lst))
            assert_equal(expr.lvalue, lst)
        with assert_raises_str(TypeError, "'int' object is not iterable"):
            expr.extend(0)

    def test_inplace_add(self):
        lst = []
        expr0 = expr = Expression(())
        for ext in [], [1], [], [2, 3]:
            lst += ext
            expr += ext
            assert_equal(expr, Expression(lst))
            assert_equal(expr.lvalue, lst)
        assert_is(expr, expr0)
        with assert_raises_str(TypeError, "'int' object is not iterable"):
            expr += 0

    def test_pop(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        assert_equal(expr.pop(0), Expression(0))
        assert_equal(expr, Expression([1, 2, 3, 4, 5, 6]))
        with assert_raises_str(IndexError, 'pop index of out range'):
            expr.pop(6)
        assert_equal(expr.pop(5), Expression(6))
        assert_equal(expr, Expression([1, 2, 3, 4, 5]))
        assert_equal(expr.pop(-1), Expression(5))
        assert_equal(expr, Expression([1, 2, 3, 4]))
        assert_equal(expr.pop(-2), Expression(3))
        assert_equal(expr, Expression([1, 2, 4]))
        assert_equal(expr.pop(1), Expression(2))
        assert_equal(expr, Expression([1, 4]))
        expr.pop()
        expr.pop()
        with assert_raises_str(IndexError, 'pop from empty list'):
            expr.pop()
        for i in range(-2, 3):
            with assert_raises_str(IndexError, 'pop from empty list'):
                expr.pop(i)

    def test_delitem(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        del expr[0]
        assert_equal(expr, Expression([1, 2, 3, 4, 5, 6]))
        with assert_raises_str(IndexError, 'pop index of out range'):
            expr.pop(6)
        del expr[5]
        assert_equal(expr, Expression([1, 2, 3, 4, 5]))
        del expr[-1]
        assert_equal(expr, Expression([1, 2, 3, 4]))
        del expr[-2]
        assert_equal(expr, Expression([1, 2, 4]))
        del expr[1]
        assert_equal(expr, Expression([1, 4]))
        del expr[1:]
        assert_equal(expr, Expression([1]))
        del expr[:]
        assert_equal(expr, Expression([]))
        for i in range(-2, 3):
            with assert_raises_str(IndexError, 'pop from empty list'):
                del expr[i]

    def test_remove(self):
        expr = Expression([0, 1, 2, 3, 4, 5, 6])
        expr.remove(Expression(0))
        assert_equal(expr, Expression([1, 2, 3, 4, 5, 6]))
        with assert_raises_str(IndexError, 'item not in list'):
            expr.remove(Expression(0))
        expr.remove(Expression(6))
        assert_equal(expr, Expression([1, 2, 3, 4, 5]))
        expr.remove(Expression(5))
        assert_equal(expr, Expression([1, 2, 3, 4]))
        expr.remove(Expression(3))
        assert_equal(expr, Expression([1, 2, 4]))
        expr.remove(Expression(2))
        assert_equal(expr, Expression([1, 4]))
        expr.remove(Expression(4))
        expr.remove(Expression(1))
        with assert_raises_str(IndexError, 'item not in list'):
            expr.remove(Expression(-1))

    def test_contains(self):
        expr = Expression(())
        assert_not_in(Expression(42), expr)
        lst = (1, 2, 3)
        expr = Expression(lst)
        for x in lst:
            assert_not_in(x, expr)
            assert_in(Expression(x), expr)
        assert_not_in(Expression(max(lst) + 1), expr)

    def test_index(self):
        expr = Expression(())
        with assert_raises_str(ValueError, 'value not in list'):
            expr.index(Expression(42))
        lst = [1, 2, 3]
        expr = Expression(lst)
        for x in lst:
            i = lst.index(x)
            j = expr.index(Expression(x))
            assert_equal(i, j)
        with assert_raises_str(ValueError, 'value not in list'):
            expr.index(Expression(max(lst) + 1))

    def test_count(self):
        lst = [1, 2, 2, 3, 2]
        expr = Expression(lst)
        for x in lst + [max(lst) + 1]:
            i = lst.count(x)
            j = expr.count(Expression(x))
            assert_equal(i, j)

    def test_reverse(self):
        for lst in (), (1, 2, 3):
            expr = Expression(lst)
            assert_equal(
                Expression(reversed(expr)),
                Expression(reversed(lst))
            )
            assert_equal(
                Expression(reversed(expr)).value,
                tuple(reversed(lst))
            )
            assert_is(expr.reverse(), None)
            assert_equal(
                expr,
                Expression(reversed(lst))
            )
            assert_equal(
                expr.value,
                tuple(reversed(lst))
            )

    def test_copy1(self):
        x = Expression([1, [2], 3])
        y = Expression(x)
        x[1][0] = 0
        assert_repr(x, 'Expression([1, [0], 3])')
        assert_repr(y, 'Expression([1, [0], 3])')
        x[1] = 0
        assert_repr(x, 'Expression([1, 0, 3])')
        assert_repr(y, 'Expression([1, [0], 3])')

    def test_copy2(self):
        x = Expression([1, [2], 3])
        y = copy.copy(x)
        x[1][0] = 0
        assert_repr(x, 'Expression([1, [0], 3])')
        assert_repr(y, 'Expression([1, [0], 3])')
        x[1] = 0
        assert_repr(x, 'Expression([1, 0, 3])')
        assert_repr(y, 'Expression([1, [0], 3])')

    def test_copy3(self):
        x = Expression([1, [2], 3])
        y = copy.deepcopy(x)
        x[1][0] = 0
        assert_repr(x, 'Expression([1, [0], 3])')
        assert_repr(y, 'Expression([1, [2], 3])')
        x[1] = 0
        assert_repr(x, 'Expression([1, 0, 3])')
        assert_repr(y, 'Expression([1, [2], 3])')

    def test_abc(self):
        x = Expression(())
        assert_is_instance(x, collections.MutableSequence)
        assert_is_instance(iter(x), collections.Iterator)

    def test_pickle(self):
        for lst in (), (1, 2, 3), (1, (2, 3)):
            x = Expression(lst)
            assert_pickle_equal(x)

class test_expression_parser():

    def test_badstring(self):
        with assert_raises(ExpressionSyntaxError):
            Expression.from_string('(1')

    def test_attr_from_file(self):
        assert_is(getattr(Expression, 'from_file', None), None)

    def test_bad_io(self):
        with assert_raises_str(AttributeError, "'int' object has no attribute 'read'"):
            Expression.from_stream(42)

    def test_bad_file_io(self):
        with open('/proc/self/mem') as fp:
            with assert_raises(IOError) as ecm:
                Expression.from_stream(fp)
        assert_equal(ecm.exception.errno, errno.EIO)

    if py3k:
        def test_bad_unicode_io(self):
            fp = StringIO(chr(0xD800))
            with assert_raises(UnicodeEncodeError):
                Expression.from_stream(fp)

    def test_stringio(self):
        fp = StringIO('(eggs) (ham)')
        def read():
            return Expression.from_stream(fp)
        x = read()
        assert_repr(x, "Expression([Symbol('eggs')])")
        x = read()
        assert_repr(x, "Expression([Symbol('ham')])")
        with assert_raises(ExpressionSyntaxError):
            x = read()

    def test_file_io_text(self):
        with tempfile.TemporaryFile(mode='w+t') as fp:
            def read():
                return Expression.from_stream(fp)
            if not py3k:
                assert_equal(type(fp), file)
            fp.write('(eggs) (ham)')
            fp.flush()
            fp.seek(0)
            x = read()
            assert_repr(x, "Expression([Symbol('eggs')])")
            x = read()
            assert_repr(x, "Expression([Symbol('ham')])")
            with assert_raises(ExpressionSyntaxError):
                x = read()

    def test_file_io_binary(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            def read():
                return Expression.from_stream(fp)
            if not py3k:
                assert_equal(type(fp), file)
            fp.write(b('(eggs) (ham)'))
            fp.flush()
            fp.seek(0)
            x = read()
            assert_repr(x, "Expression([Symbol('eggs')])")
            x = read()
            assert_repr(x, "Expression([Symbol('ham')])")
            with assert_raises(ExpressionSyntaxError):
                x = read()

class test_expression_writer():

    expr = Expression([Symbol('eggs'), Symbol('ham')])
    repr = urepr = '(eggs ham)'

    def test_bad_io(self):
        with assert_raises_str(AttributeError, "'int' object has no attribute 'write'"):
            self.expr.print_into(42)

    def test_bad_file_io(self):
        ecm = None
        fp = open('/dev/full', 'w', buffering=2)
        try:
            with assert_raises(IOError) as ecm:
                for i in range(1000):
                    self.expr.print_into(fp)
        finally:
            try:
                fp.close()
            except IOError:
                if ecm is None:
                    raise
        assert_equal(ecm.exception.errno, errno.ENOSPC)

    def test_reentrant(self):
        if not _ExpressionIO._reentrant:
            raise SkipTest('this test requires DjVuLibre >= 3.5.26')
        class File(object):
            def write(self, s):
                expr.as_string()
        expr = self.expr
        fp = File()
        expr.print_into(fp)

    def test_stringio_7(self):
        fp = StringIO()
        self.expr.print_into(fp)
        assert_equal(fp.getvalue(), self.repr)

    def test_stringio_8(self):
        fp = StringIO()
        self.expr.print_into(fp, escape_unicode=False)
        assert_equal(fp.getvalue(), self.urepr)

    def test_bytesio_7(self):
        fp = io.BytesIO()
        self.expr.print_into(fp)
        assert_equal(fp.getvalue(), b(self.repr))

    def test_bytesio_8(self):
        fp = io.BytesIO()
        self.expr.print_into(fp, escape_unicode=False)
        assert_equal(fp.getvalue(), b(self.urepr))

    def test_file_io_text_7(self):
        with tempfile.TemporaryFile(mode='w+t') as fp:
            if not py3k and os.name == 'posix':
                assert_equal(type(fp), file)
            self.expr.print_into(fp)
            fp.seek(0)
            assert_equal(fp.read(), self.repr)

    def test_file_io_text_8(self):
        if py3k:
            fp = tempfile.TemporaryFile(mode='w+t', encoding='UTF-8')
        else:
            fp = tempfile.TemporaryFile(mode='w+t')
        with fp:
            if not py3k and os.name == 'posix':
                assert_equal(type(fp), file)
            self.expr.print_into(fp, escape_unicode=False)
            fp.seek(0)
            assert_equal(fp.read(), self.urepr)

    def test_file_io_binary_7(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            if not py3k and os.name == 'posix':
                assert_equal(type(fp), file)
            self.expr.print_into(fp)
            fp.seek(0)
            assert_equal(fp.read(), b(self.repr))

    def test_file_io_binary_8(self):
        with tempfile.TemporaryFile(mode='w+b') as fp:
            if not py3k and os.name == 'posix':
                assert_equal(type(fp), file)
            self.expr.print_into(fp, escape_unicode=False)
            fp.seek(0)
            assert_equal(fp.read(), b(self.urepr))

    def test_as_string_7(self):
        s = self.expr.as_string()
        assert_equal(s, self.repr)

    def test_as_string_8(self):
        s = self.expr.as_string(escape_unicode=False)
        assert_equal(s, self.urepr)

class test_expression_writer_nonascii(test_expression_writer):

    expr = Expression(u('żółw'))
    repr = r'"\305\274\303\263\305\202w"'
    urepr = r'"żółw"'

def test_version():
    assert_is_instance(__version__, str)

# vim:ts=4 sts=4 sw=4 et
