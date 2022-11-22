# encoding=UTF-8

# Copyright © 2007-2022 Jakub Wilk <jwilk@jwilk.net>
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

import array
import errno
import os
import re
import subprocess
import sys
import tempfile

from djvu.decode import (
    AffineTransform,
    Context,
    DDJVU_VERSION,
    DOCUMENT_TYPE_BUNDLED,
    DOCUMENT_TYPE_SINGLE_PAGE,
    DocInfoMessage,
    Document,
    DocumentAnnotations,
    DocumentDecodingJob,
    DocumentOutline,
    ErrorMessage,
    File,
    FileUri,
    Hyperlinks,
    Job,
    JobFailed,
    JobOK,
    Message,
    Metadata,
    NewStreamMessage,
    NotAvailable,
    PAGE_TYPE_BITONAL,
    Page,
    PageAnnotations,
    PageJob,
    PageText,
    PixelFormat,
    PixelFormatGrey,
    PixelFormatPackedBits,
    PixelFormatPalette,
    PixelFormatRgb,
    PixelFormatRgbMask,
    RENDER_COLOR,
    SaveJob,
    Stream,
    TEXT_DETAILS_ALL,
    TEXT_DETAILS_CHARACTER,
    TEXT_DETAILS_COLUMN,
    TEXT_DETAILS_LINE,
    TEXT_DETAILS_PAGE,
    TEXT_DETAILS_PARAGRAPH,
    TEXT_DETAILS_REGION,
    TEXT_DETAILS_WORD,
    ThumbnailMessage,
    __version__,
)
from djvu.sexpr import (
    Expression,
    Symbol,
)

from tools import (
    interim_locale,
    get_changelog_version,
    locale_encoding,
    skip_unless_c_messages,
    skip_unless_command_exists,
    skip_unless_translation_exists,
    TestCase,
    wildcard_import,
)


IMAGES = os.path.join(os.path.dirname(__file__), 'images', '')


class DecodeTestCase(TestCase):
    def run_command(self, *cmd, **kwargs):
        stdin = kwargs.pop('stdin', None)
        env = dict(os.environ)
        for key, value in kwargs.items():
            if key.isupper():
                env[key] = value
                continue
            raise TypeError(f'{key!r} is an invalid keyword argument for this function')
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if stdin is not None:
            kwargs.update(stdin=subprocess.PIPE)
        child = subprocess.Popen(list(cmd), **kwargs)
        stdout, stderr = child.communicate(stdin)
        if child.returncode != 0:
            raise subprocess.CalledProcessError(child.returncode, cmd[0])
        return stdout, stderr

    def create_djvu(self, commands='', sexpr=''):
        skip_unless_command_exists('djvused')
        if sexpr:
            commands += f'\nset-ant\n{sexpr}\n.\n'
        file = tempfile.NamedTemporaryFile(prefix='test', suffix='djvu')
        file.seek(0)
        file.write(
            b'\x41\x54\x26\x54\x46\x4F\x52\x4D\x00\x00\x00\x22\x44\x4A\x56\x55'
            b'\x49\x4E\x46\x4F\x00\x00\x00\x0A\x00\x01\x00\x01\x18\x00\x2C\x01'
            b'\x16\x01\x53\x6A\x62\x7A\x00\x00\x00\x04\xBC\x73\x1B\xD7'
        )
        file.flush()
        stdout, stderr = self.run_command('djvused', '-s', file.name, stdin=commands.encode(locale_encoding))
        self.assertEqual(stdout, ''.encode(locale_encoding))
        self.assertEqual(stderr, ''.encode(locale_encoding))
        return file


class ContextTestCase(TestCase):
    def test_context_cache(self):
        context = Context()
        self.addCleanup(context.clear_cache)
        self.assertEqual(context.cache_size, 10 << 20)
        for n in -100, 0, 1 << 31:
            with self.assertRaisesString(ValueError, '0 < cache_size < (2 ** 31) must be satisfied'):
                context.cache_size = n
        with self.assertRaisesString(ValueError, '0 < cache_size < (2 ** 31) must be satisfied'):
            context.cache_size = 0
        n = 1
        while n < (1 << 31):
            context.cache_size = n
            self.assertEqual(context.cache_size, n)
            n = (n + 1) * 2 - 1


