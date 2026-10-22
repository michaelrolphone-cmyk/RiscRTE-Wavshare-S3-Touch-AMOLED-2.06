#!/usr/bin/env python3
import copy
import hashlib
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

if __name__=='__main__':unittest.main()
