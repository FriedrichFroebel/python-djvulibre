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

"""
*python-djvulibre* is a set of Python bindings for
the `DjVuLibre <https://djvu.sourceforge.net/>`_ library,
an open source implementation of `DjVu <http://djvu.org/>`_.
"""

import glob
import logging
import os
import subprocess as ipc
import sys

import setuptools
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.command.sdist import sdist as _sdist
from wheel.bdist_wheel import bdist_wheel

logger = logging.getLogger(__name__)
del logging


class PackageVersionError(Exception):
    pass


def get_ext_modules():
    for pyx_file in glob.iglob(os.path.join('djvu', '*.pyx')):
        module, _ = os.path.splitext(os.path.basename(pyx_file))
        yield module


ext_modules = list(get_ext_modules())


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
        msg = f'cannot execute pkg-config: {exc.strerror}'
        logger.warning(msg)
        return
    stdout, stderr = pkgconfig.communicate()
    stdout = stdout.decode('ASCII')
    stderr = stderr.decode('ASCII', 'replace')
    if pkgconfig.returncode != 0:
        logger.warning('pkg-config failed:')
        for line in stderr.splitlines():
            logger.warning('  ' + line)
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
    from packaging.version import Version
    return Version(version)


CONFIG_TEMPLATE = """
cdef extern from *:
    \"\"\"
    #define PYTHON_DJVULIBRE_VERSION "{py_version}"
    \"\"\"

    extern const char* PYTHON_DJVULIBRE_VERSION
"""


class BuildExtension(_build_ext):
    name = 'build_ext'

    def run(self):
        djvulibre_version = get_djvulibre_version()
        from packaging.version import Version
        if djvulibre_version != Version('0') and djvulibre_version < Version('3.5.26'):
            raise PackageVersionError('DjVuLibre >= 3.5.26 is required')
        compiler_flags = pkgconfig_build_flags('ddjvuapi')
        for extension in self.extensions:
            for attr, flags in compiler_flags.items():
                getattr(extension, attr)
                setattr(extension, attr, flags)
        new_config = CONFIG_TEMPLATE.format(
            py_version=py_version,
        )
        self.src_dir = src_dir = os.path.join(self.build_temp, 'src')
        os.makedirs(src_dir, exist_ok=True)
        self.config_path = os.path.join(src_dir, 'config.pxi')
        try:
            with open(self.config_path, 'rt') as fp:
                old_config = fp.read()
        except IOError:
            old_config = ''
        if new_config.strip() != old_config.strip():
            logger.info(f'creating {self.config_path!r}')
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
                f'{source_base[:-4]}.c'
            )
            yield target
            depends = [source, self.config_path] + ext.depends
            logger.debug(f'cythonizing {ext.name!r} extension')

            def build_c(source_, target_):
                ipc.run([
                    sys.executable, '-m', 'cython',
                    '-I', os.path.dirname(self.config_path),
                    '-o', target_,
                    source_,
                ])

            self.make_file(depends, target, build_c, [source, target])


class Sdist(_sdist):
    name = 'sdist'

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
    license='GNU GPL 2',
    description='Python support for the DjVu image format',
    long_description=__doc__.strip(),
    classifiers=classifiers,
    url='https://github.com/FriedrichFroebel/python-djvulibre',
)

setup_params = dict(
    packages=['djvu'],
    ext_modules=[
        setuptools.Extension(
            f'djvu.{name}',
            [f'djvu/{name}.pyx'],
            depends=(['djvu/common.pxi'] + glob.glob('djvu/*.pxd')),
        )
        for name in ext_modules
    ],
    cmdclass=dict(
        (cmd.__name__ if not hasattr(cmd, 'name') else cmd.name, cmd)
        for cmd in (BuildExtension, Sdist, bdist_wheel)
        if cmd is not None
    ),
    py_modules=['djvu.const'],
    extras_require={
        'dev': [
            'flake8',
            'pep8-naming',
        ],
    },
    **meta
)


if __name__ == '__main__':
    # Required for Sphinx.
    setuptools.setup(**setup_params)

# vim:ts=4 sts=4 sw=4 et