class DocumentsTestCase(DecodeTestCase):

    def test_bad_new(self):
        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.Document' instances"):
            Document()

    def test_nonexistent(self):
        path = '__nonexistent__'
        try:
            os.stat(path)
        except OSError as ex:
            c_message = ex.args[1]
        else:
            raise OSError(errno.EEXIST, os.strerror(errno.EEXIST), path)
        c_message.encode('ASCII')
        skip_unless_c_messages()
        context = Context()
        with self.assertRaises(JobFailed):
            context.new_document(FileUri(path))
        message = context.get_message()
        self.assertIsInstance(message, ErrorMessage)
        self.assertIsInstance(message.message, str)
        self.assertEqual(
            message.message,
            f"[1-11711] Failed to open '{path}': {c_message}."
        )
        self.assertEqual(str(message), message.message)

    def test_nonexistent_ja(self):
        skip_unless_c_messages()
        skip_unless_translation_exists('ja_JP.UTF-8')
        path = '__nonexistent__'
        context = Context()
        try:
            with interim_locale(LC_ALL='ja_JP.UTF-8'):
                os.stat(path)
        except OSError as ex:
            c_message = ex.args[1]
        else:
            raise OSError(errno.EEXIST, os.strerror(errno.EEXIST), path)
        try:
            c_message.encode('ASCII')
        except UnicodeError:
            pass
        else:
            self.fail(f'ja_JP error message is ASCII-only: {c_message!r}')
        with interim_locale(LC_ALL='ja_JP.UTF-8'):
            with self.assertRaises(JobFailed):
                context.new_document(FileUri(path))
            message = context.get_message()
            self.assertIsInstance(message, ErrorMessage)
            self.assertIsInstance(message.message, str)
            self.assertEqual(
                message.message,
                f"[1-11711] Failed to open '{path}': {c_message}."
            )
            self.assertEqual(
                str(message),
                f"[1-11711] Failed to open '{path}': {c_message}."
            )
            self.assertEqual(str(message), message.message)

    def test_new_document(self):
        context = Context()
        document = context.new_document(FileUri(IMAGES + 'test1.djvu'))
        self.assertIsInstance(document, Document)
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        self.assertTrue(document.decoding_done)
        self.assertFalse(document.decoding_error)
        self.assertEqual(document.decoding_status, JobOK)
        self.assertEqual(document.type, DOCUMENT_TYPE_SINGLE_PAGE)
        self.assertEqual(len(document.pages), 1)
        self.assertEqual(len(document.files), 1)
        decoding_job = document.decoding_job
        self.assertTrue(decoding_job.is_done)
        self.assertFalse(decoding_job.is_error)
        self.assertEqual(decoding_job.status, JobOK)
        document_file = document.files[0]
        self.assertIsInstance(document_file, File)
        self.assertIs(document_file.document, document)
        self.assertIs(document_file.get_info(), None)
        self.assertEqual(document_file.type, 'P')
        self.assertEqual(document_file.n_page, 0)
        page = document_file.page
        self.assertIsInstance(page, Page)
        self.assertIs(page.document, document)
        self.assertEqual(page.n, 0)
        self.assertIs(document_file.size, None)
        self.assertEqual(document_file.id, 'test1.djvu')
        self.assertIsInstance(document_file.id, str)
        self.assertEqual(document_file.name, 'test1.djvu')
        self.assertIsInstance(document_file.name, str)
        self.assertEqual(document_file.title, 'test1.djvu')
        self.assertIsInstance(document_file.title, str)
        dump = document.files[0].dump
        self.assertIsInstance(dump, str)
        self.assertEqual(
            [line for line in dump.splitlines()],
            [
                '  FORM:DJVU [83] ',
                '    INFO [10]         DjVu 64x48, v24, 300 dpi, gamma=2.2',
                '    Sjbz [53]         JB2 bilevel data',
            ]
        )
        page = document.pages[0]
        self.assertIsInstance(page, Page)
        self.assertIs(page.document, document)
        self.assertIs(page.get_info(), None)
        self.assertEqual(page.width, 64)
        self.assertEqual(page.height, 48)
        self.assertEqual(page.size, (64, 48))
        self.assertEqual(page.dpi, 300)
        self.assertEqual(page.rotation, 0)
        self.assertEqual(page.version, 24)
        document_file = page.file
        self.assertIsInstance(document_file, File)
        self.assertEqual(document_file.id, 'test1.djvu')
        self.assertIsInstance(document_file.id, str)
        dump = document.files[0].dump
        self.assertIsInstance(dump, str)
        self.assertEqual(
            [line for line in dump.splitlines()],
            [
                '  FORM:DJVU [83] ',
                '    INFO [10]         DjVu 64x48, v24, 300 dpi, gamma=2.2',
                '    Sjbz [53]         JB2 bilevel data',
            ]
        )
        self.assertIs(document.get_message(wait=False), None)
        self.assertIs(context.get_message(wait=False), None)
        with self.assertRaisesString(IndexError, 'file number out of range'):
            document.files[-1].get_info()
        self.assertIs(document.get_message(wait=False), None)
        self.assertIs(context.get_message(wait=False), None)
        with self.assertRaisesString(IndexError, 'page number out of range'):
            _ = document.pages[-1]
        with self.assertRaisesString(IndexError, 'page number out of range'):
            _ = document.pages[1]
        self.assertIs(document.get_message(wait=False), None)
        self.assertIs(context.get_message(wait=False), None)

    def test_save(self):
        skip_unless_command_exists('djvudump')
        context = Context()
        original_filename = IMAGES + 'test0.djvu'
        document = context.new_document(FileUri(original_filename))
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        self.assertTrue(document.decoding_done)
        self.assertFalse(document.decoding_error)
        self.assertEqual(document.decoding_status, JobOK)
        self.assertEqual(document.type, DOCUMENT_TYPE_BUNDLED)
        self.assertEqual(len(document.pages), 2)
        self.assertEqual(len(document.files), 3)
        stdout0, stderr0 = self.run_command('djvudump', original_filename, LC_ALL='C')
        self.assertEqual(stderr0, b'')
        stdout0 = stdout0.replace(b'\r\n', b'\n')

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'tmp.djvu'), 'wb') as tmp:
                job = document.save(tmp)
                self.assertIsInstance(job, SaveJob)
                self.assertTrue(job.is_done)
                self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('djvudump', tmp.name, LC_ALL='C')
            self.assertEqual(stderr, b'')
            stdout = stdout.replace(b'\r\n', b'\n')
            self.assertEqual(stdout, stdout0)

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'tmp.djvu'), 'wb') as tmp:
                job = document.save(tmp, pages=(0,))
                self.assertIsInstance(job, SaveJob)
                self.assertTrue(job.is_done)
                self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('djvudump', tmp.name, LC_ALL='C')
            self.assertEqual(stderr, b'')
            stdout = stdout.replace(b'\r\n', b'\n')
            stdout0 = stdout0.split(b'\n')
            stdout = stdout.split(b'\n')
            stdout[4] = stdout[4].replace(b' (1)', b'')
            self.assertEqual(len(stdout), 10)
            self.assertEqual(stdout[3:-1], stdout0[4:10])
            self.assertEqual(stdout[-1], b'')

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_filename = os.path.join(tmpdir, 'index.djvu')
            job = document.save(indirect=tmp_filename)
            self.assertIsInstance(job, SaveJob)
            self.assertTrue(job.is_done)
            self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('djvudump', tmp_filename, LC_ALL='C')
            self.assertEqual(stderr, b'')
            stdout = stdout.replace(b'\r\n', b'\n')
            stdout = stdout.split(b'\n')
            stdout0 = (
                [b'      shared_anno.iff -> shared_anno.iff'] +
                [f'      p{n:04}.djvu -> p{n:04}.djvu'.encode('UTF-8') for n in range(1, 3)]
            )
            self.assertEqual(len(stdout), 7)
            self.assertEqual(stdout[2:-2], stdout0)
            self.assertEqual(stdout[-1], b'')

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_filename = os.path.join(tmpdir, 'index.djvu')
            job = document.save(indirect=tmp_filename, pages=(0,))
            self.assertIsInstance(job, SaveJob)
            self.assertTrue(job.is_done)
            self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('djvudump', tmp_filename, LC_ALL='C')
            stdout = stdout.replace(b'\r\n', b'\n')
            self.assertEqual(stderr, b'')
            stdout = stdout.split(b'\n')
            self.assertEqual(len(stdout), 5)
            self.assertEqual(stdout[2], b'      shared_anno.iff -> shared_anno.iff')
            self.assertEqual(stdout[3], b'      p0001.djvu -> p0001.djvu')
            self.assertEqual(stdout[-1], b'')

    def test_export_ps(self):
        skip_unless_command_exists('ps2ascii')
        context = Context()
        document = context.new_document(FileUri(IMAGES + 'test0.djvu'))
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        self.assertTrue(document.decoding_done)
        self.assertFalse(document.decoding_error)
        self.assertEqual(document.decoding_status, JobOK)
        self.assertEqual(document.type, DOCUMENT_TYPE_BUNDLED)
        self.assertEqual(len(document.pages), 2)
        self.assertEqual(len(document.files), 3)
        with tempfile.NamedTemporaryFile() as tmp:
            job = document.export_ps(tmp.file)
            self.assertIsInstance(job, SaveJob)
            self.assertTrue(job.is_done)
            self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('ps2ascii', tmp.name, LC_ALL='C')
            self.assertEqual(stderr, b'')
            stdout = re.sub(br'[\x00\s]+', b' ', stdout)
            self.assertEqual(stdout, b' ')
        with tempfile.NamedTemporaryFile() as tmp:
            job = document.export_ps(tmp.file, pages=(0,), text=True)
            self.assertIsInstance(job, SaveJob)
            self.assertTrue(job.is_done)
            self.assertFalse(job.is_error)
            stdout, stderr = self.run_command('ps2ascii', tmp.name, LC_ALL='C')
            self.assertEqual(stderr, b'')
            stdout = stdout.decode('ASCII')
            stdout = re.sub(r'[\x00\s]+', ' ', stdout)
            stdout = ' '.join(stdout.split()[:3])
            expected = '1 Lorem ipsum'
            self.assertMultiLineEqual(stdout, expected)


