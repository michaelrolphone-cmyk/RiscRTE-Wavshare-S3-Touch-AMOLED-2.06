#!/usr/bin/env python3
"""Production ELF validation/admission and volume snapshots for all SD apps.

Uses the exact native ELF's compiled exports. No Xtensa instructions execute.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
from package_minimal_sd import require,sha,record,encoded,write_tree

def qualify(runtime,helper,native,internal,payload,output):
    from elftools.elf.elffile import ELFFile
    RUNTIME=Path(runtime);ROOT=Path(output);require(not ROOT.exists(),'External evidence must be new');ROOT.mkdir(parents=True)
    path=Path(helper)/'scripts/verify_update_elf.py'
    spec=importlib.util.spec_from_file_location('exact_external_admission',path);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    exports=v.public_exports(ELFFile(io.BytesIO(native)))
    text=(RUNTIME/'src/ports/esp32s3/NativeBankStore.cpp').read_text();function,_,_=v.admission_source(text)
    source=v.admission_includes(text)+'''#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "private/elf_types.h"
#include "RiscBankStoreV1.h"
#include "bootstrap/RemovableAppImage.h"
extern "C" bool esp_elf_validate_file(const uint8_t*,size_t);
static bool safe=true;static uint32_t ticks=0;static const char* missing=nullptr;
static bool operationSafe(){return safe;}
namespace RiscPlatform {static uint32_t millis(){return ticks;}}
static void vTaskDelay(unsigned n){ticks+=n;}
struct Export {const char* name;uintptr_t address;};
static const Export exports[]={'''+','.join('{'+json.dumps(k)+','+str(val)+'u}' for k,val in sorted(exports.items()))+'''};

static uintptr_t elf_find_sym_default(const char* name){
 if(missing&&!strcmp(missing,name))return 0;
 for(const auto& e:exports)if(!strcmp(e.name,name))return e.address;
 return 0;
}
'''+v.extract(text,'bool allowedImport(')+'\n'+function+'''
struct Volume {
 std::string filename,path;FILE* stream=nullptr;size_t limit=4096;unsigned opens=0,closes=0,reads=0;
 risc_storage_volume_api_v1 api{};
 explicit Volume(const char* input,const char* selected,size_t readLimit):filename(input),path(selected),limit(readLimit){
  api.api_version=1;api.struct_size=sizeof(api);api.context=this;
  api.refresh=[](void*){return true;};api.ready=[](void*){return true;};
  api.file_open_read=[](void* c,const char* path,uint64_t* n)->uint32_t{
   auto& v=*static_cast<Volume*>(c);assert(v.path==path);++v.opens;v.stream=fopen(v.filename.c_str(),"rb");
   if(!v.stream)return 0;assert(!fseek(v.stream,0,SEEK_END));*n=ftell(v.stream);rewind(v.stream);return 1;
  };
  api.file_read=[](void* c,uint32_t handle,void* out,size_t n)->size_t{
   auto& v=*static_cast<Volume*>(c);assert(handle==1&&n<=4096);++v.reads;return fread(out,1,std::min(n,v.limit),v.stream);
  };
  api.file_close=[](void* c,uint32_t handle,bool commit){
   auto& v=*static_cast<Volume*>(c);assert(handle==1&&!commit);++v.closes;const bool ok=fclose(v.stream)==0;v.stream=nullptr;return ok;
  };
 }
};
int main(int argc,char** argv){
 assert(argc==4);std::ifstream file(argv[1],std::ios::binary);assert(file);
 std::ifstream importFile(argv[3]);assert(importFile);std::vector<std::string> imports;std::string name;while(std::getline(importFile,name))imports.push_back(name);
 std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(file),{});
 assert(esp_elf_validate_file(bytes.data(),bytes.size()));
 assert(admitElf(bytes.data(),bytes.size()));
 assert(!admitElf(bytes.data(),bytes.size(),ElfRole::Driver));
 safe=false;assert(!admitElf(bytes.data(),bytes.size()));safe=true;
 for(const auto& name:imports){missing=name.c_str();assert(!admitElf(bytes.data(),bytes.size()));}missing=nullptr;
 assert(admitElf(bytes.data(),bytes.size()));
 for(size_t length:{size_t(0),size_t(51),bytes.size()-1})assert(!admitElf(bytes.data(),length));
 auto malformed=bytes;malformed[0]=0;assert(!admitElf(malformed.data(),malformed.size()));
 unsigned snapshots=0,reads=0;
 for(size_t limit:{size_t(4096),size_t(37)}){
  Volume volume(argv[1],argv[2],limit);RiscBoot::RemovableAppImage image;
  assert(image.read(&volume.api,false,argv[2],{malloc,free,
   [](void*){return operationSafe();},[](void*,size_t){vTaskDelay(1);return operationSafe();},nullptr}));
  assert(!image.closeRetained&&image.size==bytes.size()&&!memcmp(image.bytes,bytes.data(),bytes.size()));
  assert(volume.opens==1&&volume.closes==1);assert(admitElf(image.bytes,image.size));
  free(image.bytes);++snapshots;reads+=volume.reads;
 }
 printf("{\\"production_structural_validation\\":true,\\"production_application_admission\\":true,\\"driver_role_rejected\\":true,\\"unsafe_rejected\\":true,\\"missing_import_rejections\\":%zu,\\"malformed_or_truncated_rejections\\":4,\\"production_removable_image_snapshots\\":%u,\\"volume_reads\\":%u,\\"target_instructions_executed\\":false}\\n",imports.size(),snapshots,reads);
}
'''
    (ROOT/'admission.cpp').write_text(source)
    write_tree(ROOT/'payload',payload)
    includes=['-I'+str(RUNTIME/p) for p in ['src','sdk/app','sdk/driver','sdk/hardware','lib/elf_loader/include','test/native_bank_stubs']]
    boot=json.loads(internal['boot.json']);app_rows=[]
    for policy in boot['app_capabilities']:
        if not policy.get('image_source'):continue
        manifest=json.loads(internal[policy['manifest']]);image=policy['image_source'];name=image['path']
        require(image=={'path':name,'volume_instance':12} and manifest['file_name'] not in internal,'External policy/internal absence differs')
        data=payload[name];elf=ELFFile(io.BytesIO(data))
        imports=sorted({s.name for sec in elf.iter_sections() if sec['sh_type'] in ('SHT_DYNSYM','SHT_SYMTAB') for s in sec.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'})
        require(set(imports)<=exports.keys(),'Unresolved external imports: '+name)
        grants={(x['capability'],x['api']) for x in policy.get('grants',[])}
        require(all((x['capability'],x['api']) in grants for x in manifest['requires']),'Ungrantable required external capability: '+name)
        external_manifest=json.loads(payload[str(Path(name).parent/'manifest.json')])
        require(manifest==external_manifest or (manifest['id']=='lora_messages' and manifest['version']=='0.1.16' and external_manifest['version']=='0.1.17' and {k:v for k,v in manifest.items() if k!='version'}=={k:v for k,v in external_manifest.items() if k!='version'}),'External manifest differs')
        import_path=ROOT/(manifest['id']+'-imports.txt');import_path.write_text(''.join(x+'\n' for x in imports))
        app_rows.append(dict(id=manifest['id'],path=name,elf=record(data),imports=imports,import_path=str(import_path),tests=[]))
    require(len(app_rows)==22,'Incomplete external app inventory')
    commands=[]
    def run(command,**kwargs):
        commands.append(list(map(str,command)));return subprocess.run(list(map(str,command)),check=True,**kwargs)
    for sanitized in (False,True):
        suffix='sanitized' if sanitized else 'normal';flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie'] if sanitized else []
        run(['cc','-std=c11',*flags,*includes,'-c',RUNTIME/'lib/elf_loader/src/esp_elf_validate.c','-o',ROOT/('validator-'+suffix+'.o')])
        run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*flags,*includes,ROOT/'admission.cpp',ROOT/('validator-'+suffix+'.o'),'-o',ROOT/('admission-'+suffix)])
        for row in app_rows:
            outcome=run([ROOT/('admission-'+suffix),ROOT/'payload'/row['path'],'/'+row['path'],row['import_path']],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
            (ROOT/(row['id']+'-'+suffix+'.log')).write_text(outcome.stdout+outcome.stderr)
            row['tests'].append(dict(json.loads(outcome.stdout),sanitized=sanitized))
    for row in app_rows:row.pop('import_path')
    result=dict(schema=1,runtime_commit=subprocess.check_output(['git','-C',str(RUNTIME),'rev-parse','HEAD'],text=True).strip(),native_elf_sha256=sha(native),native_store_abi=v.verify_native_store_abi(native,3),
        external_app_count=22,apps=app_rows,public_export_count=len(exports),all_required_capabilities_explicitly_granted=True,
        fixture_sha256=sha(source.encode()),commands=commands,hardware_tested=False,target_instructions_executed=False,target_symbol_resolver_executed=False,
        source_files_sha256={x:sha((RUNTIME/x).read_bytes()) for x in ['src/ports/esp32s3/NativeBankStore.cpp','src/runtime/packages/ElfAdmission.h','lib/elf_loader/src/esp_elf_validate.c','src/bootstrap/RemovableAppImage.h','src/bootstrap/RuntimeFileImage.h','src/runtime/storage/VolumeImageFiles.h']})
    (ROOT/'qualification.json').write_bytes(encoded(result));return result
