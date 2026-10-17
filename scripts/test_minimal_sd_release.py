#!/usr/bin/env python3
"""Same-source release and publisher guards; synthetic envelopes are not attestations."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import package_minimal_sd as package
import minimal_sd_release as release
import publish_minimal_sd_release as publisher
import publish_minimal_sd_feed as feed
from test_provisioning_release import ReleaseContracts as Historical

class Contracts(unittest.TestCase):
    def fixture(self):
        q,_,revision=Historical().fixture();p=package.pins();c=package.baseline_contract()
        q.update(version=p['version'],baseline_contract=c,preservation=json.loads((package.DOCS/'composition-pre-native.json').read_bytes()),navigation={'passed':True,'hardware_tested':False},packing={'empty_blocks':791,'independent_round_trip_verified':True})
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
        return q,p,revision
    def test_envelope(self):
        q,p,r=self.fixture();self.assertEqual(release.check_qualification(q,p,r),q['input_lock'])
    def test_mutations(self):
        q,p,r=self.fixture()
        mutations={('hardware_tested',):True,('native_rebuilt',):False,('version',):'0.1.56',('source_revision',):'0'*40,
         ('controlled_build','same_process_qualification'):False,('controlled_build','fresh_build'):False,
         ('preservation','internal_apps'):6,('preservation','internal_providers'):37,('preservation','internal_files'):132,
         ('preservation','external_files'):44,('preservation','clock_hidden'):False,('preservation','data_mapping_preserved'):False,
         ('packing','empty_blocks'):3,('external_apps','external_app_count'):21,('external_apps','native_elf_sha256'):'0'*64,
         ('external_apps','runtime_commit'):'0'*40,('external_apps','target_instructions_executed'):True,
         ('navigation','passed'):False,('navigation','visible_catalog_count'):27,('navigation','tests'):[],('navigation','runtime_commit'):'0'*40,('navigation','hardware_tested'):True,('feed','core_inventory_files'):132,
         ('admission','elf_count'):64,('admission','placement_transition','cohort_validated'):False,
         ('admission','unauthorized_namespace_control','cohort_validated'):True,('provisioning','linked_layout','types','platform_slots'):40}
        for path,value in mutations.items():
            bad=copy.deepcopy(q);row=bad
            for key in path[:-1]:row=row[key]
            row[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):release.check_qualification(bad,p,r)
    def test_feed_is_version_specific_and_immutable(self):
        new={'apps':[],'profiles':{'core':[]},'boot_profiles':{'core':{'profile':{'files':[{}]*111,'image':{'url':'https://example.test/test-sd-apps-0.1.57/bootfs-hash.bin'}},'mirrors':[]}}}
        self.assertTrue(feed.select_update(None,new,'test-sd-apps-0.1.57'))
        self.assertFalse(feed.select_update(new,new,'test-sd-apps-0.1.57'))
        with self.assertRaises(ValueError):feed.select_update({},new,'test-sd-apps-0.1.57')
    def test_tag_exact_source(self):
        row={'ref':'refs/tags/test-sd-apps-0.1.57','object':{'type':'commit','sha':'1'*40}}
        self.assertTrue(publisher.check_tags([row],'test-sd-apps-0.1.57','0.1.57','1'*40))
        with self.assertRaises(ValueError):publisher.check_tags([row],'test-sd-apps-0.1.57','0.1.57','2'*40)
        with self.assertRaises(ValueError):publisher.check_tags([dict(row,ref='refs/tags/test-other-0.1.57')],'test-sd-apps-0.1.57','0.1.57','1'*40)
    def test_canonical_extension_resume_verifies_base(self):
        p=package.pins();r='1'*40;tag=p['release_tag'];base={'SHA256SUMS':b'sums','RELEASE-NOTES.txt':b'notes'}
        row={'tag_name':tag,'name':'Waveshare '+p['version']+' complete SD apps, hardware pending','body':'notes','prerelease':True,'draft':False,'html_url':'https://example.test/release',
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
        row={'tag_name':'test-sd-apps-0.1.57','prerelease':True,'draft':False,'assets':[]}
        with self.assertRaises(ValueError):publisher.check_release(row,row['tag_name'],{'factory.bin'})
        row['draft']=True;self.assertEqual(publisher.check_release(row,row['tag_name'],{'factory.bin'}),{'factory.bin'})

if __name__=='__main__':unittest.main()