class PixelFormatsTestCase(TestCase):

    def test_bad_new(self):
        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.PixelFormat' instances"):
            PixelFormat()

    def test_rgb(self):
        pf = PixelFormatRgb()
        self.assertRepr(pf, "djvu.decode.PixelFormatRgb(byte_order = 'RGB', bpp = 24)")
        pf = PixelFormatRgb('RGB')
        self.assertRepr(pf, "djvu.decode.PixelFormatRgb(byte_order = 'RGB', bpp = 24)")
        pf = PixelFormatRgb('BGR')
        self.assertRepr(pf, "djvu.decode.PixelFormatRgb(byte_order = 'BGR', bpp = 24)")

    def test_rgb_mask(self):
        pf = PixelFormatRgbMask(0xFF, 0xF00, 0x1F000, 0, 16)
        self.assertRepr(
            pf,
            "djvu.decode.PixelFormatRgbMask(red_mask = 0x00ff, green_mask = 0x0f00, blue_mask = 0xf000, xor_value = 0x0000, bpp = 16)"
        )
        pf = PixelFormatRgbMask(0xFF000000, 0xFF0000, 0xFF00, 0xFF, 32)
        self.assertRepr(
            pf,
            (
                "djvu.decode.PixelFormatRgbMask(red_mask = 0xff000000, green_mask = 0x00ff0000, blue_mask = 0x0000ff00, "
                "xor_value = 0x000000ff, bpp = 32)"
            )
        )

    def test_grey(self):
        pf = PixelFormatGrey()
        self.assertRepr(pf, "djvu.decode.PixelFormatGrey(bpp = 8)")

    def test_palette(self):
        with self.assertRaises(KeyError) as ecm:
            _ = PixelFormatPalette({})
        self.assertEqual(
            ecm.exception.args,
            ((0, 0, 0),)
        )
        data = {(i, j, k): i + 7 * j + 37 + k for i in range(6) for j in range(6) for k in range(6)}
        pf = PixelFormatPalette(data)
        data_repr = (f'{k!r}: 0x{v:02x}' for k, v in sorted(data.items()))
        data_repr = ', '.join(data_repr)
        self.assertEqual(
            repr(pf),
            f'djvu.decode.PixelFormatPalette({{{data_repr}}}, bpp = 8)'
        )

    def test_packed_bits(self):
        pf = PixelFormatPackedBits('<')
        self.assertRepr(pf, "djvu.decode.PixelFormatPackedBits('<')")
        self.assertEqual(pf.bpp, 1)
        pf = PixelFormatPackedBits('>')
        self.assertRepr(pf, "djvu.decode.PixelFormatPackedBits('>')")
        self.assertEqual(pf.bpp, 1)


