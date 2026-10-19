#!/usr/bin/env python3
"""Read-only publisher preflight; no authentication, network or release writes."""
import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys

def main():
    expected = {'pyelftools': '0.32', 'jsonschema': '4.25.1'}
    for name, version in expected.items():
        if importlib.metadata.version(name) != version:
            raise ValueError('Publisher dependency differs: ' + name)
    modules = ('serial_transfer_release', 'publish_serial_transfer_release',
               'publish_serial_transfer_feed', 'publish_serial_transfer_pair',
               'build_serial_transfer_pair', 'serial_transfer_memory', 'qualify_serial_transfer_logs',
               'elftools.elf.elffile', 'jsonschema')
    for name in modules:
        importlib.import_module(name)
    versions = {}
    for name in ('git', 'gh', 'python3'):
        path = shutil.which(name)
        if path is None:
            raise ValueError('Publisher executable missing: ' + name)
        versions[name] = subprocess.check_output([path, '--version'], text=True).splitlines()[0]
    print(json.dumps({'status': 'passed', 'dependencies': expected,
                      'imported_modules': list(modules), 'tools': versions,
                      'release_written': False, 'device_accessed': False}, sort_keys=True))

if __name__ == '__main__':
    main()
