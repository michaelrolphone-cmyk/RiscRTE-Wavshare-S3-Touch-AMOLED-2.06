#!/usr/bin/env python3
"""Offline fail-closed promotion controls. Synthetic tests never claim hardware."""
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import release_artifact_reuse as reuse
import test_wifi_footer_release as retained


class PromotionContracts(unittest.TestCase):
    def plan(self):
        return dict(schema=1, profile='wifi-footer-v1', repository=reuse.REPOSITORY,
                    producer_revision='1'*40, publication_revision='2'*40,
                    run_id=123, run_attempt=1, artifact_id=456, archive_sha256='a'*64,
                    manifest_sha256='b'*64, checksums_sha256='c'*64, publish=False)

    def provider(self):
        plan = self.plan()
        run = dict(id=123, run_attempt=1, repository=dict(full_name=reuse.REPOSITORY, id=789),
                   head_repository=dict(full_name=reuse.REPOSITORY, id=789), head_sha='1'*40,
                   head_branch='release/wifi-footer-0.1.55', event='push',
                   path='.github/workflows/wifi-footer-native.yml', workflow_id=987,
                   status='completed', conclusion='success', run_started_at='2026-10-17T01:00:00Z',
                   updated_at='2026-10-17T01:10:00Z')
        artifact = dict(id=456, name='wifi-footer-release-'+'1'*40, expired=False,
                        expires_at='2026-11-17T01:00:00Z', created_at='2026-10-17T01:09:00Z',
                        digest='sha256:'+'a'*64,
                        workflow_run=dict(id=123, head_sha='1'*40, head_branch=run['head_branch'],
                                          repository_id=789, head_repository_id=789))
        jobs = [dict(name='native', run_id=123, run_attempt=1, head_sha='1'*40,
                     status='completed', conclusion='success', started_at='2026-10-17T01:00:00Z',
                     completed_at='2026-10-17T01:10:00Z', steps=[dict(
                         name='Build exact retained Home/power and patched Wi-Fi; qualify native product and final factory',
                         status='completed', conclusion='success', started_at='2026-10-17T01:01:00Z',
                         completed_at='2026-10-17T01:08:00Z')])]
        return plan, run, artifact, jobs

    def test_provider_binds_exact_successful_attempt(self):
        args = self.provider()
        result = reuse.verify_provider(*args, datetime(2026,10,19,tzinfo=timezone.utc))
        self.assertEqual(result['native_build_and_qualification_seconds'], 420)
        self.assertEqual(result['native_job_seconds'], 600)

    def test_provider_negative_matrix(self):
        mutations = [
            (1, ('id',), 124), (1, ('run_attempt',), 2),
            (1, ('repository','full_name'), 'evil/repo'), (1, ('head_repository','id'), 790),
            (1, ('head_sha',), '9'*40), (1, ('event',), 'pull_request'),
            (1, ('path',), '.github/workflows/other.yml'), (1, ('status',), 'in_progress'),
            (1, ('conclusion',), 'failure'), (1, ('conclusion',), 'cancelled'),
            (2, ('id',), 457), (2, ('name',), 'other'), (2, ('expired',), True),
            (2, ('expires_at',), '2026-10-18T00:00:00Z'), (2, ('digest',), 'sha256:'+'d'*64),
            (2, ('workflow_run','id'), 124), (2, ('workflow_run','head_sha'), '3'*40),
            (2, ('workflow_run','repository_id'), 790), (2, ('workflow_run','head_branch'), 'main'),
            (2, ('created_at',), '2026-10-16T00:00:00Z'),
            (2, ('created_at',), '2026-10-17T01:11:00Z'),
            (3, (0,'run_attempt'), 2), (3, (0,'head_sha'), '9'*40),
            (3, (0,'conclusion'), 'failure'), (3, (0,'steps',0,'conclusion'), 'skipped'),
            (3, (0,'steps'), []), (3, (0,'name'), 'unqualified'),
        ]
        for target, path, value in mutations:
            args = copy.deepcopy(self.provider())
            node = args[target]
            for key in path[:-1]: node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                reuse.verify_provider(*args, datetime(2026,10,19,tzinfo=timezone.utc))
        for jobs in ([], self.provider()[3]*2):
            args = list(self.provider()); args[3] = jobs
            with self.assertRaises(ValueError): reuse.verify_provider(*args, datetime(2026,10,19,tzinfo=timezone.utc))

    def closure_fixture(self):
        audit = reuse.decode((reuse.ROOT/'docs/release-artifact-reuse/wifi-footer-audit.json').read_bytes())
        audit['audited_revision']='1'*40
        pins = dict(publication_enabled=False, finalized=True, version='0.1.55', runtime_revision='8'*40)
        after_pins = dict(pins, publication_enabled=True)
        row = dict(mode='100644', type='blob', object='9'*40)
        before = {'scripts/build.py':dict(row), 'native/firmware.c':dict(row),
                  audit['pins_path']:dict(row), '.gitmodules':dict(row)}
        after = copy.deepcopy(before)
        after[audit['pins_path']]['object'] = 'a'*40
        after[audit['metadata_paths'][0]] = dict(row)
        audit['non_document_tree_sha256'] = reuse.sha(reuse.encoded({p:r for p,r in before.items() if not p.startswith('docs/')}))
        audit['build_pins_sha256'] = reuse.sha(reuse.encoded({k:v for k,v in pins.items() if k!='publication_enabled'}))
        return audit, before, after, pins, after_pins

    def closure(self, fixture):
        audit, before, after, pins, publication = fixture
        with patch.object(reuse, 'tree', side_effect=[before, after]), \
             patch.object(reuse, 'blob', side_effect=[reuse.encoded(pins),reuse.encoded(publication)]), \
             patch.object(reuse, 'git', return_value=b'7'*40+b'\n'):
            return reuse.audit_closure(Path('.'), '1'*40, '2'*40, audit)

    def test_only_exact_publication_metadata_is_admitted(self):
        result, before, after = self.closure(self.closure_fixture())
        self.assertEqual(len(result['changes']),2)
        self.assertFalse(before['publication_enabled']); self.assertTrue(after['publication_enabled'])

    def test_all_unknown_inputs_modes_and_submodules_reject(self):
        paths = ['native/firmware.c','profiles/config.cmake','scripts/compiler.py','.github/workflows/wifi-footer-native.yml',
                 'docs/arbitrary.md','docs/wifi-footer/new-receipt.json','.gitmodules','third-party']
        for path in paths:
            fixture=self.closure_fixture(); fixture[2][path]=dict(mode='100644',type='blob',object='d'*40)
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'build input'):
                self.closure(fixture)
        for mode,kind in [('100755','blob'),('120000','blob'),('160000','commit')]:
            fixture=self.closure_fixture();fixture[2][fixture[0]['metadata_paths'][0]].update(mode=mode,type=kind)
            with self.assertRaises(ValueError):self.closure(fixture)
        fixture=self.closure_fixture();del fixture[2]['native/firmware.c']
        with self.assertRaises(ValueError):self.closure(fixture)

    def test_dependency_compiler_config_and_audit_changes_reject(self):
        for key in ('version','runtime_revision','compiler','configuration','release_tag','finalized'):
            fixture=self.closure_fixture();fixture[4][key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):self.closure(fixture)
        fixture=self.closure_fixture();fixture[1]['scripts/unknown.py']=dict(mode='100644',type='blob',object='f'*40)
        with self.assertRaisesRegex(ValueError,'Unaudited producer build code'):self.closure(fixture)
        fixture=self.closure_fixture();fixture[3]['runtime_revision']='f'*40;fixture[4]['runtime_revision']='f'*40
        with self.assertRaisesRegex(ValueError,'Unaudited producer dependency'):self.closure(fixture)
        fixture=self.closure_fixture();fixture[4]['publication_enabled']=False
        with self.assertRaises(ValueError):self.closure(fixture)

    def test_json_numeric_boolean_type_changes_are_build_changes(self):
        for before,after in [(1,True),(1,1.0),(False,0),(0,0.0),(True,1)]:
            fixture=self.closure_fixture()
            fixture[3]['flags']={'RISC_NATIVE_SERIAL_FILES':before}
            fixture[4]['flags']={'RISC_NATIVE_SERIAL_FILES':after}
            fixture[0]['build_pins_sha256']=reuse.sha(reuse.encoded({k:v for k,v in fixture[3].items() if k!='publication_enabled'}))
            with self.subTest(before=before,after=after),self.assertRaisesRegex(ValueError,'pins changed'):
                self.closure(fixture)

    def test_new_producer_and_document_alias_cannot_reuse_old_audit(self):
        fixture=self.closure_fixture()
        fixture[0]['audited_revision']='8'*40
        for snapshot in (fixture[1],fixture[2]):
            snapshot['docs/wifi-footer/power-header-selection.json']=dict(mode='120000',type='blob',object='a'*40)
        with self.assertRaisesRegex(ValueError,'Producer revision is not the audited recipe'):
            self.closure(fixture)

    def test_archive_digest_inventory_and_path_controls(self):
        def archive(names):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as z:
                for name in names:z.writestr(name,b'synthetic')
            return stream.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'artifact.zip';data=archive(['release.json']);path.write_bytes(data)
            reuse.extract_archive(path,root/'good',reuse.sha(data),len(data))
            for digest,size in [('0'*64,len(data)),(reuse.sha(data),len(data)+1)]:
                with self.assertRaises(ValueError):reuse.extract_archive(path,root/'bad',digest,size)
            for names in [['../escape'],['a/b'],['/absolute'],['same','same'],['dir/']]:
                data=archive(names);path.write_bytes(data)
                with self.subTest(names=names),self.assertRaises(ValueError):reuse.extract_archive(path,root/'bad',reuse.sha(data),len(data))
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as z:
                entry=zipfile.ZipInfo('symlink');entry.create_system=3;entry.external_attr=0o120777<<16;z.writestr(entry,b'target')
            path.write_bytes(data.getvalue())
            with self.assertRaises(ValueError):reuse.extract_archive(path,root/'bad',reuse.sha(data.getvalue()),len(data.getvalue()))

    def bundle(self,root):
        fixture=retained.ReleaseContracts()
        files,report,pins,revision=fixture.output_fixture()
        report['publication_enabled']=False
        digest=fixture.write_output(root,files,report)
        plan=self.plan();plan.update(manifest_sha256=reuse.sha((root/'release.json').read_bytes()),checksums_sha256=digest)
        envelope=reuse.make_envelope(plan,{'profile':'synthetic'}, {'workflow_id':987},root,'3'*40)
        (root/reuse.ENVELOPE).write_bytes(reuse.encoded(envelope))
        return plan,envelope

    def test_producer_manifest_identity_and_verifier_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan,envelope=self.bundle(root);(root/reuse.ENVELOPE).unlink()
            with patch.object(reuse,'clean'),patch.object(reuse.subprocess,'run') as command:
                reuse.verify_producer(root,Path('/producer'),plan)
                self.assertIn('/producer/scripts/wifi_footer_release.py',command.call_args.args[0])
                command.side_effect=RuntimeError('qualification failed')
                with self.assertRaises(RuntimeError):reuse.verify_producer(root,Path('/producer'),plan)
            for key in ('run_id','run_attempt','manifest_sha256','checksums_sha256','producer_revision'):
                broken=dict(plan);broken[key]=999 if isinstance(plan[key],int) else '9'*len(plan[key])
                with patch.object(reuse,'clean'),patch.object(reuse.subprocess,'run') as command,self.assertRaises(ValueError):
                    reuse.verify_producer(root,Path('/producer'),broken)
                command.assert_not_called()

    def test_envelope_missing_extra_and_changed_asset_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan,envelope=self.bundle(root);expected=reuse.encoded(envelope)
            with patch.object(reuse,'verify_producer'):
                reuse.verify_published(root,envelope['producer_assets'],expected,Path('/producer'),plan)
                for name in ['firmware.bin',reuse.ENVELOPE,'release.json','SHA256SUMS']:
                    old=(root/name).read_bytes();(root/name).write_bytes(old+b'changed')
                    with self.subTest(name=name),self.assertRaises(ValueError):reuse.verify_published(root,envelope['producer_assets'],expected,Path('/producer'),plan)
                    (root/name).write_bytes(old)
                (root/'extra').write_bytes(b'new')
                with self.assertRaises(ValueError):reuse.verify_published(root,envelope['producer_assets'],expected,Path('/producer'),plan)
                (root/'extra').unlink();(root/'firmware.bin').unlink()
                with self.assertRaises(ValueError):reuse.verify_published(root,envelope['producer_assets'],expected,Path('/producer'),plan)

    def test_publication_and_interrupted_upload_resume(self):
        for interrupt in (False,True):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)/'assets';root.mkdir();plan,envelope=self.bundle(root)
                plan['publish']=True;envelope['authorization_sha256']=reuse.sha(reuse.encoded(plan))
                (root/reuse.ENVELOPE).write_bytes(reuse.encoded(envelope))
                report=reuse.decode((root/'release.json').read_bytes());tag=report['release_tag']
                state={'tag':None,'release':None,'assets':{},'interrupted':False,'created':0,'downloads':0}
                def row():
                    if state['release'] is None:return None
                    return dict(state['release'],assets=[dict(name=n,state='uploaded') for n in state['assets']])
                def api(*args,**kwargs):
                    if '/git/matching-refs/tags/' in str(args):return [[state['tag']]] if state['tag'] else [[]]
                    if '--method' in args:
                        state['tag']=dict(ref='refs/tags/'+tag,object=dict(type='commit',sha=plan['producer_revision']));return state['tag']
                    return state['tag']
                def gh(*args,**kwargs):
                    if args[:2]==('release','create'):
                        state['created']+=1;state['release']=dict(tag_name=tag,prerelease=True,draft=True,name=args[args.index('--title')+1],body=(root/'RELEASE-NOTES.txt').read_text(),html_url='https://example.test/release')
                    elif args[:2]==('release','upload'):
                        for name in args[3:args.index('--repo')]:
                            path=Path(name);state['assets'][path.name]=path.read_bytes()
                            if interrupt and not state['interrupted']:
                                state['interrupted']=True;raise RuntimeError('upload interrupted')
                    elif args[:2]==('release','download'):
                        state['downloads']+=1;out=Path(args[args.index('--dir')+1]);out.mkdir()
                        for name,data in state['assets'].items():(out/name).write_bytes(data)
                    elif args[:2]==('release','edit'):state['release']['draft']=False
                    else:raise AssertionError(args)
                with patch.object(reuse.publisher,'object_json',side_effect=api),patch.object(reuse.publisher,'gh',side_effect=gh), \
                     patch.object(reuse.publisher,'find_release',side_effect=lambda *a:row()), \
                     patch.object(reuse.publisher,'wait_for_created_release',side_effect=lambda *a:row()),patch.object(reuse,'verify_producer'):
                    if interrupt:
                        with self.assertRaises(RuntimeError):reuse.publish(root,envelope,Path('/producer'),plan)
                        self.assertTrue(state['release']['draft'])
                    self.assertEqual(reuse.publish(root,envelope,Path('/producer'),plan),'https://example.test/release')
                    self.assertFalse(state['release']['draft']);self.assertEqual(state['created'],1)
                    self.assertEqual(state['tag']['object']['sha'],plan['producer_revision'])
                    self.assertEqual(state['assets'],{p.name:p.read_bytes() for p in root.iterdir()})
                    self.assertGreaterEqual(state['downloads'],2)
                    # Repeat is read-only: no duplicate release or changed assets.
                    reuse.publish(root,envelope,Path('/producer'),plan);self.assertEqual(state['created'],1)
                    state['tag']['object']['sha']=plan['publication_revision']
                    with self.assertRaisesRegex(ValueError,'Existing tag source differs'):reuse.publish(root,envelope,Path('/producer'),plan)

    def test_authorization_is_strict_and_no_compile_route(self):
        plan=self.plan();reuse.validate_plan(plan)
        for key,value in [('publish','true'),('repository','evil/repo'),('run_attempt',True),('profile','other'),('producer_revision','main'),('archive_sha256','')]:
            bad=dict(plan);bad[key]=value
            with self.assertRaises(ValueError):reuse.validate_plan(bad)
        bad=dict(plan);bad['extra']='ignored?'
        with self.assertRaises(ValueError):reuse.validate_plan(bad)
        with self.assertRaises(ValueError):reuse.decode(b'{"schema":1,"schema":2}')
        workflow=(reuse.ROOT/reuse.PROMOTION_WORKFLOW).read_text()
        self.assertNotIn('espressif/idf',workflow)
        self.assertNotIn('run_wifi_footer_native_ci.sh',workflow)
        self.assertIn('contents: read',workflow)
        self.assertIn('github.event_name == \'workflow_dispatch\'',workflow)
        self.assertIn('publication_native_rebuilt', (reuse.ROOT/'scripts/release_artifact_reuse.py').read_text())


if __name__=='__main__':
    unittest.main(verbosity=2)