class PageJobsTestCase(TestCase):

    def test_bad_new(self):
        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.PageJob' instances"):
            PageJob()

    def test_decode(self):
        context = Context()
        document = context.new_document(FileUri(IMAGES + 'test1.djvu'))
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        page_job = document.pages[0].decode()
        self.assertTrue(page_job.is_done)
        self.assertIsInstance(page_job, PageJob)
        self.assertTrue(page_job.is_done)
        self.assertFalse(page_job.is_error)
        self.assertEqual(page_job.status, JobOK)
        self.assertEqual(page_job.width, 64)
        self.assertEqual(page_job.height, 48)
        self.assertEqual(page_job.size, (64, 48))
        self.assertEqual(page_job.dpi, 300)
        self.assertEqual(page_job.gamma, 2.2)
        self.assertEqual(page_job.version, 24)
        self.assertEqual(page_job.type, PAGE_TYPE_BITONAL)
        self.assertEqual((page_job.rotation, page_job.initial_rotation), (0, 0))
        with self.assertRaisesString(ValueError, 'rotation must be equal to 0, 90, 180, or 270'):
            page_job.rotation = 100
        page_job.rotation = 180
        self.assertEqual((page_job.rotation, page_job.initial_rotation), (180, 0))
        del page_job.rotation
        self.assertEqual((page_job.rotation, page_job.initial_rotation), (0, 0))

        with self.assertRaisesString(ValueError, 'page_rect width/height must be a positive integer'):
            page_job.render(RENDER_COLOR, (0, 0, -1, -1), (0, 0, 10, 10), PixelFormatRgb())

        with self.assertRaisesString(ValueError, 'render_rect width/height must be a positive integer'):
            page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, -1, -1), PixelFormatRgb())

        with self.assertRaisesString(ValueError, 'render_rect must be inside page_rect'):
            page_job.render(RENDER_COLOR, (0, 0, 10, 10), (2, 2, 10, 10), PixelFormatRgb())

        if sys.maxsize > (1 << 32):
            with self.assertRaisesString(ValueError, 'render_rect must be inside page_rect'):
                page_job.render(RENDER_COLOR, (0, 0, 10, 10), (2, 2, 0xFFFFFFFF, 1), PixelFormatRgb())
        else:
            with self.assertRaisesString(OverflowError, 'Python int too large to convert to C long'):
                page_job.render(RENDER_COLOR, (0, 0, 10, 10), (2, 2, 0xFFFFFFFF, 1), PixelFormatRgb())

        with self.assertRaisesString(ValueError, 'row_alignment must be a positive integer'):
            page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 10, 10), PixelFormatRgb(), -1)

        with self.assertRaisesRegex(MemoryError, r'\AUnable to allocate [0-9]+ bytes for an image memory\Z'):
            x = int((sys.maxsize // 2) ** 0.5)
            page_job.render(RENDER_COLOR, (0, 0, x, x), (0, 0, x, x), PixelFormatRgb(), 8)

        s = page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 4, 4), PixelFormatGrey(), 1)
        self.assertEqual(s, b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xEF\xFF\xFF\xFF\xA4\xFF\xFF\xFF\xB8')

        buffer = array.array('B', b'\0')
        with self.assertRaisesString(ValueError, 'Image buffer is too small (16 > 1)'):
            page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 4, 4), PixelFormatGrey(), 1, buffer)

        buffer = array.array('B', b'\0' * 16)
        self.assertIs(page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 4, 4), PixelFormatGrey(), 1, buffer), buffer)
        s = buffer.tobytes()
        self.assertEqual(s, b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xEF\xFF\xFF\xFF\xA4\xFF\xFF\xFF\xB8')

        buffer = array.array('I', [0] * 4)
        pixel_format = PixelFormatRgbMask(0xFF0000, 0xFF00, 0xFF, bpp=32)
        self.assertIs(page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 2, 2), pixel_format, 1, buffer), buffer)
        s = buffer.tobytes()
        self.assertEqual(s, b'\xFF\xFF\xFF\x00' * 4)

        if sys.version_info >= (3, 3):
            buffer = bytearray(16)
            memview = memoryview(buffer).cast('I', shape=(2, 2))
            self.assertIs(
                page_job.render(RENDER_COLOR, (0, 0, 10, 10), (0, 0, 2, 2), pixel_format, 1, memview),
                memview
            )
            s = bytes(buffer)
            self.assertEqual(s, b'\xFF\xFF\xFF\x00' * 4)


