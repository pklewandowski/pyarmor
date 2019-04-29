#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
#############################################################
#                                                           #
#      Copyright @ 2018 -  Dashingsoft corp.                #
#      All rights reserved.                                 #
#                                                           #
#      pyarmor                                              #
#                                                           #
#      Version: 4.3.2 -                                     #
#                                                           #
#############################################################
#
#
#  @File: packer.py
#
#  @Author: Jondy Zhao(jondy.zhao@gmail.com)
#
#  @Create Date: 2018/11/08
#
#  @Description:
#
#   Pack obfuscated Python scripts with any of third party
#   tools: py2exe, py2app, cx_Freeze
#

'''Pack obfuscated scripts to one bundle, distribute the
bundle as a folder or file to other people, and they can
execute your program without Python installed.

The prefer way is

    pip install pyinstaller
    cd /path/to/src
    parmor pack hello.py

'''

import logging
import os
import shutil
import subprocess
import sys

from distutils.util import get_platform
from glob import glob
from py_compile import compile as compile_file
from shlex import split
from zipfile import PyZipFile


try:
    import argparse
except ImportError:
    # argparse is new in version 2.7
    import polyfills.argparse as argparse

# Default output path, library name, command options for setup script
DEFAULT_PACKER = {
    'py2app': ('dist', 'library.zip', ['py2app', '--dist-dir']),
    'py2exe': ('dist', 'library.zip', ['py2exe', '--dist-dir']),
    'PyInstaller': ('dist', '', ['-m', 'PyInstaller', '--distpath']),
    'cx_Freeze': (
        os.path.join(
            'build', 'exe.%s-%s' % (get_platform(), sys.version[0:3])),
        'python%s%s.zip' % sys.version_info[:2],
        ['build', '--build-exe'])
}


def logaction(func):
    def wrap(*args, **kwargs):
        logging.info('%s', func.__name__)
        return func(*args, **kwargs)
    return wrap


