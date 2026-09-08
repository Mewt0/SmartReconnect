"""Build a clean WoT archive using Python 2.7 on Windows or Linux."""
from __future__ import print_function
import argparse
import imp
import os
import py_compile
import re
import shutil
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output-dir', default='.')
    args = parser.parse_args()
    if sys.version_info[:2] != (2, 7):
        parser.error('WoT payload must be compiled with Python 2.7')
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*$', args.version):
        parser.error('Invalid version')
    root = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(args.output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    output = os.path.join(output_dir, 'mewt0.smartReconnect_%s.wotmod' % args.version)
    if os.path.exists(output):
        parser.error('Output already exists: ' + output)
    staging = tempfile.mkdtemp(prefix='smartreconnect-build-')
    try:
        payload = []
        for directory, dirs, files in os.walk(os.path.join(root, 'res')):
            dirs[:] = sorted(d for d in dirs if d != '__pycache__')
            for name in sorted(files):
                if not name.endswith('.py'):
                    continue
                source = os.path.join(directory, name)
                relative = os.path.relpath(source, root).replace(os.sep, '/')
                dest = os.path.join(staging, *relative.split('/'))
                if not os.path.isdir(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))
                with open(source, 'rb') as stream:
                    data = stream.read().replace(b'{{VERSION}}', args.version.encode('ascii'))
                with open(dest, 'wb') as stream:
                    stream.write(data)
                py_compile.compile(dest, cfile=dest + 'c', dfile=relative, doraise=True)
                payload.append((relative + 'c', dest + 'c'))
        with open(os.path.join(root, 'meta.xml'), 'rb') as stream:
            meta = stream.read().replace(b'{{VERSION}}', args.version.encode('ascii'))
        archive_path = os.path.join(staging, 'payload.wotmod')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', meta)
            for relative, path in payload:
                archive.write(path, relative)
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(payload) + 1
            for relative, unused in payload:
                assert archive.read(relative)[:4] == imp.get_magic()
        shutil.copyfile(archive_path, output)
        print('Built %s (%d Python 2.7 modules)' % (output, len(payload)))
    finally:
        shutil.rmtree(staging)


if __name__ == '__main__':
    main()
