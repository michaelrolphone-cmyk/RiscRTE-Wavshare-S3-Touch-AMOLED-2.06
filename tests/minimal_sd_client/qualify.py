import argparse,json,hashlib,subprocess,pathlib,os
p=argparse.ArgumentParser();p.add_argument('--internal',type=pathlib.Path,required=True);p.add_argument('--historical-headers',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
root=a.output.resolve();root.mkdir(parents=True,exist_ok=True)
internal=a.internal.resolve();headers=a.historical_headers.resolve()
custody=json.loads((pathlib.Path(__file__).parent/'source-custody.json').read_bytes())
for row in custody['files']:
 assert hashlib.sha256((headers/pathlib.Path(row['source_path']).name).read_bytes()).hexdigest()==row['sha256']
rows=[]
for p in sorted(internal.glob('*.json')):
 j=json.loads(p.read_bytes())
 if j.get('type')=='application' and j.get('launcher_visible',True):
  rows.append(dict(id=j['id'],file_name=j['file_name'],display_name=j.get('display_name',j['id']),icon=j.get('icon',''),min_firmware_version=j.get('min_firmware_version','')))
assert len(rows)==24
assert not any(x['id'] in ['twatch-clock-return','springboard','watch-bringup'] for x in rows)
initializers=',\n'.join('{.struct_size=sizeof(risc_app_catalog_entry_v1),.flags=1,'+','.join('.'+k+'='+json.dumps(v) for k,v in r.items())+'}' for r in rows)
source=r'''#include "PortableAppCatalog.h"
#include <assert.h>
#include <stdio.h>
static risc_app_catalog_entry_v1 rows[]={ROWS};
static unsigned acquire_calls,release_calls,snapshots;
static int mode;
static int32_t snapshot(void*c,risc_app_catalog_snapshot_v1*out){(void)c;out->count=24;out->generation=mode==2&&snapshots++?2:1;return 0;}
static int32_t get(void*c,uint64_t generation,uint32_t index,risc_app_catalog_entry_v1*out){(void)c;assert(generation==1&&index<24);*out=rows[mode==1&&index==1?0:index];if(mode==3)out->flags=0;return 0;}
static risc_app_catalog_v1 service={1,sizeof(service),NULL,snapshot,get};
static bool acquire(const char*n,uint32_t version,uint64_t instance,risc_runtime_capability_v1*out){assert(!strcmp(n,"app.catalog")&&version==1&&instance==0);++acquire_calls;out->api=&service;out->slot=1;out->generation=1;return true;}
static bool release(risc_runtime_capability_v1*g){++release_calls;memset(g,0,sizeof(*g));return true;}
static const risc_runtime_api_v1 rt={.api_version=1,.struct_size=sizeof(rt),.acquire=acquire,.release=release};
int main(void){
 portable_app_catalog c={0};assert(portable_catalog_refresh(&c,&rt));assert(c.count==24);
 for(unsigned i=0;i<24;++i){portable_app_catalog_launch l;assert(portable_catalog_launch_prepare(&c,i,&l));assert(!strcmp(l.route,rows[i].file_name));assert(portable_catalog_launch_valid(&c,&l));}
 assert(portable_catalog_close(&c,&rt));
 mode=1;assert(!portable_catalog_refresh(&c,&rt));assert(c.count==0);assert(portable_catalog_close(&c,&rt));
 mode=2;snapshots=0;assert(!portable_catalog_refresh(&c,&rt));assert(c.count==0);assert(portable_catalog_close(&c,&rt));
 mode=3;assert(portable_catalog_refresh(&c,&rt));assert(c.count==24);for(unsigned i=0;i<24;++i){portable_app_catalog_launch l;assert(!portable_catalog_launch_prepare(&c,i,&l));}assert(portable_catalog_close(&c,&rt));
 assert(acquire_calls==4&&release_calls==4);puts("historical Springboard client: 24-row refresh/launch, duplicate and generation rejection, unavailable-row launch rejection passed");return 0;
}
'''.replace('ROWS',initializers)
(root/'client.c').write_text(source)
commands=[];results=[]
for san in [False,True]:
 exe=root/('client-san' if san else 'client')
 cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-I'+str(headers),str(root/'client.c'),'-o',str(exe)]
 if san:cmd+=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']
 subprocess.run(cmd,check=True);commands.append(cmd)
 env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=0'
 r=subprocess.run([str(exe)],check=True,text=True,capture_output=True,env=env);results.append({'sanitized':san,'stdout':r.stdout})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'schema':1,'passed':True,'system_source':'f31f89636304d202c49884e2e9b2e0b2ec5fb891','retained_springboard_elf_sha256':sha(internal/'springboard.elf'),'retained_manifest_sha256':sha(internal/'springboard.json'),'visible_rows':rows,'historical_headers':{p.name:sha(p) for p in sorted(headers.glob('*.h'))},'commands':commands,'results':results,'coverage':['Production historical PortableAppCatalog client functions on exact candidate manifest identities/metadata','24 rows and exact launch routes; hidden shim omitted','Duplicate publication and generation change rejected; unavailable rows do not launch'],'modeled_boundaries':['Runtime app.catalog snapshot/get is modeled here; separate qualification runs actual Runtime graph','No target instructions, renderer, hardware or allocator capacity proof'],'hardware_tested':False}
(root/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':True,'cases':8,'visible_rows':24,'receipt':str(root/'qualification.json')}))