class ThumbnailsTestCase(TestCase):

    def test(self):
        context = Context()
        document = context.new_document(FileUri(IMAGES + 'test1.djvu'))
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        thumbnail = document.pages[0].thumbnail
        self.assertEqual(thumbnail.status, JobOK)
        self.assertEqual(thumbnail.calculate(), JobOK)
        message = document.get_message()
        self.assertIsInstance(message, ThumbnailMessage)
        self.assertEqual(message.thumbnail.page.n, 0)
        (w, h, r), pixels = thumbnail.render((5, 5), PixelFormatGrey(), dry_run=True)
        self.assertEqual((w, h, r), (5, 3, 5))
        self.assertIs(pixels, None)
        (w, h, r), pixels = thumbnail.render((5, 5), PixelFormatGrey())
        self.assertEqual((w, h, r), (5, 3, 5))
        self.assertEqual(pixels[:15], b'\xFF\xEB\xA7\xF2\xFF\xFF\xBF\x86\xBE\xFF\xFF\xE7\xD6\xE7\xFF')
        buffer = array.array('B', b'\0')
        with self.assertRaisesString(ValueError, 'Image buffer is too small (25 > 1)'):
            _ = thumbnail.render((5, 5), PixelFormatGrey(), buffer=buffer)
        buffer = array.array('B', b'\0' * 25)
        (w, h, r), pixels = thumbnail.render((5, 5), PixelFormatGrey(), buffer=buffer)
        self.assertIs(pixels, buffer)
        s = buffer[:15].tobytes()
        self.assertEqual(s, b'\xFF\xEB\xA7\xF2\xFF\xFF\xBF\x86\xBE\xFF\xFF\xE7\xD6\xE7\xFF')


class JobsTestCase(TestCase):

    def test_jobs(self):
        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.Job' instances"):
            Job()

        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.DocumentDecodingJob' instances"):
            DocumentDecodingJob()


class AffineTransformsTestCase(TestCase):

    def test_bad_args(self):
        with self.assertRaisesString(ValueError, 'need more than 2 values to unpack'):
            AffineTransform((1, 2), (3, 4, 5))

    def test1(self):
        af = AffineTransform((0, 0, 10, 10), (17, 42, 42, 100))
        self.assertIsInstance(af, AffineTransform)
        self.assertEqual(af((0, 0)), (17, 42))
        self.assertEqual(af((0, 10)), (17, 142))
        self.assertEqual(af((10, 0)), (59, 42))
        self.assertEqual(af((10, 10)), (59, 142))
        self.assertEqual(af((0, 0, 10, 10)), (17, 42, 42, 100))
        self.assertEqual(af(x for x in (0, 0, 10, 10)), (17, 42, 42, 100))
        self.assertEqual(af.apply((123, 456)), af((123, 456)))
        self.assertEqual(af.apply((12, 34, 56, 78)), af((12, 34, 56, 78)))
        self.assertEqual(af.inverse((17, 42)), (0, 0))
        self.assertEqual(af.inverse((17, 142)), (0, 10))
        self.assertEqual(af.inverse((59, 42)), (10, 0))
        self.assertEqual(af.inverse((59, 142)), (10, 10))
        self.assertEqual(af.inverse((17, 42, 42, 100)), (0, 0, 10, 10))
        self.assertEqual(af.inverse(x for x in (17, 42, 42, 100)), (0, 0, 10, 10))
        self.assertEqual(af.inverse(af((234, 567))), (234, 567))
        self.assertEqual(af.inverse(af((23, 45, 67, 78))), (23, 45, 67, 78))


class MessagesTestCase(TestCase):

    def test_bad_new(self):
        with self.assertRaisesString(TypeError, "cannot create 'djvu.decode.Message' instances"):
            Message()


