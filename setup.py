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

'''
*python-djvulibre* is a set of Python bindings for
the `DjVuLibre <http://djvu.sourceforge.net/>`_ library,
an open source implementation of `DjVu <http://djvu.org/>`_.
'''

import glob
import io
import os
import re
import subprocess as ipc
import sys

import setuptools
from packaging.version import Version, parse as parse_version
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.command.sdist import sdist as _sdist
from wheel.bdist_wheel import bdist_wheel

try:
    import sphinx.setup_command as sphinx_setup_command
except ImportError:
    sphinx_setup_command = None


class PackageVersionError(Exception):
    pass


def ext_modules():
    for pyx_file in glob.iglob(os.path.join('djvu', '*.pyx')):
        module, _ = os.path.splitext(os.path.basename(pyx_file))
        yield module

ext_modules = list(ext_modules())


def get_version():
    path = os.path.join(os.path.dirname(__file__), 'doc', 'changelog')
    with open(path, encoding='UTF-8') as fd:
        line = fd.readline()
    return line.split()[1].strip('()')


py_version = get_version()


def run_pkgconfig(*cmdline):
    cmdline = ['pkg-config'] + list(cmdline)
    try:
        pkgconfig = ipc.Popen(
            cmdline,
            stdout=ipc.PIPE, stderr=ipc.PIPE
        )
    except EnvironmentError as exc:
        msg = 'cannot execute pkg-config: {exc.strerror}'.format(exc=exc)
        print(msg)
        return
    stdout, stderr = pkgconfig.communicate()
    stdout = stdout.decode('ASCII')
    stderr = stderr.decode('ASCII', 'replace')
    if pkgconfig.returncode != 0:
        print('pkg-config failed:')
        for line in stderr.splitlines():
            print('  ' + line)
        return
    return stdout


def pkgconfig_build_flags(*packages, **kwargs):
    flag_map = {
        '-I': 'include_dirs',
        '-L': 'library_dirs',
        '-l': 'libraries',
    }
    fallback = dict(
        libraries=['djvulibre'],
    )

    stdout = run_pkgconfig('--libs', '--cflags', *packages)
    if stdout is None:
        return fallback
    kwargs.setdefault('extra_link_args', [])
    kwargs.setdefault('extra_compile_args', [])
    for argument in stdout.split():
        key = argument[:2]
        try:
            value = argument[2:]
            kwargs.setdefault(flag_map[key], []).append(value)
        except KeyError:
            kwargs['extra_link_args'].append(argument)
            kwargs['extra_compile_args'].append(argument)
    return kwargs


def pkgconfig_version(package):
    stdout = run_pkgconfig('--modversion', package)
    if stdout is None:
        return
    return stdout.strip()


def get_djvulibre_version():
    version = pkgconfig_version('ddjvuapi')
    if version is None:
        raise PackageVersionError('cannot determine DjVuLibre version')
    version = version or '0'
    return Version(version)


class build_ext(_build_ext):

    def run(self):
        djvulibre_version = get_djvulibre_version()
        if djvulibre_version != Version('0') and djvulibre_version < Version('3.5.21'):
            raise PackageVersionError('DjVuLibre >= 3.5.21 is required')
        compiler_flags = pkgconfig_build_flags('ddjvuapi')
        for extension in self.extensions:
            for attr, flags in compiler_flags.items():
                getattr(extension, attr)
                setattr(extension, attr, flags)
        new_config = [
            'DEF PY3K = {0}'.format(sys.version_info >= (3, 0)),  # TODO: Drop.
            'DEF PYTHON_DJVULIBRE_VERSION = b"{0}"'.format(py_version),
            'DEF HAVE_MINIEXP_IO_T = {0}'.format(djvulibre_version >= Version('3.5.26')),
        ]
        self.src_dir = src_dir = os.path.join(self.build_temp, 'src')
        os.makedirs(src_dir, exist_ok=True)
        self.config_path = os.path.join(src_dir, 'config.pxi')
        try:
            with open(self.config_path, 'rt') as fp:
                old_config = fp.read()
        except IOError:
            old_config = ''
        new_config = '\n'.join(new_config)
        if new_config.strip() != old_config.strip():
            print('creating {conf!r}'.format(conf=self.config_path))
            with open(self.config_path, mode='w') as fd:
                fd.write(new_config)
        _build_ext.run(self)

    def build_extensions(self):
        self.check_extensions_list(self.extensions)
        for ext in self.extensions:
            ext.sources = list(self.cython_sources(ext))
            self.build_extension(ext)

    def cython_sources(self, ext):
        for source in ext.sources:
            source_base = os.path.basename(source)
            target = os.path.join(
                self.src_dir,
                '{mod}.c'.format(mod=source_base[:-4])
            )
            yield target
            depends = [source, self.config_path] + ext.depends
            print('cythoning {ext.name!r} extension'.format(ext=ext))
            def build_c(source, target):
                ipc.run([
                    sys.executable, '-m', 'cython',
                    '-I', os.path.dirname(self.config_path),
                    '-o', target,
                    source,
                ])
            self.make_file(depends, target, build_c, [source, target])


if sphinx_setup_command:
    class build_sphinx(sphinx_setup_command.BuildDoc):
        def run(self):
            # Make sure that djvu module is imported from the correct
            # directory.
            #
            # The current directory (which is normally in sys.path[0]) is
            # typically a wrong choice: it contains djvu/__init__.py but not
            # the extension modules. Prepend the directory that build_ext would
            # use instead.
            build_ext = self.get_finalized_command('build_ext')
            sys.path[:0] = [build_ext.build_lib]
            for ext in ext_modules:
                __import__('djvu.' + ext)
            del sys.path[0]
            sphinx_setup_command.BuildDoc.run(self)
else:
    build_sphinx = None


class sdist(_sdist):

    def maybe_move_file(self, base_dir, src, dst):
        src = os.path.join(base_dir, src)
        dst = os.path.join(base_dir, dst)
        if os.path.exists(src):
            self.move_file(src, dst)

    def make_release_tree(self, base_dir, files):
        _sdist.make_release_tree(self, base_dir, files)
        self.maybe_move_file(base_dir, 'COPYING', 'doc/COPYING')

classifiers = '''
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: GNU General Public License (GPL)
Operating System :: POSIX
Programming Language :: Cython
Programming Language :: Python
Programming Language :: Python :: 3
Topic :: Multimedia :: Graphics
Topic :: Multimedia :: Graphics :: Graphics Conversion
Topic :: Text Processing
'''.strip().splitlines()

meta = dict(
    name='python-djvulibre',
    version=py_version,
    author='Jakub Wilk, FriedrichFröbel (fork)',
    author_email='jwilk@jwilk.net',
    license='GNU GPL 2',
    description='Python support for the DjVu image format',
    long_description=__doc__.strip(),
    classifiers=classifiers,
    url='https://jwilk.net/software/python-djvulibre',
)

setup_params = dict(
    packages=['djvu'],
    ext_modules=[
        setuptools.Extension(
            'djvu.{mod}'.format(mod=name),
            ['djvu/{mod}.pyx'.format(mod=name)],
            depends=(['djvu/common.pxi'] + glob.glob('djvu/*.pxd')),
        )
        for name in ext_modules
    ],
    cmdclass=dict(
        (cmd.__name__, cmd)
        for cmd in (build_ext, build_sphinx, sdist, bdist_wheel)
        if cmd is not None
    ),
    py_modules=['djvu.const'],
    **meta
)

setuptools.setup(**setup_params)

# vim:ts=4 sts=4 sw=4 et