def run_command(cmdlist):
    logging.info('\n\n%s\n\n', ' '.join(cmdlist))
    if sys.flags.debug:
        p = subprocess.Popen(cmdlist)
    else:
        p = subprocess.Popen(cmdlist, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    output, _ = p.communicate()

    if p.returncode != 0:
        if not sys.flags.debug:
            logging.error('\n\n%s\n\n', output.decode())
        raise RuntimeError('Run command failed')


def relpath(path, start=os.curdir):
    try:
        return os.path.relpath(path, start)
    except Exception:
        return path


@logaction
def update_library(obfdist, libzip):
    '''Update compressed library generated by py2exe or cx_Freeze, replace
the original scripts with obfuscated ones.

    '''
    # # It's simple ,but there are duplicated .pyc files
    # with PyZipFile(libzip, 'a') as f:
    #     f.writepy(obfdist)
    filelist = []
    for root, dirs, files in os.walk(obfdist):
        filelist.extend([os.path.join(root, s) for s in files])

    with PyZipFile(libzip, 'r') as f:
        namelist = f.namelist()
        f.extractall(obfdist)

    for s in filelist:
        if s.lower().endswith('.py'):
            compile_file(s, s + 'c')

    with PyZipFile(libzip, 'w') as f:
        for name in namelist:
            f.write(os.path.join(obfdist, name), name)


@logaction
def copy_runtime_files(runtimes, output):
    for s in glob(os.path.join(runtimes, '*.key')):
        shutil.copy(s, output)
    for s in glob(os.path.join(runtimes, '*.lic')):
        shutil.copy(s, output)
    for dllname in glob(os.path.join(runtimes, '_pytransform.*')):
        shutil.copy(dllname, output)


def pathwrapper(func):
    def wrap(*args, **kwargs):
        oldpath = os.getcwd()
        os.chdir(args[2])
        logging.info('Change current path to %s', os.getcwd())
        logging.info('-' * 50)
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(oldpath)
            logging.info('Restore current path to %s', oldpath)
            logging.info('%s\n', '-' * 50)
    return wrap


@pathwrapper
def run_setup_script(src, entry, build, script, packcmd, obfdist):
    '''Update entry script, copy pytransform.py to source path, then run
setup script to build the bundle.

    '''
    obf_entry = os.path.join(obfdist, entry)

    tempfile = '%s.armor.bak' % entry
    shutil.move(os.path.join(src, entry), tempfile)
    shutil.move(obf_entry, src)
    shutil.copy(os.path.join(obfdist, 'pytransform.py'), src)

    try:
        run_command([sys.executable, script] + packcmd)
    finally:
        shutil.move(tempfile, os.path.join(src, entry))
        os.remove(os.path.join(src, 'pytransform.py'))


def call_pyarmor(args):
    s = os.path.join(os.path.dirname(__file__), 'pyarmor.py')
    run_command([sys.executable, s] + list(args))


def _packer(t, src, entry, build, script, output, options, xoptions, clean):
    libname = DEFAULT_PACKER[t][1]
    packcmd = DEFAULT_PACKER[t][2] + [relpath(output, build)] + options
    script = 'setup.py' if script is None else script
    check_setup_script(t, os.path.join(build, script))
    if xoptions:
        logging.warning('-x, -xoptions are ignored')

    project = relpath(os.path.join(build, 'obf'))
    obfdist = os.path.join(project, 'dist')

    logging.info('obfuscated scrips output path: %s', obfdist)
    logging.info('build path: %s', project)
    if clean and os.path.exists(project):
        logging.info('Remove build path')
        shutil.rmtree(project)

    logging.info('Run PyArmor to create a project')
    call_pyarmor(['init', '-t', 'app', '--src', relpath(src),
                  '--entry', entry, project])

    logging.info('Run PyArmor to config the project')
    filters = ('global-include *.py', 'prune build, prune dist',
               'exclude %s pytransform.py' % entry)
    args = ('config', '--runtime-path', '',
            '--manifest', ','.join(filters), project)
    call_pyarmor(args)

    logging.info('Run PyArmor to build the project')
    call_pyarmor(['build', project])

    run_setup_script(src, entry, build, script, packcmd,
                     os.path.abspath(obfdist))

    update_library(obfdist, os.path.join(output, libname))

    copy_runtime_files(obfdist, output)


@logaction
def check_setup_script(_type, setup):
    if os.path.exists(setup):
        return

    logging.info('Please run the following command to generate setup.py')
    if _type == 'py2exe':
        logging.info('\tpython -m py2exe.build_exe -W setup.py hello.py')
    elif _type == 'cx_Freeze':
        logging.info('\tcxfreeze-quickstart')
    else:
        logging.info('\tvi setup.py')
    raise RuntimeError('No setup script %s found' % setup)


def run_pyi_makespec(project, obfdist, src, entry, packcmd):
    s = os.pathsep
    # d = os.path.relpath(obfdist, project)
    d = obfdist
    datas = [
        '--add-data', '%s%s.' % (os.path.join(d, 'license.lic'), s),
        '--add-data', '%s%s.' % (os.path.join(d, 'pytransform.key'), s),
        '--add-data', '%s%s.' % (os.path.join(d, '_pytransform.*'), s)
    ]
    scripts = [os.path.join(src, entry), os.path.join(obfdist, entry)]

    options = ['-y']
    options.extend(datas)
    options.extend(scripts)

    run_command([sys.executable] + packcmd + options)


def update_specfile(project, obfdist, src, entry, specfile):
    with open(specfile) as f:
        lines = f.readlines()

    patched_lines = (
        "", "# Patched by PyArmor",
        "a.scripts[-1] = '%s', r'%s', 'PYSOURCE'" % (
            entry[:-3], os.path.join(obfdist, entry)),
        "for i in range(len(a.pure)):",
        "    if a.pure[i][1].startswith(a.pathex[0]):",
        "        a.pure[i] = a.pure[i][0], a.pure[i][1].replace("
        "a.pathex[0], r'%s'), a.pure[i][2]" % os.path.abspath(obfdist),
        "# Patch end.", "", "")

    for i in range(len(lines)):
        if lines[i].startswith("pyz = PYZ(a.pure"):
            break
    else:
        raise RuntimeError('Unsupport specfile, no PYZ line found')
    lines[i:i] = '\n'.join(patched_lines)

    patched_file = specfile[:-5] + '-patched.spec'
    with open(patched_file, 'w') as f:
        f.writelines(lines)

    return os.path.normpath(patched_file)


def _pyinstaller(src, entry, output, specfile, options, xoptions, clean):
    src = relpath(src)
    output = relpath(output)
    packcmd = DEFAULT_PACKER['PyInstaller'][2] + [output] + options

    project = os.path.join(output, 'obf')
    obfdist = os.path.join(project, 'dist')
    if specfile is None:
        specfile = os.path.join(os.path.basename(entry)[:-3] + '.spec')

    logging.info('build path: %s', relpath(project))
    if clean and os.path.exists(project):
        logging.info('Remove build path')
        shutil.rmtree(project)

    logging.info('Run PyArmor to obfuscate scripts...')
    args = ['obfuscate', '-r', '-O', obfdist] + xoptions
    call_pyarmor(args + [os.path.join(src, entry)])

    if clean or (not os.path.exists(specfile)):
        logging.info('Run PyInstaller to generate .spec file...')
        run_pyi_makespec(project, obfdist, src, entry, packcmd)
        logging.info('Save .spec file to %s', specfile)
    else:
        logging.info('Use cached .spec file: %s', specfile)

    logging.info('Patching .spec file...')
    patched_spec = update_specfile(project, obfdist, src, entry, specfile)
    logging.info('Save patched .spec file to %s', patched_spec)

    logging.info('Run PyInstaller with patched .spec file...')
    run_command([sys.executable] + packcmd + ['-y', patched_spec])


def packer(args):
    t = args.type
    src = os.path.abspath(os.path.dirname(args.entry[0]))
    entry = os.path.basename(args.entry[0])
    extra_options = [] if args.options is None else split(args.options)
    xoptions = [] if args.xoptions is None else split(args.xoptions)

    if args.setup is None:
        build = src
        script = None
    else:
        build = os.path.abspath(os.path.dirname(args.setup))
        script = os.path.basename(args.setup)

    if args.output is None:
        dist = DEFAULT_PACKER[t][0]
        output = os.path.join(build, dist)
    else:
        output = args.output if os.path.isabs(args.output) \
            else os.path.join(build, args.output)
    output = os.path.normpath(output)

    logging.info('Prepare to pack obfuscated scripts with %s...', t)
    logging.info('entry script: %s', entry)
    logging.info('src for searching scripts: %s', relpath(src))

    if t == 'PyInstaller':
        _pyinstaller(src, entry, output, script,
                     extra_options, xoptions, args.clean)
    else:
        _packer(t, src, entry, build, script, output,
                extra_options, xoptions, args.clean)

    logging.info('Final output path: %s', relpath(output))
    logging.info('Pack obfuscated scripts successfully.')


def add_arguments(parser):
    parser.add_argument('-v', '--version', action='version', version='v0.1')

    parser.add_argument('-t', '--type', default='PyInstaller', metavar='TYPE',
                        choices=DEFAULT_PACKER.keys(),
                        help=', '.join(DEFAULT_PACKER.keys()))
    parser.add_argument('-s', '--setup', help=argparse.SUPPRESS)
    parser.add_argument('-O', '--output',
                        help='Directory to put final built distributions in')
    parser.add_argument('-e', '--options',
                        help='Extra options to run pack command')
    parser.add_argument('-x', '--xoptions',
                        help='Extra options to obfuscate scripts')
    parser.add_argument('--clean', action="store_true",
                        help='Remove build path before packing')
    parser.add_argument('entry', metavar='SCRIPT', nargs=1,
                        help='Entry script')


def main(args):
    parser = argparse.ArgumentParser(
        prog='packer.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Pack obfuscated scripts',
        epilog=__doc__,
    )
    add_arguments(parser)
    packer(parser.parse_args(args))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(message)s',
    )
    try:
        main(sys.argv[1:])
    except Exception as e:
        if sys.flags.debug:
            raise
        print(e)
        sys.exit(1)
