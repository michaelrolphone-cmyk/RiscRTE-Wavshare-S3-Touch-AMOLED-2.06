#!/usr/bin/env python3
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import consolidated_wave_source as q

class SourceTrees(unittest.TestCase):
    def setUp(self):
        self.base={'production.c':('100644','a'*40)}
        self.base['scripts/package_serial_lifetime.py']=('100644','a'*40)
        integrations=set(q.INTEGRATION-q.NEW)-set(self.base)
        additions=integrations|{f'original/{i}.txt' for i in range(49-len(integrations))}
        assert len(additions)==49
        self.capture=dict(self.base,**{p:('100644','b'*40) for p in additions})
        self.current=dict(self.capture,**{p:('100644','c'*40) for p in q.NEW})
    def validate(self):q.validate_trees(self.base,self.capture,self.current)
    def test_union(self):self.validate()
    def test_production_change(self):
        self.current['production.c']=('100644','d'*40)
        with self.assertRaisesRegex(ValueError,'Preserved source'):self.validate()
    def test_missing_original(self):
        self.current.pop('original/0.txt')
        with self.assertRaisesRegex(ValueError,'Missing'):self.validate()
    def test_changed_original(self):
        self.current['original/0.txt']=('100644','d'*40)
        with self.assertRaisesRegex(ValueError,'Preserved source'):self.validate()
    def test_extra_source(self):
        self.current['unapproved.c']=('100644','d'*40)
        with self.assertRaisesRegex(ValueError,'unadmitted'):self.validate()
    def test_missing_guard(self):
        self.current.pop('scripts/consolidated_wave_source.py')
        with self.assertRaisesRegex(ValueError,'Missing'):self.validate()
    def test_original_capture_rewrite(self):
        self.capture['production.c']=('100644','d'*40)
        with self.assertRaisesRegex(ValueError,'capture changes'):self.validate()
    def test_integration_symlink(self):
        self.current['scripts/consolidated_wave_source.py']=('120000','d'*40)
        with self.assertRaisesRegex(ValueError,'mode'):self.validate()

class HistoricalLifetime(unittest.TestCase):
    def test_historical_lifetime_contracts_keep_original_hashes(self):
        import package_serial_lifetime as lifetime
        with mock.patch.object(q, 'validate', return_value='f'*40) as admission:
            pins=lifetime.pins()
        admission.assert_called_once_with(lifetime.ROOT)
        self.assertEqual(len(pins['historical_contracts']),240)
        self.assertEqual(pins['baseline_source'],'049d3c932fa6683b2a8614abf0b46a881bf23cfb')
        # Both historical source trees retain all240 original recipe digests.
        for path,digest in pins['historical_contracts'].items():
            self.assertEqual(hashlib.sha256(q.git(q.ROOT,'show',pins['baseline_source']+':'+path)).hexdigest(),digest)
    def test_changed_historical_recipe_rejected(self):
        import package_serial_lifetime as lifetime
        with mock.patch.object(q,'validate',return_value='f'*40), mock.patch.object(q,'git',return_value=b'changed'):
            with self.assertRaisesRegex(ValueError,'Historical recipe changed'):lifetime.pins()
    def test_unadmitted_current_checkout_rejected(self):
        import package_serial_lifetime as lifetime
        with mock.patch.object(q,'validate',side_effect=ValueError('Dirty source checkout')):
            with self.assertRaisesRegex(ValueError,'Dirty source checkout'):lifetime.pins()

