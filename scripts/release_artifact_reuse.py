#!/usr/bin/env python3
"""Promote an immutable qualified producer; never compile or rewrite its assets."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

import publish_provisioning_release as publisher

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
ENVELOPE = 'publication-envelope.json'
PROMOTION_WORKFLOW = '.github/workflows/release-artifact-promotion.yml'
SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'bytes': len(data), 'sha256': sha(data)}


def decode(data):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def clean(root, revision):
    require(SHA.fullmatch(revision), 'Immutable source revision required')
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == revision, 'Checkout revision differs')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all'), 'Clean checkout required')


def tree(root, revision):
    require(SHA.fullmatch(revision), 'Immutable tree revision required')
    rows = {}
    for entry in git(root, 'ls-tree', '-r', '-z', '--full-tree', revision).split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        path = raw_path.decode('utf-8')
        require(path not in rows, 'Duplicate tracked path')
        rows[path] = {'mode': mode, 'type': kind, 'object': oid}
    require(rows, 'Empty source tree')
    return rows


def blob(root, revision, path):
    return git(root, 'show', revision + ':' + path)


def audit_closure(root, producer, publication, audit):
    """All unknown tree entries are build inputs, including mode/gitlink changes."""
    before, after = tree(root, producer), tree(root, publication)
    require(audit['schema'] == 1 and audit['profile'] == 'wifi-footer-v1', 'Unknown audit profile')
    require(producer == audit['audited_revision'], 'Producer revision is not the audited recipe; review a new profile')
    code = {p: v for p, v in before.items() if not p.startswith('docs/')}
    require(sha(encoded(code)) == audit['non_document_tree_sha256'], 'Unaudited producer build code; rebuild or review a new profile')
    pins_path = audit['pins_path']
    pins_before = decode(blob(root, producer, pins_path))
    pins_after = decode(blob(root, publication, pins_path))
    require(pins_before.get('publication_enabled') is False and pins_after.get('publication_enabled') is True,
            'Exact disabled-to-enabled publication transition required')
    require(pins_before.get('finalized') is True and pins_after.get('finalized') is True, 'Finalized producer required')
    normalized_before = dict(pins_before); normalized_before.pop('publication_enabled')
    normalized_after = dict(pins_after); normalized_after.pop('publication_enabled')
    require(encoded(normalized_before) == encoded(normalized_after), 'Build/dependency/configuration pins changed; rebuild required')
    require(sha(encoded(normalized_before)) == audit['build_pins_sha256'], 'Unaudited producer dependency/build pins')
    allowed = set(audit['metadata_paths'])
    require(allowed == {'docs/wifi-footer/retained-touch/README.md',
                        'docs/wifi-footer/retained-touch/normal.json',
                        'docs/wifi-footer/retained-touch/sanitized.json'}, 'Audit metadata allowance differs')
    changes = []
    closure = {}
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if path == pins_path:
            require(old and new and old['type'] == new['type'] == 'blob'
                    and old['mode'] == new['mode'] == '100644', 'Pins type or mode differs')
            closure[path] = {'normalized_sha256': sha(encoded(normalized_before))}
        elif path in allowed:
            require(all(row is None or (row['type'] == 'blob' and row['mode'] == '100644') for row in (old, new)),
                    'Metadata must remain ordinary non-executable files')
        else:
            require(old == new, 'Unclassified or changed build input; rebuild required: ' + path)
            closure[path] = old
        if old != new:
            changes.append({'path': path, 'before': old, 'after': new})
    return {'profile': audit['profile'], 'audit_sha256': sha(encoded(audit)),
            'producer_tree': git(root, 'rev-parse', producer + '^{tree}').decode().strip(),
            'publication_tree': git(root, 'rev-parse', publication + '^{tree}').decode().strip(),
            'unchanged_input_closure_sha256': sha(encoded(closure)), 'changes': changes}, pins_before, pins_after


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timestamp timezone required')
    return result


def verify_provider(plan, run, artifact, jobs, now):
    """Provider metadata is fetched for the exact attempt, never a latest alias."""
    source = plan['producer_revision']
    require(run['id'] == plan['run_id'] and run['run_attempt'] == plan['run_attempt'], 'Producer run/attempt differs')
    require(run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY, 'Producer repository differs')
    require(run['repository']['id'] == run['head_repository']['id'], 'Fork producer rejected')
    require(run['head_sha'] == source and run['event'] == 'push', 'Producer source/event differs')
    require(run['path'] == '.github/workflows/wifi-footer-native.yml', 'Producer workflow differs')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Successful completed producer required')
    require(artifact['id'] == plan['artifact_id'] and artifact['name'] == 'wifi-footer-release-' + source, 'Artifact identity differs')
    require(artifact['expired'] is False and timestamp(artifact['expires_at']) > now, 'Producer artifact expired')
    require(artifact['digest'] == 'sha256:' + plan['archive_sha256'], 'Provider archive digest differs')
    link = artifact['workflow_run']
    require(link['id'] == plan['run_id'] and link['head_sha'] == source and link['head_branch'] == run['head_branch'], 'Artifact producer binding differs')
    require(link['repository_id'] == link['head_repository_id'] == run['repository']['id'], 'Artifact repository differs')
    require(timestamp(run['run_started_at']) <= timestamp(artifact['created_at']) <= timestamp(run['updated_at']), 'Artifact outside producer attempt')
    require(len(jobs) > 0, 'Producer jobs missing')
    native = [j for j in jobs if j['name'] == 'native']
    require(len(native) == 1, 'Native qualification job missing or ambiguous')
    job = native[0]
    require(job['run_id'] == plan['run_id'] and job['run_attempt'] == plan['run_attempt'] and job['head_sha'] == source,
            'Qualification job identity differs')
    require(job['status'] == 'completed' and job['conclusion'] == 'success', 'Native qualification failed')
    qualified = [s for s in job['steps'] if s['name'] == 'Build exact retained Home/power and patched Wi-Fi; qualify native product and final factory']
    require(len(qualified) == 1 and qualified[0]['status'] == 'completed' and qualified[0]['conclusion'] == 'success', 'Qualification step failed or missing')
    return {'repository_id': run['repository']['id'], 'workflow_id': run['workflow_id'],
            'workflow_path': run['path'], 'head_branch': run['head_branch'],
            'artifact_created_at': artifact['created_at'], 'artifact_expires_at': artifact['expires_at'],
            'native_job_seconds': (timestamp(job['completed_at']) - timestamp(job['started_at'])).total_seconds(),
            'native_build_and_qualification_seconds': (timestamp(qualified[0]['completed_at']) - timestamp(qualified[0]['started_at'])).total_seconds()}


def extract_archive(path, output, digest, size):
    data = path.read_bytes()
    require(sha(data) == digest and len(data) == size, 'Downloaded archive digest/size differs')
    require(not output.exists(), 'Producer output must be new')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= 100 and sum(e.file_size for e in entries) <= 512 * 1024 * 1024, 'Archive bounds exceeded')
        names = [e.filename for e in entries]
        require(len(names) == len(set(names)), 'Duplicate archive entries')
        require(all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', n) for n in names), 'Unsafe/non-flat archive path')
        require(all(not e.is_dir() and not stat.S_ISLNK(e.external_attr >> 16) and not e.flag_bits & 1 for e in entries), 'Unsafe archive member')
        output.mkdir(parents=True)
        for entry in entries:
            (output / entry.filename).write_bytes(archive.read(entry))


def inventory(root):
    rows = {}
    for path in root.iterdir():
        require(path.is_file() and not path.is_symlink(), 'Non-regular release asset')
        rows[path.name] = record(path.read_bytes())
    return dict(sorted(rows.items()))


def verify_producer(root, source, plan):
    clean(source, plan['producer_revision'])
    require(sha((root / 'SHA256SUMS').read_bytes()) == plan['checksums_sha256'], 'Producer checksum custody differs')
    require(sha((root / 'release.json').read_bytes()) == plan['manifest_sha256'], 'Producer manifest digest differs')
    report = decode((root / 'release.json').read_bytes())
    require(report['repository'] == REPOSITORY and report['source_revision'] == plan['producer_revision'], 'Manifest producer differs')
    require(report['ci']['repository'] == REPOSITORY and report['ci']['source_revision'] == plan['producer_revision']
            and report['ci']['run_id'] == plan['run_id'] and report['ci']['run_attempt'] == plan['run_attempt'], 'Manifest run/attempt differs')
    require(report['publication_enabled'] is False and report['native_rebuilt'] is True, 'Original unpublished producer history required')
    # Original clean, source-pinned verifier re-runs every independent integrity
    # and qualification check. No module is imported from artifact content.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    env.pop('PYTHONPATH', None)
    subprocess.run([sys.executable, '-B', str(source / 'scripts/wifi_footer_release.py'),
                    '--verify', str(root), '--expected-sha', plan['checksums_sha256'],
                    '--source-revision', plan['producer_revision']], cwd=source, env=env, check=True)
    clean(source, plan['producer_revision'])
    return report


def make_envelope(plan, closure, provider, root, controller_revision):
    report = decode((root / 'release.json').read_bytes())
    return {'schema': 1, 'kind': 'qualified-artifact-publication', 'repository': REPOSITORY,
            'tag_policy': 'immutable-producer-source', 'release_tag': report['release_tag'],
            'producer_revision': plan['producer_revision'], 'publication_revision': plan['publication_revision'],
            'controller_revision': controller_revision, 'authorization_sha256': sha(encoded(plan)),
            'producer': {k: plan[k] for k in ('run_id', 'run_attempt', 'artifact_id', 'archive_sha256', 'manifest_sha256', 'checksums_sha256')},
            'provider': provider, 'build_input_closure': closure, 'producer_assets': inventory(root),
            'producer_native_rebuilt': True, 'publication_native_rebuilt': False, 'hardware_tested': False,
            'producer_workflow_revision': plan['producer_revision'], 'producer_workflow_sha256': report['ci']['workflow_sha256']}


def verify_published(root, producer_assets, envelope_bytes, source, plan):
    require(inventory(root) == dict(producer_assets, **{ENVELOPE: record(envelope_bytes)}), 'Published asset inventory or bytes differ')
    require((root / ENVELOPE).read_bytes() == envelope_bytes, 'Publication envelope differs')
    # Preserve the producer verifier's strict original inventory unchanged.
    with tempfile.TemporaryDirectory(prefix='producer-verification-') as temporary:
        original = Path(temporary)
        for name in producer_assets:
            shutil.copyfile(root / name, original / name)
        verify_producer(original, source, plan)


def publish(root, envelope, source, plan):
    """Existing immutable-tag/version checks and independently downloaded bytes."""
    validate_plan(plan)
    require(plan['publish'] is True, 'Publication not authorized in committed request')
    require(envelope['authorization_sha256'] == sha(encoded(plan))
            and envelope['producer_revision'] == plan['producer_revision']
            and envelope['publication_revision'] == plan['publication_revision'], 'Publication authorization binding differs')
    report = decode((root / 'release.json').read_bytes())
    tag, revision = report['release_tag'], plan['producer_revision']
    names = set(inventory(root))
    body = (root / 'RELEASE-NOTES.txt').read_text()
    title = 'Waveshare ' + report['version'] + ' wifi-footer repair, hardware pending'
    envelope_bytes = encoded(envelope)
    verify = lambda path: verify_published(path, envelope['producer_assets'], envelope_bytes, source, plan)
    verify(root)
    pages = publisher.object_json('api', '--paginate', '--slurp', 'repos/' + REPOSITORY + '/git/matching-refs/tags/')
    tags = [row for page in pages for row in page]
    if not publisher.check_tags(tags, tag, report['version'], revision):
        publisher.object_json('api', '--method', 'POST', 'repos/' + REPOSITORY + '/git/refs', '-f', 'ref=refs/tags/' + tag, '-f', 'sha=' + revision)
    def verify_tag():
        exact = publisher.object_json('api', 'repos/' + REPOSITORY + '/git/ref/tags/' + tag)
        require(exact['object']['type'] == 'commit' and exact['object']['sha'] == revision, 'Release tag producer differs')
    verify_tag()
    row = publisher.find_release(REPOSITORY, tag)
    if row is None:
        publisher.gh('release', 'create', tag, '--repo', REPOSITORY, '--verify-tag', '--target', revision,
                     '--draft', '--prerelease', '--latest=false', '--title', title, '--notes-file', str(root / 'RELEASE-NOTES.txt'))
        row = publisher.wait_for_created_release(REPOSITORY, tag)
    missing = publisher.check_release(row, tag, names, title, body)
    with tempfile.TemporaryDirectory(prefix='promotion-readback-') as temporary:
        temporary = Path(temporary)
        if row['assets']:
            existing = temporary / 'existing'
            publisher.gh('release', 'download', tag, '--repo', REPOSITORY, '--dir', str(existing))
            require(inventory(existing) == {n: record((root / n).read_bytes()) for n in names - missing}, 'Existing release bytes differ')
        if missing:
            require(row['draft'] is True, 'Only draft uploads may resume')
            publisher.gh('release', 'upload', tag, *[str(root / n) for n in sorted(missing)], '--repo', REPOSITORY)
        staged = temporary / 'staged'
        publisher.gh('release', 'download', tag, '--repo', REPOSITORY, '--dir', str(staged))
        verify(staged)
        row = publisher.find_release(REPOSITORY, tag)
        require(not publisher.check_release(row, tag, names, title, body), 'Draft incomplete')
        verify_tag()
        if row['draft'] is True:
            publisher.gh('release', 'edit', tag, '--repo', REPOSITORY, '--draft=false', '--prerelease', '--latest=false')
        final = publisher.find_release(REPOSITORY, tag)
        require(final['draft'] is False and not publisher.check_release(final, tag, names, title, body), 'Publication readback differs')
        public = temporary / 'public'
        publisher.gh('release', 'download', tag, '--repo', REPOSITORY, '--dir', str(public))
        verify(public)
    verify_tag()
    return final['html_url']


def validate_plan(plan):
    fields = {'schema', 'profile', 'repository', 'producer_revision', 'publication_revision', 'run_id', 'run_attempt',
              'artifact_id', 'archive_sha256', 'manifest_sha256', 'checksums_sha256', 'publish'}
    require(set(plan) == fields and plan['schema'] == 1 and plan['profile'] == 'wifi-footer-v1', 'Unknown authorization schema/profile')
    require(plan['repository'] == REPOSITORY and type(plan['publish']) is bool, 'Authorization repository/intent differs')
    for key in ('producer_revision', 'publication_revision'):
        require(isinstance(plan[key], str) and SHA.fullmatch(plan[key]), 'Immutable authorization source required')
    for key in ('run_id', 'run_attempt', 'artifact_id'):
        require(type(plan[key]) is int and plan[key] > 0, 'Positive immutable provider identity required')
    for key in ('archive_sha256', 'manifest_sha256', 'checksums_sha256'):
        require(isinstance(plan[key], str) and DIGEST.fullmatch(plan[key]), 'Exact authorization digest required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    require(__debug__, 'Validation cannot be disabled')
    revision = os.environ.get('GITHUB_SHA', '')
    clean(ROOT, revision)
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Controller repository differs')
    require(os.environ.get('GITHUB_WORKFLOW_SHA') == revision, 'Controller workflow revision differs')
    require(os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + PROMOTION_WORKFLOW + '@refs/heads/main', 'Trusted main controller workflow required')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Promotion runs from main only')
    relative = args.authorization.as_posix()
    require(re.fullmatch(r'docs/release-artifact-reuse/requests/[a-z0-9-]+\.json', relative), 'Committed request path required')
    request = blob(ROOT, revision, relative)
    require((ROOT / relative).read_bytes() == request, 'Authorization checkout bytes differ')
    plan = decode(request); validate_plan(plan)
    require(not args.publish or plan['publish'], 'Publication not authorized in committed request')
    audit = decode((ROOT / 'docs/release-artifact-reuse/wifi-footer-audit.json').read_bytes())
    workspace = args.workspace.resolve()
    require(not workspace.exists(), 'Promotion workspace must be new')
    workspace.mkdir(parents=True)
    started = time.monotonic()
    for sha_ in (plan['producer_revision'], plan['publication_revision']):
        subprocess.run(['git', '-C', str(ROOT), 'fetch', '--no-tags', 'origin', sha_], check=True)
    closure, producer_pins, publication_pins = audit_closure(ROOT, plan['producer_revision'], plan['publication_revision'], audit)
    source = workspace / 'producer-source'
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(source), plan['producer_revision']], check=True)
    base = 'repos/' + REPOSITORY + '/actions/'
    run = publisher.object_json('api', base + 'runs/' + str(plan['run_id']) + '/attempts/' + str(plan['run_attempt']))
    artifact = publisher.object_json('api', base + 'artifacts/' + str(plan['artifact_id']))
    pages = publisher.object_json('api', '--paginate', '--slurp', base + 'runs/' + str(plan['run_id']) + '/attempts/' + str(plan['run_attempt']) + '/jobs?per_page=100')
    jobs = [job for page in pages for job in page['jobs']]
    provider = verify_provider(plan, run, artifact, jobs, datetime.now(timezone.utc))
    require(run['head_branch'] == producer_pins['release_branch'], 'Producer release branch differs')
    archive = workspace / 'producer.zip'
    with archive.open('wb') as output:
        subprocess.run(['gh', 'api', base + 'artifacts/' + str(plan['artifact_id']) + '/zip'], stdout=output, check=True)
    original = workspace / 'producer-assets'
    extract_archive(archive, original, plan['archive_sha256'], artifact['size_in_bytes'])
    verify_producer(original, source, plan)
    envelope = make_envelope(plan, closure, provider, original, revision)
    assets = workspace / 'publication-assets'
    shutil.copytree(original, assets)
    (assets / ENVELOPE).write_bytes(encoded(envelope))
    verify_published(assets, envelope['producer_assets'], encoded(envelope), source, plan)
    result = {'schema': 1, 'verified_publication_only': True, 'native_compilation_invoked': False,
              'publication_requested': args.publish, 'published_url': publish(assets, envelope, source, plan) if args.publish else None,
              'wall_seconds': time.monotonic() - started,
              'process_user_seconds': resource.getrusage(resource.RUSAGE_SELF).ru_utime,
              'process_system_seconds': resource.getrusage(resource.RUSAGE_SELF).ru_stime,
              'child_user_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
              'child_system_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
              'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              'producer_native_job_seconds': provider['native_job_seconds'],
              'producer_build_and_qualification_seconds': provider['native_build_and_qualification_seconds'],
              'measurement_note': 'Historical build/qualification wall time is not isolated compile CPU time; machines differ.',
              'envelope_sha256': sha(encoded(envelope)), 'producer_assets': envelope['producer_assets']}
    (workspace / 'promotion-result.json').write_bytes(encoded(result))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
