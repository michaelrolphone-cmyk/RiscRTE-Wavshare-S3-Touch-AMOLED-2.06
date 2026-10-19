#!/usr/bin/env python3
"""Resume only exact-source immutable releases; publish after byte verification."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import package_serial_transfer as package
from package_serial_transfer import require, sha
from serial_transfer_release import verify_output, PRODUCTS


def gh(*args, absent=False):
    result = subprocess.run(['gh', *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        if absent and '(HTTP 404)' in result.stderr: return None
        raise RuntimeError('GitHub command failed: ' + result.stderr.strip())
    return result.stdout


def object_json(*args, absent=False):
    data = gh(*args, absent=absent)
    return None if data is None else json.loads(data)


def check_tags(rows, tag, version, revision):
    expected = 'refs/tags/' + tag
    exact = []
    for row in rows:
        if re.search(r'(?<![0-9])' + re.escape(version) + r'(?![0-9])', row['ref']):
            require(row['ref'] == expected, 'Version already reserved by another tag')
            require(row['object']['type'] == 'commit' and row['object']['sha'] == revision, 'Existing tag source differs')
            exact.append(row)
    require(len(exact) <= 1, 'Ambiguous release tag')
    return bool(exact)


def find_release(repo, tag):
    pages = object_json('api', '--paginate', '--slurp', 'repos/' + repo + '/releases?per_page=100')
    rows = [row for page in pages for row in page if row['tag_name'] == tag]
    require(len(rows) <= 1, 'Ambiguous release tag')
    return rows[0] if rows else None


def check_release(row, tag, names, title=None, body=None):
    require(row['tag_name'] == tag and row['prerelease'] is True, 'Release identity differs')
    if title is not None: require(row['name'] == title and row['body'] == body, 'Existing release text differs')
    assets = row['assets']
    actual = [a['name'] for a in assets]
    require(len(actual) == len(set(actual)) and set(actual) <= names, 'Unexpected or duplicate release assets')
    require(all(a['state'] == 'uploaded' for a in assets), 'Incomplete remote asset requires explicit recovery')
    if row['draft'] is False: require(set(actual) == names, 'Published release is incomplete')
    return names - set(actual)


def check_release_source(row, revision, release_id=None):
    require(row is not None and type(row['id']) is int and row['id'] > 0 and
            row['target_commitish'] == revision, 'Release source identity differs')
    if release_id is not None:
        require(row['id'] == release_id, 'Canonical release ID changed')
    return row['id']


def read_created_release(repo, tag, revision):
    """Wait only for visibility after one successful create; never create again."""
    for pause in (0, 1, 2, 4):
        if pause:
            time.sleep(pause)
        row = find_release(repo, tag)
        if row is not None:
            # A visible wrong-source release is a hard failure, not a reason
            # to retry until a different identity happens to appear.
            check_release_source(row, revision)
            require(row['tag_name'] == tag, 'Created release tag differs')
            return row
    raise ValueError('Created draft release remains absent after bounded read-only visibility checks; '
                     'no second create was attempted. Inspect the existing release and resume the same source only.')


def pair_asset_names(version):
    result={'PAIR-QUALIFICATION.json','PAIR-SHA256SUMS'}
    for mode in ('create','replace','known-lora','conditional-known-lora'):
        stem='Waveshare-'+version+'-SD-Apps-'+mode
        result.update(stem+suffix for suffix in ('.zip','.json','-context.json','-descriptor.json'))
    return result


def publish(root, digest, revision):
    p = package.pins()
    require(p['publication_enabled'] is True, 'Product release publication not selected')
    verify_output(root, digest, revision)
    repo = 'michaelrolphone-cmyk/' + PRODUCTS[p['product']][0]
    title = PRODUCTS[p['product']][1] + ' ' + p['version'] + ' complete SD apps, hardware pending'
    body = (root / 'RELEASE-NOTES.txt').read_text()
    tag = p['release_tag']; names = {f.name for f in root.iterdir()}
    pages = object_json('api', '--paginate', '--slurp', 'repos/' + repo + '/git/matching-refs/tags/')
    tags = [row for page in pages for row in page]
    if not check_tags(tags, tag, p['version'], revision):
        object_json('api', '--method', 'POST', 'repos/' + repo + '/git/refs', '-f', 'ref=refs/tags/' + tag, '-f', 'sha=' + revision)
    exact = object_json('api', 'repos/' + repo + '/git/ref/tags/' + tag)
    require(exact['object']['type'] == 'commit' and exact['object']['sha'] == revision, 'Created tag readback differs')
    row = find_release(repo, tag)
    if row is None:
        gh('release', 'create', tag, '--repo', repo, '--verify-tag', '--target', revision, '--draft', '--prerelease', '--latest=false',
           '--title', title,
           '--notes-file', str(root / 'RELEASE-NOTES.txt'))
        row = read_created_release(repo, tag, revision)
    release_id = check_release_source(row, revision)
    if row is not None and not row['draft'] and set(a['name'] for a in row['assets'])-names:
        actual=[a['name'] for a in row['assets']]
        require(len(actual)==len(set(actual)) and set(actual)<=names|pair_asset_names(p['version']), 'Unexpected canonical extension')
        base=dict(row,assets=[a for a in row['assets'] if a['name'] in names])
        require(not check_release(base,tag,names,title,body),'Published base is incomplete')
        with tempfile.TemporaryDirectory(prefix='wave-base-resume-') as tmp:
            for name in sorted(names):gh('release','download',tag,'--repo',repo,'--pattern',name,'--dir',tmp)
            verify_output(Path(tmp),digest,revision)
        check_release_source(find_release(repo, tag), revision, release_id)
        exact = object_json('api', 'repos/' + repo + '/git/ref/tags/' + tag)
        require(check_tags([exact], tag, p['version'], revision), 'Resumed tag readback differs')
        # The following pair publication step regenerates and verifies every
        # allowed sidecar. This branch attests only the immutable base release.
        print(row['html_url']);return
    missing = check_release(row, tag, names, title, body)
    # A resumed upload may only add missing names. Existing bytes must match;
    # no tag/asset replacement or deletion is performed.
    with tempfile.TemporaryDirectory(prefix='shared-default-release-readback-') as d:
        existing = Path(d) / 'existing'; existing.mkdir()
        if row['assets']:
            gh('release', 'download', tag, '--repo', repo, '--dir', str(existing))
            require({f.name for f in existing.iterdir()} == names - missing, 'Remote inventory changed during readback')
            for f in existing.iterdir(): require(sha(f.read_bytes()) == sha((root / f.name).read_bytes()), 'Existing asset bytes differ: ' + f.name)
        if missing:
            require(row['draft'] is True, 'Only draft upload may be resumed')
            gh('release', 'upload', tag, *[str(root / n) for n in sorted(missing)], '--repo', repo)
        staged = Path(d) / 'staged'
        gh('release', 'download', tag, '--repo', repo, '--dir', str(staged))
        verify_output(staged, digest, revision)
        row = find_release(repo, tag)
        check_release_source(row, revision, release_id)
        require(not check_release(row, tag, names, title, body), 'Draft release incomplete')
        exact = object_json('api', 'repos/' + repo + '/git/ref/tags/' + tag)
        require(exact['object']['type'] == 'commit' and exact['object']['sha'] == revision, 'Tag changed before publication')
        if row['draft'] is True: gh('release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease', '--latest=false')
        final = find_release(repo, tag)
        check_release_source(final, revision, release_id)
        require(final['draft'] is False and not check_release(final, tag, names, title, body), 'Published release readback differs')
        public = Path(d) / 'published'
        gh('release', 'download', tag, '--repo', repo, '--dir', str(public))
        verify_output(public, digest, revision)
    exact = object_json('api', 'repos/' + repo + '/git/ref/tags/' + tag)
    require(exact['object']['type'] == 'commit' and exact['object']['sha'] == revision, 'Final tag readback differs')
    print(final['html_url'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    require(__debug__, 'Validation cannot be disabled')
    publish(args.assets.resolve(), args.expected_sha, args.source_revision)