class WorkingSource(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init','-q');self.git('config','user.email','test@example.invalid');self.git('config','user.name','Test')
        self.git('config','maintenance.auto','false');self.git('config','gc.auto','0')
        (self.root/'file').write_text('original\n');self.git('add','file');self.git('commit','-qm','fixture')
        self.head=self.git('rev-parse','HEAD').strip()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],env=self.env,text=True)
    def test_clean(self):self.assertEqual(q.clean(self.root,self.head),self.head)
    def test_wrong_head(self):
        with self.assertRaisesRegex(ValueError,'Wrong source head'):q.clean(self.root,'0'*40)
    def test_assume_unchanged(self):
        self.git('update-index','--assume-unchanged','file');(self.root/'file').write_text('wrong\n')
        with self.assertRaisesRegex(ValueError,'Hidden index'):q.clean(self.root)
    def test_skip_worktree(self):
        self.git('update-index','--skip-worktree','file')
        with self.assertRaisesRegex(ValueError,'Hidden index'):q.clean(self.root)
    def test_hidden_untracked(self):
        self.git('config','status.showUntrackedFiles','no');(self.root/'hidden').write_text('wrong')
        with self.assertRaisesRegex(ValueError,'Dirty'):q.clean(self.root)
    def test_local_info_exclude_cannot_hide_source(self):
        (self.root/'.git/info/exclude').write_text('hidden.h\n')
        (self.root/'hidden.h').write_text('source')
        with self.assertRaisesRegex(ValueError,'locally ignored'):q.clean(self.root)
    def test_untracked_nested_ignore_cannot_hide_source(self):
        (self.root/'nested').mkdir()
        (self.root/'nested/.gitignore').write_text('*\n')
        (self.root/'nested/hidden.h').write_text('source')
        with self.assertRaisesRegex(ValueError,'locally ignored'):q.clean(self.root)
    def test_tracked_output_exclusion_allowed(self):
        (self.root/'.gitignore').write_text('/build/\n')
        self.git('add','.gitignore');self.git('commit','-qm','outputs')
        (self.root/'build').mkdir();(self.root/'build/generated.h').write_text('output')
        q.clean(self.root)
    def test_untracked_root_ignore_cannot_hide_source(self):
        (self.root/'.gitignore').write_text('*\n')
        (self.root/'hidden.h').write_text('source')
        with self.assertRaisesRegex(ValueError,'locally ignored'):q.clean(self.root)
    def test_actual_working_bytes(self):
        entries=q.inventory(self.root,'HEAD');(self.root/'file').write_text('wrong')
        with self.assertRaisesRegex(ValueError,'Working source'):q.validate_working(self.root,entries)
    def test_working_symlink(self):
        entries=q.inventory(self.root,'HEAD');(self.root/'file').unlink();(self.root/'file').symlink_to('/etc/hosts')
        with self.assertRaisesRegex(ValueError,'escapes'):q.validate_working(self.root,entries)
    def test_redirecting_environment_ignored(self):
        old=os.environ.get('GIT_DIR');os.environ['GIT_DIR']='/not/a/repository'
        try:self.assertEqual(q.clean(self.root,self.head),self.head)
        finally:
            if old is None:os.environ.pop('GIT_DIR',None)
            else:os.environ['GIT_DIR']=old

class WorkflowSource(unittest.TestCase):
    def test_actual_actions_identity_and_exact_tree(self):
        text=(q.ROOT/'.github/workflows/serial-logging-native.yml').read_text()
        self.assertNotIn('      GITHUB_SHA:',text)
        self.assertIn('SOURCE_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}',text)
        self.assertIn('rev-parse HEAD^{tree}',text)
        self.assertIn('rev-parse FETCH_HEAD^{tree}',text)
        self.assertIn('= "$GITHUB_SHA"',text)
    def test_pr_output_cannot_enter_publish_job(self):
        text=(q.ROOT/'.github/workflows/serial-logging-native.yml').read_text()
        self.assertIn("if: github.event_name == 'push' && needs.native.outputs.publication_enabled == 'true'",text)
        self.assertIn("github.event_name == 'pull_request' && 'qualification' || 'release'",text)
        shell=(q.ROOT/'scripts/run_serial_logging_native_ci.sh').read_text()
        self.assertIn("value=False if k=='publication_enabled' and os.environ.get('GITHUB_EVENT_NAME')=='pull_request'",shell)
        self.assertIn('transport_mode+=(--qualification-only)',shell)