class StreamsTestCase(TestCase):

    def test_bad_new(self):
        with self.assertRaisesString(TypeError, "Argument 'document' has incorrect type (expected djvu.decode.Document, got NoneType)"):
            Stream(None, 42)

    def test(self):
        context = Context()
        document = context.new_document('dummy://dummy.djvu')
        message = document.get_message()
        self.assertIsInstance(message, NewStreamMessage)
        self.assertEqual(message.name, 'dummy.djvu')
        self.assertEqual(message.uri, 'dummy://dummy.djvu')
        self.assertIsInstance(message.stream, Stream)
        with self.assertRaises(NotAvailable):
            _ = document.outline.sexpr
        with self.assertRaises(NotAvailable):
            _ = document.annotations.sexpr
        with self.assertRaises(NotAvailable):
            _ = document.pages[0].text.sexpr
        with self.assertRaises(NotAvailable):
            _ = document.pages[0].annotations.sexpr
        try:
            with open(IMAGES + 'test1.djvu', 'rb') as fp:
                message.stream.write(fp.read())
        finally:
            message.stream.close()
        with self.assertRaisesString(IOError, 'I/O operation on closed file'):
            message.stream.write(b'eggs')
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        outline = document.outline
        outline.wait()
        x = outline.sexpr
        self.assertEqual(x, Expression([]))
        anno = document.annotations
        anno.wait()
        x = anno.sexpr
        self.assertEqual(x, Expression([]))
        text = document.pages[0].text
        text.wait()
        x = text.sexpr
        self.assertEqual(x, Expression([]))
        anno = document.pages[0].annotations
        anno.wait()
        x = anno.sexpr
        self.assertEqual(x, Expression([]))


class MetadataTestCase(DecodeTestCase):
    def test_metadata(self):
        model_metadata = {
            'English': 'eggs',
            'Русский': 'яйца',
        }
        meta = (f'|{k}| {v}' for k, v in model_metadata.items())
        meta = '\n'.join(meta)
        test_script = f'set-meta\n{meta}\n.\n'
        try:
            test_file = self.create_djvu(test_script)
        except UnicodeEncodeError:
            raise self.SkipTest('you need to run this test with LC_CTYPE=C or LC_CTYPE=<lang>.UTF-8')
        try:
            context = Context()
            document = context.new_document(FileUri(test_file.name))
            message = document.get_message()
            self.assertIsInstance(message, DocInfoMessage)
            annotations = document.annotations
            self.assertIsInstance(annotations, DocumentAnnotations)
            annotations.wait()
            metadata = annotations.metadata
            self.assertIsInstance(metadata, Metadata)
            self.assertEqual(len(metadata), len(model_metadata))
            self.assertEqual(sorted(metadata), sorted(model_metadata))
            self.assertEqual(sorted(metadata.keys()), sorted(model_metadata.keys()))
            self.assertEqual(sorted(metadata.values()), sorted(model_metadata.values()))
            self.assertEqual(sorted(metadata.items()), sorted(model_metadata.items()))
            for k in metadata:
                self.assertIsInstance(k, str)
                self.assertIsInstance(metadata[k], str)
            for k in None, 42, '+'.join(model_metadata):
                with self.assertRaises(KeyError) as ecm:
                    _ = metadata[k]
                self.assertEqual(ecm.exception.args, (k,))
        finally:
            test_file.close()


