#!/usr/bin/env python3
"""Qualify LoRa 0.1.17 against the exact delivered Wave 0.1.55 native exports.

No Xtensa instructions run. Host tests execute exact production source for ELF
structure/admission and volume-image snapshots, with a read-only POSIX-backed
volume fixture and addresses obtained from the delivered native export tables.
"""
import argparse, hashlib, importlib.util, io, json, os, subprocess, sys, zipfile
from pathlib import Path

if not __debug__:
    raise RuntimeError('Python optimization disables qualification assertions')


def sha(x): return hashlib.sha256(x).hexdigest()
def run(cmd, **kw):
    return subprocess.run([str(x) for x in cmd], check=True, **kw)
def git(path, *args):
    return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()

def check_runtime_inputs(runtime):
    assert git(runtime, 'rev-parse', 'HEAD') == 'f410c8592ecb37a520df3f29db8d88234dc7ddc9'
    paths = ('src', 'lib', 'sdk', 'test')
    assert not git(runtime, 'diff', 'HEAD', '--', *paths), 'Modified Runtime compile input'
    # Include ignored files: an untracked header can still affect compilation.
    assert not git(runtime, 'ls-files', '--others', '--', *paths), 'Untracked Runtime compile input'


def main():
    from elftools.elf.elffile import ELFFile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True,
                        help='Root containing exact runtime/, baseline/, and lora/ inputs')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--helper-repo', type=Path, required=True)
    parser.add_argument('--native-evidence', type=Path, required=True)
    args = parser.parse_args()
    BASE, ROOT, RUNTIME = args.base.resolve(), args.work.resolve(), args.base.resolve() / 'runtime'
    ROOT.mkdir(parents=True, exist_ok=True)
    helper = subprocess.check_output(['git', '-C', str(args.helper_repo), 'show',
        '74f7491dc470b92dfa41fce41bf0c500f3714a94:scripts/verify_update_elf.py'])
    helper_path = ROOT / 'verify_update_elf.py'
    helper_path.write_bytes(helper)
    spec = importlib.util.spec_from_file_location('pinned_verify_update_elf', helper_path)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)

    check_runtime_inputs(RUNTIME)
    archive=args.native_evidence.resolve()
    assert sha(archive.read_bytes()) == '99fc3ab1338f98ba366cd3a82cff92d49d1d244c47c2a9876db5b8b0d7f04f5b'
    with zipfile.ZipFile(archive) as z:
        native=z.read('build/riscrte_native.elf')
        nativebin=z.read('build/riscrte_native.bin')
    rawq=(BASE/'baseline/qualification.json').read_bytes()
    assert sha(rawq)=='d93db5acee3d63de7bf59afb764b433bf90f0d91d3a8ba78b05a6c3d0dbdc724'
    nativeq=json.loads(rawq)
    assert sha(native) == nativeq['admission']['native_elf_sha256']
    assert sha(nativebin)=='8a7296faf233c47f4a42a5c95e763bd6cdb8204cf88fec2a066e83a0a5390ccb'
    elf=BASE/'lora/Waveshare-LoRa-0.1.17-SD-card/Apps/lora_messages/lora_messages.elf'
    data=elf.read_bytes()
    assert len(data)==136960 and sha(data)=='81877ba548ae0c45f4ebbbe71c53753159a4b3a28282ac9ce3c5ef63ad90c0f5'
    exports=v.public_exports(ELFFile(io.BytesIO(native)))
    app=ELFFile(io.BytesIO(data))
    imports=sorted({s.name for sec in app.iter_sections() if sec['sh_type'] in ('SHT_DYNSYM','SHT_SYMTAB') for s in sec.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'})
    assert set(imports) <= exports.keys()
    text=(RUNTIME/'src/ports/esp32s3/NativeBankStore.cpp').read_text()
    function,_,_=v.admission_source(text)
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
static const char* imports[]={'''+','.join(json.dumps(k) for k in imports)+'''};
static uintptr_t elf_find_sym_default(const char* name){
 if(missing&&!strcmp(missing,name))return 0;
 for(const auto& e:exports)if(!strcmp(e.name,name))return e.address;
 return 0;
}
'''+v.extract(text,'bool allowedImport(')+'\n'+function+'''
struct Volume {
 std::string filename;FILE* stream=nullptr;size_t limit=4096;unsigned opens=0,closes=0,reads=0;
 risc_storage_volume_api_v1 api{};
 explicit Volume(const char* input,size_t readLimit):filename(input),limit(readLimit){
  api.api_version=1;api.struct_size=sizeof(api);api.context=this;
  api.refresh=[](void*){return true;};api.ready=[](void*){return true;};
  api.file_open_read=[](void* c,const char* path,uint64_t* n)->uint32_t{
   assert(!strcmp(path,"Apps/lora_messages/lora_messages.elf")||!strcmp(path,"/Apps/lora_messages/lora_messages.elf"));
   auto& v=*static_cast<Volume*>(c);++v.opens;v.stream=fopen(v.filename.c_str(),"rb");
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
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);assert(file);
 std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(file),{});
 assert(esp_elf_validate_file(bytes.data(),bytes.size()));
 assert(admitElf(bytes.data(),bytes.size()));
 assert(!admitElf(bytes.data(),bytes.size(),ElfRole::Driver));
 safe=false;assert(!admitElf(bytes.data(),bytes.size()));safe=true;
 for(const char* name:imports){missing=name;assert(!admitElf(bytes.data(),bytes.size()));}missing=nullptr;
 assert(admitElf(bytes.data(),bytes.size()));
 for(size_t length:{size_t(0),size_t(51),bytes.size()-1})assert(!admitElf(bytes.data(),length));
 auto malformed=bytes;malformed[0]=0;assert(!admitElf(malformed.data(),malformed.size()));
 unsigned snapshots=0,reads=0;
 for(size_t limit:{size_t(4096),size_t(37)}){
  Volume volume(argv[1],limit);RiscBoot::RemovableAppImage image;
  assert(image.read(&volume.api,false,"/Apps/lora_messages/lora_messages.elf",{malloc,free,
   [](void*){return operationSafe();},[](void*,size_t){vTaskDelay(1);return operationSafe();},nullptr}));
  assert(!image.closeRetained&&image.size==bytes.size()&&!memcmp(image.bytes,bytes.data(),bytes.size()));
  assert(volume.opens==1&&volume.closes==1);assert(admitElf(image.bytes,image.size));
  free(image.bytes);++snapshots;reads+=volume.reads;
 }
 printf("{\\"production_structural_validation\\":true,\\"production_application_admission\\":true,\\"driver_role_rejected\\":true,\\"unsafe_rejected\\":true,\\"missing_import_rejections\\":%zu,\\"malformed_or_truncated_rejections\\":4,\\"production_removable_image_snapshots\\":%u,\\"volume_reads\\":%u,\\"target_instructions_executed\\":false}\\n",sizeof(imports)/sizeof(imports[0]),snapshots,reads);
}
'''
    (ROOT/'admission.cpp').write_text(source)
    includes=['-I'+str(RUNTIME/p) for p in ['src','sdk/app','sdk/driver','lib/elf_loader/include','test/native_bank_stubs']]
    tests=[]
    for sanitized in [False,True]:
        suffix='sanitized' if sanitized else 'normal'
        flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie'] if sanitized else []
        run(['cc','-std=c11',*flags,*includes,'-c',RUNTIME/'lib/elf_loader/src/esp_elf_validate.c','-o',ROOT/('validator-'+suffix+'.o')])
        run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*flags,*includes,ROOT/'admission.cpp',ROOT/('validator-'+suffix+'.o'),'-o',ROOT/('admission-'+suffix)])
        outcome=run([ROOT/('admission-'+suffix),elf],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
        (ROOT/(suffix+'.log')).write_text(outcome.stdout+outcome.stderr)
        tests.append(dict(json.loads(outcome.stdout),sanitized=sanitized))
    boot=json.loads((BASE/'baseline/store/boot.json').read_bytes())
    row=next(x for x in boot['app_capabilities'] if x['manifest']=='lora_messages.json')
    manifest=json.loads((BASE/'baseline/store/lora_messages.json').read_bytes())
    external=json.loads((elf.parent/'manifest.json').read_bytes())
    assert manifest['version']=='0.1.16' and external['version']=='0.1.17'
    assert {k:x for k,x in manifest.items() if k!='version'}=={k:x for k,x in external.items() if k!='version'}
    assert row['image_source']=={'path':'Apps/lora_messages/lora_messages.elf','volume_instance':12}
    grants={(x['capability'],x['api']) for x in row['grants']}
    assert all((x['capability'],x['api']) in grants for x in manifest['requires'])
    assert manifest['optional']==[{'api':2,'capability':'radio.lora'}]
    assert not any(x['capability']=='radio.lora' for x in row['grants'])
    store_root=BASE/'baseline/store'
    entries=[{'path':p.relative_to(store_root).as_posix(),'size_bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(store_root.rglob('*')) if p.is_file()]
    entries.sort(key=lambda x:x['path'])
    digest=sha(json.dumps(entries,sort_keys=True,separators=(',',':')).encode())
    assert digest==nativeq['admission']['candidate_store_sha256']
    assert nativeq['admission']['cohort_validated'] and nativeq['admission']['elf_count']==62
    assert nativeq['admission_sanitized']['cohort_validated'] and nativeq['admission_sanitized']['candidate_store_sha256']==digest
    sd_row=next(x for x in boot['drivers'] if x.get('instance_id')==12)
    sd_manifest=json.loads((store_root/sd_row['manifest']).read_bytes())
    assert sd_manifest['id']=='sdmmc-fatfs' and sd_manifest['provides']==[{'capability':'storage.volume','api':1}]
    result={'schema':1,'runtime_commit':git(RUNTIME,'rev-parse','HEAD'),
        'native_elf_sha256':sha(native),'native_bin_sha256':sha(nativebin),
        'native_evidence_archive_sha256':sha(archive.read_bytes()),
        'lora_elf_sha256':sha(data),'lora_elf_bytes':len(data),
        'public_export_count':len(exports),'compiled_public_exports':{x:hex(exports[x]) for x in imports},
        'native_store_abi':v.verify_native_store_abi(native,3),
        'tests':tests,'delivered_lora_policy':row,'required_capability_count':len(manifest['requires']),
        'all_required_capabilities_explicitly_granted':True,
        'optional_lora_ungranted':True,'internal_external_manifest_difference_only_version':True,
        'source_volume_provider':{'boot_row':sd_row,'id':sd_manifest['id'],'version':sd_manifest['version'],'provides':sd_manifest['provides']},
        'published_cohort_closure':{'store_digest':digest,'prepared':True,'cohort_validated':True,'elf_count':62,'normal_and_sanitized':True,'freshly_executed_in_this_checkpoint':False,'evidence_source':'baseline/qualification.json admission and admission_sanitized; all delivered store files digest-verified'},
        'target_symbol_resolver_executed':False,'target_instructions_executed':False,
        'hardware_tested':False,'app_level_external_media_end_to_end_tested':False,
        'source_files_sha256':{x:sha((RUNTIME/x).read_bytes()) for x in ['src/ports/esp32s3/NativeBankStore.cpp','src/runtime/packages/ElfAdmission.h','lib/elf_loader/src/esp_elf_validate.c','src/bootstrap/RemovableAppImage.h','src/bootstrap/RuntimeFileImage.h','src/runtime/storage/VolumeImageFiles.h']}}
    (ROOT/'qualification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
