#!/usr/bin/env python3
"""Same-source release and publisher guards; synthetic envelopes are not attestations."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import package_stat_diagnostic as package
import stat_diagnostic_release as release
import publish_stat_diagnostic_release as publisher
import publish_stat_diagnostic_feed as feed
import test_provisioning_release as historical

class Contracts(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        self.publisher_selection=patch.object(publisher, 'package', SimpleNamespace(pins=lambda: dict(package.pins(),publication_enabled=True)))
        self.publisher_selection.start();self.addCleanup(self.publisher_selection.stop)

    def fixture(self):
        q,_,revision=historical.ReleaseContracts().fixture();p=package.pins();p['runtime_revision']=p['runtime_revision'] or '3f3587a0dbd06c898a80cce1f97455b23aa19ec6';c=package.baseline_contract()
        q.update(version=p['version'],baseline_contract=c,preservation=json.loads((package.ROOT/'docs/minimal-sd-apps/composition-pre-native.json').read_bytes()),navigation={'passed':True,'hardware_tested':False},packing={'empty_blocks':791,'independent_round_trip_verified':True})
        q['input_lock']['candidate_version']=p['version'];q['input_lock']['native_files']={'firmware_elf':{'sha256':'5'*64}}
        for role,row in q['input_lock']['sources'].items():row['revision']=revision if role=='product' else p[role+'_revision']
        q['controlled_build']['sources']=q['input_lock']['sources']
        q['default'].update(default_sha256=p['default_sha256'],default_bytes=p['default_bytes'],manifest_sha256=p['default_manifest_sha256'])
        for name in ('admission','admission_sanitized'):
            row=q[name];row['elf_count']=43;row.pop('preserving_transition')
            row.update(placement_transition={'prepared':True,'cohort_validated':True,'elf_count':43},unauthorized_namespace_control={'expected_rejection':True,'cohort_validated':False,'elf_count':0,'control_packaged':False})
        f=q['feed'];f['core_inventory_files']=111;f['core_inventory_elfs']=43;f['receipt']['file_count']=111;f['controller']['files_selected']=111
        q['artifacts'].update({n:{'bytes':1,'sha256':'3'*64} for n in release.PAYLOAD})
        test=dict(production_structural_validation=True,production_application_admission=True,production_removable_image_snapshots=2,missing_import_rejections=1,driver_role_rejected=True,unsafe_rejected=True,malformed_or_truncated_rejections=4)
        q['external_apps']=dict(external_app_count=22,apps=[{'imports':['memcpy'],'tests':[dict(test,sanitized=x) for x in (False,True)]} for _ in range(22)],native_elf_sha256='5'*64,runtime_commit=p['runtime_revision'],all_required_capabilities_explicitly_granted=True,target_instructions_executed=False,hardware_tested=False)
        q['historical_springboard_client']=dict(passed=True,hardware_tested=False,system_source='f31f89636304d202c49884e2e9b2e0b2ec5fb891',visible_rows=[{}]*24,results=[dict(sanitized=x) for x in (False,True)],retained_springboard_elf_sha256=c['files']['springboard.elf']['sha256'],retained_manifest_sha256=c['files']['springboard.json']['sha256'])
        nav=q['navigation'];nav.update(runtime_commit=p['runtime_revision'],external_app_count=22,visible_catalog_count=24,provider_count=38,clock_hidden=True,newly_moved_internal_images_absent=21,production_runtime_graph_unchanged=True,production_structural_validation=True,production_serial_per_file_installation=True,target_instructions_executed=False,tests=[])
        for sanitized in (False,True):
            for mode in ('normal','no-card','missing','malformed','removed','relocation'):
                nav['tests'].append(dict(sanitized=sanitized,mode=mode,catalog_checks=2,home_invocations=53,hidden_shim_returns=2,preference_checks=1,prior_invocation_preference_reads=1,app_data_checks=1,external_failures_recovered=0 if mode=='normal' else 44))
            for scenario in ('clean','known-lora'):
                nav['tests'].append(dict(sanitized=sanitized,scenario=scenario,production_serial_protocol=True,namespace=12,preserved_sentinels=5,verified_file_bytes=6226968,hardware_tested=False,create_files=45 if scenario=='clean' else 42,replace_files=45 if scenario=='clean' else 48,verified_prior_hashes=0 if scenario=='clean' else 3))
        q['preservation'].update(moved_elfs=[], changed_store_files=['cohort.json'],
            external_payload_byte_identical=True, all_existing_packaged_assets_retained=True,
            external_files_inventory=c['external_files'], external_bytes=3113484, external_max_file_bytes=288112)
        commands=[['c++','production.cpp']]
        q['serial_stat_boundaries']=dict(schema=1,hardware_tested=False,leak_sanitizer=False,
            cases=[dict(build=build,group=group,case=case,stdout='PASS',stderr='')
                   for build in ('normal','sanitized')
                   for group,cases in [('readiness',('active-session','sleep-prepared','owner-refused','io-unavailable')),
                                       ('home',('unavailable','busy','late-retained'))] for case in cases],
            compilations=[dict(build=build,commands=commands) for build in ('normal','sanitized')],
            inputs_sha256={'/synthetic/production.c':'9'*64})
        sources=('src/bootstrap/Runtime.cpp','src/runtime/serial/Files.cpp','src/ports/esp32s3/CpuPort.cpp',
                 'src/ports/esp32s3/NativeSettingsLifecycle.cpp','src/ports/esp32s3/NativeSettingsMaintenance.cpp',
                 'src/ports/esp32s3/NativeSettingsBootstrap.cpp','lib/storage_fatfs/fatfs/ff.c',
                 'tests/native_serial_liveness/sd_fixture.c')
        q['native_serial_scheduler']=dict(schema=1,passed=True,expectation='fixed',runtime_commit=p['runtime_revision'],
            runtime_dirty=False,hardware_tested=False,target_instructions_executed=False,leak_sanitizer=False,
            cases=[dict(build=build,case=case,returncode=0,expected_returncode=0,passed=True,log_sha256='8'*64)
                   for build in ('normal','sanitized') for case in ('full-progress','full-pace8','full-pace16','full-pace32','full-slow','full-stall')],
            compilations=[dict(build=build,commands=[['c++', *(['-fsanitize=address,undefined'] if build=='sanitized' else []), '-c','/synthetic/'+source,'-o','/synthetic/object.o'] for source in sources]) for build in ('normal','sanitized')],
            input_sha256={'/synthetic/'+source:'9'*64 for source in sources})
        q['provisioning']['linked_layout']['static_workspaces']['serial_workspace']['bytes']=2800
        baseline=json.loads((package.DOCS/'baseline-target-memory.json').read_bytes())
        from stat_diagnostic_memory import compare
        target=copy.deepcopy(baseline['linked'])
        for name,size in p['target_workspace_bytes'].items(): target['workspaces'][name]['bytes']=size
        q['native']['radio_iq']=copy.deepcopy(baseline['iq'])
        q['target_memory']=compare(target,baseline['linked'],q['native']['radio_iq'],baseline['iq'],p['target_workspace_bytes'])
        return q,p,revision
    def test_envelope(self):
        q,p,r=self.fixture();self.assertEqual(release.check_qualification(q,p,r),q['input_lock'])
    def test_duplicate_cases_and_failed_scheduler_are_rejected(self):
        q,p,r=self.fixture()
        for field in ('serial_stat_boundaries','native_serial_scheduler'):
            bad=copy.deepcopy(q);bad[field]['cases'][-1]=copy.deepcopy(bad[field]['cases'][0])
            with self.subTest(field=field),self.assertRaises(ValueError):release.check_qualification(bad,p,r)
        for field,value in [('passed',False),('returncode',2),('expected_returncode',2),('log_sha256','not-a-digest')]:
            bad=copy.deepcopy(q);bad['native_serial_scheduler']['cases'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):release.check_qualification(bad,p,r)
    def test_scheduler_requires_compiled_production_sources_and_sanitizers(self):
        q,p,r=self.fixture()
        for action in ('missing-source','missing-sanitizer','wrong-sanitizer'):
            bad=copy.deepcopy(q);commands=bad['native_serial_scheduler']['compilations'][1]['commands']
            if action=='missing-source':commands.pop()
            elif action=='missing-sanitizer':commands[0].remove('-fsanitize=address,undefined')
            else:commands[0][1]='-fsanitize=undefined'
            with self.subTest(action=action),self.assertRaises(ValueError):release.check_qualification(bad,p,r)
    def test_canonical_release_id_cannot_change(self):
        row={'id':123,'target_commitish':'1'*40}
        self.assertEqual(publisher.check_release_source(row,'1'*40),123)
        for changed,revision,release_id in [(dict(row,id=124),'1'*40,123),(row,'2'*40,123),
                                           (dict(row,id=True),'1'*40,None),(None,'1'*40,None)]:
            with self.assertRaises(ValueError):publisher.check_release_source(changed,revision,release_id)
    def test_mutations(self):
        q,p,r=self.fixture()
        mutations={('hardware_tested',):True,('native_rebuilt',):False,('version',):'0.1.59',('source_revision',):'0'*40,
         ('controlled_build','same_process_qualification'):False,('controlled_build','fresh_build'):False,
         ('preservation','internal_apps'):6,('preservation','internal_providers'):37,('preservation','internal_files'):132,
         ('preservation','external_files'):44,('preservation','clock_hidden'):False,('preservation','data_mapping_preserved'):False,
         ('packing','empty_blocks'):3,('external_apps','external_app_count'):21,('external_apps','native_elf_sha256'):'0'*64,
         ('external_apps','runtime_commit'):'0'*40,('external_apps','target_instructions_executed'):True,
         ('navigation','passed'):False,('navigation','visible_catalog_count'):27,('navigation','tests'):[],('navigation','runtime_commit'):'0'*40,('navigation','hardware_tested'):True,('feed','core_inventory_files'):132,
         ('admission','elf_count'):64,('admission','placement_transition','cohort_validated'):False,
         ('admission','unauthorized_namespace_control','cohort_validated'):True,('provisioning','linked_layout','types','platform_slots'):40,
         ('preservation','moved_elfs'):['clock.elf'],('preservation','changed_store_files'):['boot.json'],
         ('preservation','external_payload_byte_identical'):False,('preservation','all_existing_packaged_assets_retained'):False,
         ('preservation','external_files_inventory'):{},('preservation','external_bytes'):3113483,
         ('serial_stat_boundaries','cases'):[],('serial_stat_boundaries','hardware_tested'):True,
         ('serial_stat_boundaries','compilations'):[],('serial_stat_boundaries','inputs_sha256'):{},
         ('native_serial_scheduler','passed'):False,('native_serial_scheduler','expectation'):'baseline',
         ('native_serial_scheduler','cases'):[],('native_serial_scheduler','runtime_commit'):'0'*40,
         ('native_serial_scheduler','runtime_dirty'):True,('native_serial_scheduler','hardware_tested'):True,
         ('native_serial_scheduler','target_instructions_executed'):True,('native_serial_scheduler','input_sha256'):{}}
        for path,value in mutations.items():
            bad=copy.deepcopy(q);row=bad
            for key in path[:-1]:row=row[key]
            row[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):release.check_qualification(bad,p,r)
    def test_feed_is_version_specific_and_immutable(self):
        new={'apps':[],'profiles':{'core':[]},'boot_profiles':{'core':{'profile':{'files':[{}]*111,'image':{'url':'https://example.test/test-sd-apps-0.1.60/bootfs-hash.bin'}},'mirrors':[]}}}
        self.assertTrue(feed.select_update(None,new,'test-sd-apps-0.1.60'))
        self.assertFalse(feed.select_update(new,new,'test-sd-apps-0.1.60'))
        with self.assertRaises(ValueError):feed.select_update({},new,'test-sd-apps-0.1.60')
    def test_tag_exact_source(self):
        row={'ref':'refs/tags/test-sd-apps-0.1.60','object':{'type':'commit','sha':'1'*40}}
        self.assertTrue(publisher.check_tags([row],'test-sd-apps-0.1.60','0.1.60','1'*40))
        with self.assertRaises(ValueError):publisher.check_tags([row],'test-sd-apps-0.1.60','0.1.60','2'*40)
        with self.assertRaises(ValueError):publisher.check_tags([dict(row,ref='refs/tags/test-other-0.1.60')],'test-sd-apps-0.1.60','0.1.60','1'*40)
    def test_canonical_extension_resume_verifies_base(self):
        p=package.pins();r='1'*40;tag=p['release_tag'];base={'SHA256SUMS':b'sums','RELEASE-NOTES.txt':b'notes'}
        row={'id':123,'target_commitish':r,'tag_name':tag,'name':'Waveshare '+p['version']+' complete SD apps, hardware pending','body':'notes','prerelease':True,'draft':False,'html_url':'https://example.test/release',
             'assets':[{'name':name,'state':'uploaded'} for name in base]+[{'name':'Waveshare-'+p['version']+'-SD-Apps-known-lora.zip','state':'uploaded'}]}
        ref={'ref':'refs/tags/'+tag,'object':{'type':'commit','sha':r}}
        calls=[]
        def api(*args,**kwargs):return [[ref]] if '--paginate' in args else ref
        def gh(*args,**kwargs):
            self.assertEqual(args[:2],('release','download'));calls.append(args)
            name=args[args.index('--pattern')+1];Path(args[args.index('--dir')+1],name).write_bytes(base[name])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in base.items():(root/name).write_bytes(data)
            with patch.object(publisher,'verify_output') as verify,patch.object(publisher,'object_json',side_effect=api),patch.object(publisher,'find_release',return_value=row),patch.object(publisher,'gh',side_effect=gh):
                publisher.publish(root,'2'*64,r);self.assertEqual(verify.call_count,2)
            self.assertEqual(len(calls),2)
            row['assets'][-1]['name']='unexpected.zip'
            with patch.object(publisher,'verify_output'),patch.object(publisher,'object_json',side_effect=api),patch.object(publisher,'find_release',return_value=row),self.assertRaises(ValueError):publisher.publish(root,'2'*64,r)
    def test_published_release_cannot_be_incomplete(self):
        row={'tag_name':'test-sd-apps-0.1.60','prerelease':True,'draft':False,'assets':[]}
        with self.assertRaises(ValueError):publisher.check_release(row,row['tag_name'],{'factory.bin'})
        row['draft']=True;self.assertEqual(publisher.check_release(row,row['tag_name'],{'factory.bin'}),{'factory.bin'})
    def publication_fixture(self):
        p=package.pins();revision='1'*40;tag=p['release_tag']
        base={'SHA256SUMS':b'sums','RELEASE-NOTES.txt':b'notes'}
        row=dict(id=123,target_commitish=revision,tag_name=tag,draft=True,prerelease=True,
                 name='Waveshare '+p['version']+' complete SD apps, hardware pending',
                 body='notes',html_url='https://example.test/release',assets=[])
        ref={'ref':'refs/tags/'+tag,'object':{'type':'commit','sha':revision}}
        def api(*args,**kwargs):return [[ref]] if '--paginate' in args else ref
        return revision,base,row,api
    def test_created_release_transient_visibility_creates_once(self):
        revision,base,row,api=self.publication_fixture();reads=[];commands=[]
        def find(*args):
            reads.append(args)
            return None if len(reads)<=2 else copy.deepcopy(row)
        def gh(*args,**kwargs):
            commands.append(args)
            if args[:2]==('release','upload'):
                row['assets']=[{'name':name,'state':'uploaded'} for name in base]
            elif args[:2]==('release','edit'):row['draft']=False
            elif args[:2]==('release','download'):
                output=Path(args[args.index('--dir')+1]);output.mkdir(parents=True,exist_ok=True)
                for name,data in base.items():(output/name).write_bytes(data)
            else:self.assertEqual(args[:2],('release','create'))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in base.items():(root/name).write_bytes(data)
            with patch.object(publisher,'verify_output'),patch.object(publisher,'object_json',side_effect=api),\
                 patch.object(publisher,'find_release',side_effect=find),patch.object(publisher,'gh',side_effect=gh),\
                 patch.object(publisher.time,'sleep') as sleep:
                publisher.publish(root,'2'*64,revision)
                sleep.assert_called_once_with(1)
        self.assertEqual(sum(command[:2]==('release','create') for command in commands),1)
        self.assertEqual(sum(command[:2]==('release','upload') for command in commands),1)
        self.assertEqual(sum(command[:2]==('release','edit') for command in commands),1)
    def test_created_release_stable_absence_never_recreates(self):
        revision,base,row,api=self.publication_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in base.items():(root/name).write_bytes(data)
            with patch.object(publisher,'verify_output'),patch.object(publisher,'object_json',side_effect=api),\
                 patch.object(publisher,'find_release',return_value=None) as find,patch.object(publisher,'gh') as gh,\
                 patch.object(publisher.time,'sleep') as sleep:
                with self.assertRaisesRegex(ValueError,'bounded read-only visibility checks'):
                    publisher.publish(root,'2'*64,revision)
                self.assertEqual(find.call_count,5)
                self.assertEqual([call.args for call in sleep.call_args_list],[(1,),(2,),(4,)])
                self.assertEqual(gh.call_count,1);self.assertEqual(gh.call_args.args[:2],('release','create'))
    def test_created_release_source_mismatch_is_not_visibility_retry(self):
        revision,base,row,api=self.publication_fixture();wrong=dict(row,target_commitish='2'*40)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in base.items():(root/name).write_bytes(data)
            with patch.object(publisher,'verify_output'),patch.object(publisher,'object_json',side_effect=api),\
                 patch.object(publisher,'find_release',side_effect=[None,None,wrong,row]) as find,\
                 patch.object(publisher,'gh') as gh,patch.object(publisher.time,'sleep') as sleep:
                with self.assertRaisesRegex(ValueError,'Release source identity differs'):
                    publisher.publish(root,'2'*64,revision)
                self.assertEqual(find.call_count,3);sleep.assert_called_once_with(1)
                self.assertEqual(gh.call_count,1);self.assertEqual(gh.call_args.args[:2],('release','create'))

if __name__=='__main__':unittest.main()