class SexprTestCase(TestCase):

    def test(self):
        context = Context()
        document = context.new_document(FileUri(IMAGES + 'test0.djvu'))
        self.assertIsInstance(document, Document)
        message = document.get_message()
        self.assertIsInstance(message, DocInfoMessage)
        anno = DocumentAnnotations(document, shared=False)
        self.assertIsInstance(anno, DocumentAnnotations)
        anno.wait()
        x = anno.sexpr
        self.assertEqual(x, Expression([]))
        anno = document.annotations
        self.assertIsInstance(anno, DocumentAnnotations)
        anno.wait()
        self.assertIs(anno.background_color, None)
        self.assertIs(anno.horizontal_align, None)
        self.assertIs(anno.vertical_align, None)
        self.assertIs(anno.mode, None)
        self.assertIs(anno.zoom, None)
        expected_metadata = [
            Symbol('metadata'),
            [Symbol('ModDate'), '2015-08-17 19:54:57+02:00'],
            [Symbol('CreationDate'), '2015-08-17 19:54:57+02:00'],
            [Symbol('Producer'), 'pdfTeX-1.40.16'],
            [Symbol('Creator'), 'LaTeX with hyperref package'],
            [Symbol('Author'), 'Jakub Wilk']
        ]
        expected_xmp = [
            Symbol('xmp'),
            (
                '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                '<rdf:Description rdf:about="">'
                '<xmpMM:History xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"><rdf:Seq><rdf:li xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#" stEvt:action="converted" stEvt:parameters="from application/pdf to image/vnd.djvu" stEvt:softwareAgent="pdf2djvu 0.8.1 (DjVuLibre 3.5.27, Poppler 0.26.5, GraphicsMagick++ 1.3.21, GNOME XSLT 1.1.28, GNOME XML 2.9.2, PStreams 0.8.0)" stEvt:when="2015-08-17T17:54:58+00:00"/></rdf:Seq></xmpMM:History>'  # noqa: E501
                '<dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Jakub Wilk</dc:creator>'
                '<dc:format xmlns:dc="http://purl.org/dc/elements/1.1/">image/vnd.djvu</dc:format>'
                '<pdf:Producer xmlns:pdf="http://ns.adobe.com/pdf/1.3/">pdfTeX-1.40.16</pdf:Producer>'
                '<xmp:CreatorTool xmlns:xmp="http://ns.adobe.com/xap/1.0/">LaTeX with hyperref package</xmp:CreatorTool>'
                '<xmp:CreateDate xmlns:xmp="http://ns.adobe.com/xap/1.0/">2015-08-17T19:54:57+02:00</xmp:CreateDate>'
                '<xmp:ModifyDate xmlns:xmp="http://ns.adobe.com/xap/1.0/">2015-08-17T19:54:57+02:00</xmp:ModifyDate>'
                '<xmp:MetadataDate xmlns:xmp="http://ns.adobe.com/xap/1.0/">2015-08-17T17:54:58+00:00</xmp:MetadataDate>'
                '</rdf:Description>'
                '</rdf:RDF>\n'
            )
        ]
        self.assertEqual(
            anno.sexpr,
            Expression([expected_metadata, expected_xmp])
        )
        metadata = anno.metadata
        self.assertIsInstance(metadata, Metadata)
        hyperlinks = anno.hyperlinks
        self.assertIsInstance(hyperlinks, Hyperlinks)
        self.assertEqual(len(hyperlinks), 0)
        self.assertEqual(list(hyperlinks), [])
        outline = document.outline
        self.assertIsInstance(outline, DocumentOutline)
        outline.wait()
        self.assertEqual(
            outline.sexpr,
            Expression([
                Symbol('bookmarks'),
                ['Lorem ipsum', '#p0001.djvu'],
                [
                    'Hyperlinks', '#p0002.djvu',
                    ['local', '#p0002.djvu'],
                    ['remote', '#p0002.djvu']
                ]
            ])
        )
        page = document.pages[1]
        anno = page.annotations
        self.assertIsInstance(anno, PageAnnotations)
        anno.wait()
        self.assertIs(anno.background_color, None)
        self.assertIs(anno.horizontal_align, None)
        self.assertIs(anno.vertical_align, None)
        self.assertIs(anno.mode, None)
        self.assertIs(anno.zoom, None)
        expected_hyperlinks = [
            [Symbol('maparea'), '#p0001.djvu', '', [Symbol('rect'), 520, 2502, 33, 42], [Symbol('border'), Symbol('#ff0000')]],
            [Symbol('maparea'), 'http://jwilk.net/', '', [Symbol('rect'), 458, 2253, 516, 49], [Symbol('border'), Symbol('#00ffff')]]
        ]
        self.assertEqual(
            anno.sexpr,
            Expression([expected_metadata, expected_xmp] + expected_hyperlinks)
        )
        page_metadata = anno.metadata
        self.assertIsInstance(page_metadata, Metadata)
        self.assertEqual(page_metadata.keys(), metadata.keys())
        self.assertEqual([page_metadata[k] == metadata[k] for k in metadata], [True, True, True, True, True])
        hyperlinks = anno.hyperlinks
        self.assertIsInstance(hyperlinks, Hyperlinks)
        self.assertEqual(len(hyperlinks), 2)
        self.assertEqual(
            list(hyperlinks),
            [Expression(h) for h in expected_hyperlinks]
        )
        text = page.text
        self.assertIsInstance(text, PageText)
        text.wait()
        text_s = text.sexpr
        text_s_detail = [
            PageText(page, details).sexpr
            for details in (
                TEXT_DETAILS_PAGE, TEXT_DETAILS_COLUMN, TEXT_DETAILS_REGION, TEXT_DETAILS_PARAGRAPH, TEXT_DETAILS_LINE, TEXT_DETAILS_WORD,
                TEXT_DETAILS_CHARACTER, TEXT_DETAILS_ALL
            )
        ]
        self.assertEqual(text_s_detail[0], text_s_detail[1])
        self.assertEqual(text_s_detail[1], text_s_detail[2])
        self.assertEqual(text_s_detail[2], text_s_detail[3])
        self.assertEqual(
            text_s_detail[0],
            Expression([
                Symbol('page'), 0, 0, 2550, 3300,
                (
                    '2 Hyperlinks \n'
                    '2.1 local \n'
                    '→1 \n'
                    '2.2 remote \nhttp://jwilk.net/ \n'
                    '2 \n'
                )
            ])
        )
        self.assertEqual(
            text_s_detail[4],
            Expression([
                Symbol('page'), 0, 0, 2550, 3300,
                [Symbol('line'), 462, 2712, 910, 2777, '2 Hyperlinks '],
                [Symbol('line'), 462, 2599, 714, 2641, '2.1 local '],
                [Symbol('line'), 464, 2505, 544, 2540, '→1 '],
                [Symbol('line'), 462, 2358, 772, 2400, '2.2 remote '],
                [Symbol('line'), 463, 2256, 964, 2298, 'http://jwilk.net/ '],
                [Symbol('line'), 1260, 375, 1282, 409, '2 ']
            ])
        )
        self.assertEqual(text_s_detail[5], text_s)
        self.assertEqual(text_s_detail[6], text_s)
        self.assertEqual(text_s_detail[7], text_s)
        self.assertEqual(
            text_s,
            Expression([
                Symbol('page'), 0, 0, 2550, 3300,
                [
                    Symbol('line'), 462, 2712, 910, 2777, [Symbol('word'), 462, 2727, 495, 2776, '2'],
                    [Symbol('word'), 571, 2712, 910, 2777, 'Hyperlinks']
                ],
                [
                    Symbol('line'), 462, 2599, 714, 2641, [Symbol('word'), 462, 2599, 532, 2641, '2.1'],
                    [Symbol('word'), 597, 2599, 714, 2640, 'local']
                ],
                [Symbol('line'), 464, 2505, 544, 2540, [Symbol('word'), 464, 2505, 544, 2540, '→1']],
                [
                    Symbol('line'), 462, 2358, 772, 2400, [Symbol('word'), 462, 2358, 535, 2400, '2.2'],
                    [Symbol('word'), 598, 2358, 772, 2397, 'remote']
                ],
                [Symbol('line'), 463, 2256, 964, 2298, [Symbol('word'), 463, 2256, 964, 2298, 'http://jwilk.net/']],
                [Symbol('line'), 1260, 375, 1282, 409, [Symbol('word'), 1260, 375, 1282, 409, '2']]
            ])
        )
        with self.assertRaisesString(TypeError, 'details must be a symbol or none'):
            PageText(page, 'eggs')
        with self.assertRaisesString(
                ValueError,
                (
                    'details must be equal to TEXT_DETAILS_PAGE, or TEXT_DETAILS_COLUMN, or TEXT_DETAILS_REGION, or TEXT_DETAILS_PARAGRAPH,'
                    ' or TEXT_DETAILS_LINE, or TEXT_DETAILS_WORD, or TEXT_DETAILS_CHARACTER or TEXT_DETAILS_ALL'
                )
        ):
            PageText(page, Symbol('eggs'))