class CIIdentity(unittest.TestCase):
    def setUp(self):
        import serial_logging_release as release
        self.release=release
        self.revision='a'*40
        self.p=dict(product='waveshare',release_branch='release/sd-apps-0.1.63',publication_enabled=True)
        self.repo='michaelrolphone-cmyk/RiscRTE-Wavshare-S3-Touch-AMOLED-2.06'
        self.ci=dict(GITHUB_REPOSITORY=self.repo,GITHUB_SHA=self.revision,GITHUB_WORKFLOW_SHA=self.revision,
            GITHUB_REF='refs/pull/28/merge',GITHUB_EVENT_NAME='pull_request',GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',
            GITHUB_HEAD_REF='consolidate/native-qualification-20261022',GITHUB_BASE_REF='main',SOURCE_HEAD_SHA='b'*40)
        self.ci['GITHUB_WORKFLOW_REF']=self.repo+'/.github/workflows/serial-logging-native.yml@'+self.ci['GITHUB_REF']
        patcher=mock.patch.object(q,'validate',return_value=self.revision)
        self.admission=patcher.start();self.addCleanup(patcher.stop)
        patcher=mock.patch.object(q,'git',return_value=b'equal-tree\n')
        self.git=patcher.start();self.addCleanup(patcher.stop)
    def test_qualification_preserves_real_merge_identity(self):
        self.release.verify_ci_identity(self.ci,self.p,self.revision,True)
        self.admission.assert_called_once_with(self.release.package.ROOT)
        self.assertEqual(self.git.call_args_list,[mock.call(self.release.package.ROOT,'rev-parse',self.revision+'^{tree}'),
            mock.call(self.release.package.ROOT,'rev-parse',self.ci['SOURCE_HEAD_SHA']+'^{tree}')])
    def test_default_release_rejects_pr(self):
        with self.assertRaisesRegex(ValueError,'Unexpected CI source branch'):
            self.release.verify_ci_identity(self.ci,self.p,self.revision)
        self.admission.assert_not_called()
    def test_default_release_retains_both_legacy_branches(self):
        for ref in ('refs/heads/provision/product-integration-053','refs/heads/'+self.p['release_branch']):
            ci=dict(self.ci,GITHUB_REF=ref,GITHUB_WORKFLOW_REF=self.repo+'/.github/workflows/serial-logging-native.yml@'+ref)
            self.release.verify_ci_identity(ci,self.p,self.revision)
        self.admission.assert_not_called()
    def test_wrong_pr_identities_rejected(self):
        changes={'GITHUB_REPOSITORY':'other/repo','GITHUB_SHA':'c'*40,'GITHUB_WORKFLOW_SHA':'c'*40,
            'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'push','GITHUB_HEAD_REF':'other-branch',
            'GITHUB_BASE_REF':'other-base','SOURCE_HEAD_SHA':'not-a-commit',
            'GITHUB_WORKFLOW_REF':self.repo+'/.github/workflows/other.yml@refs/pull/28/merge',
            'GITHUB_RUN_ID':'0','GITHUB_RUN_ATTEMPT':'0'}
        for key,value in changes.items():
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.release.verify_ci_identity(dict(self.ci,**{key:value}),self.p,self.revision,True)
    def test_changed_merge_tree_rejected(self):
        self.git.side_effect=[b'merge-tree\n',b'other-source-tree\n']
        with self.assertRaisesRegex(ValueError,'merge/source tree differs'):
            self.release.verify_ci_identity(self.ci,self.p,self.revision,True)
    def test_wrong_admitted_checkout_rejected(self):
        self.admission.return_value='c'*40
        with self.assertRaisesRegex(ValueError,'checkout differs'):
            self.release.verify_ci_identity(self.ci,self.p,self.revision,True)
    def test_dirty_current_source_rejected(self):
        self.admission.side_effect=ValueError('Dirty source checkout')
        with self.assertRaisesRegex(ValueError,'Dirty source checkout'):
            self.release.verify_ci_identity(self.ci,self.p,self.revision,True)

class TransportMode(unittest.TestCase):
    def test_qualification_is_explicit_and_never_publishable(self):
        import serial_logging_release as release
        p={'publication_enabled':True}
        row={'qualification_only':True,'publication_enabled':False}
        release.check_transport_mode(row,p,True)
        for candidate,mode in [(row,False),({'publication_enabled':False},False),
                (dict(row,publication_enabled=True),True),({'publication_enabled':False},True),
                (dict(row,qualification_only=1),True)]:
            with self.subTest(row=candidate,mode=mode),self.assertRaises(ValueError):
                release.check_transport_mode(candidate,p,mode)
        release.check_transport_mode({'publication_enabled':True},p)
    def test_default_publishers_reject_qualification_before_external_mutation(self):
        import serial_logging_release as release
        import publish_serial_logging_release as publisher
        import publish_serial_logging_feed as feed
        import build_serial_logging_pair as pair
        p={'publication_enabled':True,'release_tag':'synthetic-release'}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'qualification.json').write_text('{}')
            (root/'release.json').write_text(json.dumps({'qualification_only':True,'publication_enabled':False}))
            (root/'SHA256SUMS').write_text('synthetic guard fixture, not build evidence\n')
            with mock.patch.object(release.package,'pins',return_value=p),mock.patch.object(feed,'pins',return_value=p), \
                    mock.patch.object(pair,'pins',return_value=p),mock.patch.object(pair,'release_identity',return_value='a'*40), \
                    mock.patch.object(release,'release_names',return_value=(set(),{})), \
                    mock.patch.object(release,'check_directory',return_value={}), \
                    mock.patch.object(publisher,'gh') as gh, mock.patch.object(feed,'object_json') as api, \
                    mock.patch.object(feed,'find_release') as find:
                metadata=root/'metadata.json';metadata.write_text('{}')
                for action in (lambda:publisher.publish(root,'digest','a'*40),
                               lambda:feed.publish(root,'digest','a'*40),
                               lambda:pair.build(root,metadata,root,root,root/'output')):
                    with self.assertRaisesRegex(ValueError,'Transport qualification mode differs'):action()
                gh.assert_not_called();api.assert_not_called();find.assert_not_called()

if __name__=='__main__':unittest.main()