class VersionTestCase(TestCase):
    def test_version(self):
        self.assertIsInstance(__version__, str)
        self.assertEqual(__version__, get_changelog_version())
        self.assertIsInstance(DDJVU_VERSION, int)


class WildcardImportTestCase(TestCase):
    def test_wildcard_import(self):
        namespace = wildcard_import('djvu.decode')
        self.assertListEqual(
            sorted(namespace.keys()),
            [
                'AffineTransform',
                'Annotations',
                'ChunkMessage',
                'Context',
                'DDJVU_VERSION',
                'DOCUMENT_TYPE_BUNDLED',
                'DOCUMENT_TYPE_INDIRECT',
                'DOCUMENT_TYPE_OLD_BUNDLED',
                'DOCUMENT_TYPE_OLD_INDEXED',
                'DOCUMENT_TYPE_SINGLE_PAGE',
                'DOCUMENT_TYPE_UNKNOWN',
                'DocInfoMessage',
                'Document',
                'DocumentAnnotations',
                'DocumentDecodingJob',
                'DocumentExtension',
                'DocumentFiles',
                'DocumentOutline',
                'DocumentPages',
                'ErrorMessage',
                'FILE_TYPE_INCLUDE',
                'FILE_TYPE_PAGE',
                'FILE_TYPE_THUMBNAILS',
                'File',
                'FileURI',
                'FileUri',
                'Hyperlinks',
                'InfoMessage',
                'Job',
                'JobDone',
                'JobException',
                'JobFailed',
                'JobNotDone',
                'JobNotStarted',
                'JobOK',
                'JobStarted',
                'JobStopped',
                'Message',
                'Metadata',
                'NewStreamMessage',
                'NotAvailable',
                'PAGE_TYPE_BITONAL',
                'PAGE_TYPE_COMPOUND',
                'PAGE_TYPE_PHOTO',
                'PAGE_TYPE_UNKNOWN',
                'PRINT_BOOKLET_NO',
                'PRINT_BOOKLET_RECTO',
                'PRINT_BOOKLET_VERSO',
                'PRINT_BOOKLET_YES',
                'PRINT_ORIENTATION_AUTO',
                'PRINT_ORIENTATION_LANDSCAPE',
                'PRINT_ORIENTATION_PORTRAIT',
                'Page',
                'PageAnnotations',
                'PageInfoMessage',
                'PageJob',
                'PageText',
                'PixelFormat',
                'PixelFormatGrey',
                'PixelFormatPackedBits',
                'PixelFormatPalette',
                'PixelFormatRgb',
                'PixelFormatRgbMask',
                'ProgressMessage',
                'RENDER_BACKGROUND',
                'RENDER_BLACK',
                'RENDER_COLOR',
                'RENDER_COLOR_ONLY',
                'RENDER_FOREGROUND',
                'RENDER_MASK_ONLY',
                'RedisplayMessage',
                'RelayoutMessage',
                'SaveJob',
                'Stream',
                'TEXT_DETAILS_ALL',
                'TEXT_DETAILS_CHARACTER',
                'TEXT_DETAILS_COLUMN',
                'TEXT_DETAILS_LINE',
                'TEXT_DETAILS_PAGE',
                'TEXT_DETAILS_PARAGRAPH',
                'TEXT_DETAILS_REGION',
                'TEXT_DETAILS_WORD',
                'Thumbnail',
                'ThumbnailMessage',
                'cmp_text_zone'
            ]
        )

# vim:ts=4 sts=4 sw=4 et
