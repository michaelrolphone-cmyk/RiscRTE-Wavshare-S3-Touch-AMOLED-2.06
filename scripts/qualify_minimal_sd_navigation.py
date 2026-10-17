#!/usr/bin/env python3
"""Exact minimal-SD Runtime navigation and serial-file host qualification.

Runs unchanged production Runtime against exact boot/board/manifests/ELF bytes.
The host deliberately substitutes instruction mapping, native device services,
and native atomic persistence. Actual Xtensa structural validation, Runtime
selection/grants/catalog/lifecycles, and serial Files protocol run as production
source. Target import/export admission belongs to the native build gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(files):
    return [{'path': p, 'size_bytes': len(b), 'sha256': sha(b)} for p, b in sorted(files.items())]


def directory(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob('*') if p.is_file()}


def materialize(files, root):
    root.mkdir()
    for name, data in files.items():
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == name, 'Unsafe input file path')
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def qualify(runtime: Path, internal_files: dict[str, bytes], external_files: dict[str, bytes], output: Path):
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    require(__debug__, 'Assertions must remain enabled')
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip()
    compile_roots = ['src', 'sdk', 'lib', 'test', 'waveshare-settings-profile.h']
    require(not subprocess.check_output(['git', '-C', str(runtime), 'diff', 'HEAD', '--', *compile_roots]), 'Runtime compile inputs modified')
    require(not subprocess.check_output(['git', '-C', str(runtime), 'ls-files', '--others', '--', *compile_roots]), 'Untracked Runtime compile inputs')
    boot = json.loads(internal_files['boot.json'])
    require(boot['default_app'] == 'default.elf' and len(boot['drivers']) == 38, 'Wrong minimal internal provider graph')
    apps, visible, images, mappings = {}, {}, {}, []
    internal_apps = set()
    for index, row in enumerate(boot['app_capabilities']):
        manifest = json.loads(internal_files[row['manifest']])
        filename = manifest['file_name']
        require(filename not in apps, 'Duplicate app executable identity')
        apps[filename] = dict(manifest, grants=row['grants'], index=index)
        if manifest.get('launcher_visible', True):
            visible[filename] = manifest['id']
        source = row.get('image_source')
        if source:
            require(source == {'volume_instance': 12, 'path': source['path']} and filename not in internal_files, 'External app has unexpected source/fallback/internal copy')
            data = external_files[source['path']]
            require(source['path'].endswith('/' + filename), 'External image basename differs')
            images[filename] = sha(data)
            sd_manifest = json.loads(external_files[str(Path(source['path']).parent / 'manifest.json')])
            # Existing LoRa has a newer SD version. Identity, requirements and
            # preferences remain identical across the internal and SD metadata.
            require({k: v for k, v in manifest.items() if k != 'version'} ==
                    {k: v for k, v in sd_manifest.items() if k != 'version'}, 'External app authority/identity metadata differs')
        else:
            require(filename in internal_files, 'Essential internal application absent')
            internal_apps.add(filename)
        mappings.append({'id': manifest['id'], 'file_name': filename, 'manifest': row['manifest'],
                         'requires': manifest['requires'], 'grants': row['grants'], 'image_source': source})
    require(internal_apps == {'default.elf', 'springboard.elf', 'wifi_settings.elf', 'settings.elf', 'clock.elf'}, 'Unexpected internal app set')
    require(len(apps) == 27 and len(images) == 22 and len(visible) == 24, 'Unexpected complete application inventory')
    require(len(internal_files['clock.elf']) == 1232 and json.loads(internal_files['clock.json'])['launcher_visible'] is False, 'Clock return shim not hidden/exact-sized')
    require(len(external_files) == 45 and len(internal_files) == 111, 'Unexpected package file inventory')
    result = {'schema': 1, 'runtime_commit': head, 'internal_inventory': inventory(internal_files),
              'external_inventory': inventory(external_files), 'app_mappings': mappings,
              'internal_apps': sorted(internal_apps), 'external_app_count': len(images),
              'visible_catalog_count': len(visible), 'provider_count': len(boot['drivers']),
              'newly_moved_internal_images_absent': 21, 'clock_hidden': True,
              'factory_erases_internal_settings': True, 'preflash_internal_data_survival_claimed': False,
              'leak_sanitizer_enabled': False, 'leak_sanitizer_reason': 'Host ptrace environment cannot run LSan; ASan and UBSan remain enabled',
              'target_instructions_executed': False, 'target_export_admission_tested': False,
              'hardware_tested': False, 'production_runtime_graph_unchanged': True,
              'modeled_boundaries': ['Xtensa instruction mapping and app entrypoints',
                  'device/provider implementation callbacks', 'native atomic persistence and legacy KV/app-data backing'],
              'coverage_limits': ['Does not execute production app UI or hidden shim instructions',
                  'Runtime app.catalog is exercised from declared Springboard authority; software.installed-apps provider UI enumeration is a separate gate',
                  'Preference checks prove production Runtime identity/grant/namespace routing with a host storage endpoint, not NVS/SD durability',
                  'Serial protocol uses production Files and PosixFiles with namespace 12; no physical SD/USB transport claim'],
              'tests': [], 'commands': []}
    with tempfile.TemporaryDirectory(prefix='navigation-', dir=output) as temporary:
        work = Path(temporary)
        materialize(internal_files, work / 'internal')
        materialize(external_files, work / 'external')
        (work / 'inputs.json').write_text(json.dumps({'apps': apps, 'visible': visible, 'external_images': images}))
        for name, content in [('navigation.cpp', NAVIGATION_CPP), ('install.cpp', INSTALL_CPP), ('esp_dlfcn.h', LOADER_HEADER)]:
            (work / name).write_text(content)
            (output / name).write_text(content)
        includes = ['-I' + str(p) for p in [work, runtime, runtime / 'src', runtime / 'sdk/app', runtime / 'sdk/driver', runtime / 'sdk/hardware', runtime / 'lib/ArduinoJson/src', runtime / 'test', runtime / 'test/drivers/stubs', runtime / 'test/support/native_registry/stubs', runtime / 'lib/elf_loader/include']]
        defines = ['RISC_REMOVABLE_APP_TEST=1', 'RISC_PAIRED_APP_DATA=1', 'RISC_PAIRED_APP_DATA_EXPANDED=1',
                   'RISC_RUNTIME_PREFERENCE_STORE=1', 'RISC_RUNTIME_ATOMIC_KEY_VALUE=1', 'RISC_RUNTIME_STORAGE_FILES=1',
                   'RISC_PLATFORM_CAPACITY=40', 'RISC_PROVIDER_CAPACITY=40', 'RISC_INSTALLED_APP_CAPACITY=64',
                   'RISC_APP_POLICY_ROWS=32', 'RISC_APP_REQUIREMENT_ROWS=32', 'RISC_RUNTIME_ATOMIC_BINDING_CAPACITY=34']
        runtime_sources = ['src/bootstrap/Json.cpp', 'src/bootstrap/Board.cpp', 'src/bootstrap/Runtime.cpp',
                           'src/runtime/streams/AppStreamSessions.cpp', 'src/runtime/streams/ProviderQueueHost.cpp',
                           'src/runtime/drivers/ProviderGraphV2.cpp', 'src/runtime/drivers/ProviderModuleV2.cpp']
        dependencies = {runtime / p for p in runtime_sources + ['lib/elf_loader/src/esp_elf_validate.c', 'src/runtime/serial/Files.cpp']}
        def run(command, log, timeout=180):
            command = [str(x) for x in command]
            result['commands'].append(command)
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout, env=env)
            with (output / log).open('a') as sink:
                sink.write('$ ' + shlex.join(command) + '\n' + proc.stdout)
            require(proc.returncode == 0, f'Qualification failed ({proc.returncode}); see {output / log}: {proc.stdout[-1500:]}')
            return proc.stdout
        for sanitized in (False, True):
            label = 'sanitized' if sanitized else 'normal'
            build = work / label
            build.mkdir()
            sanitizers = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie'] if sanitized else []
            flags = ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-missing-field-initializers', '-Wno-misleading-indentation', *sanitizers, *['-D' + d for d in defines], *includes]
            objects = []
            for index, source in enumerate([runtime / p for p in runtime_sources] + [work / 'navigation.cpp']):
                obj = build / f'{index}.o'
                run([os.environ.get('CXX', 'c++'), *flags, '-MMD', '-MF', build / f'{index}.d', '-c', source, '-o', obj], 'compile-' + label + '.log')
                objects.append(obj)
            validator = build / 'validator.o'
            run([os.environ.get('CC', 'cc'), '-std=c11', *sanitizers, '-I' + str(runtime / 'lib/elf_loader/include'), '-I' + str(runtime / 'test/native_bank_stubs'), '-MMD', '-MF', build / 'validator.d', '-c', runtime / 'lib/elf_loader/src/esp_elf_validate.c', '-o', validator], 'compile-' + label + '.log')
            binary = build / 'navigation'
            run([os.environ.get('CXX', 'c++'), *sanitizers, *objects, validator, '-lcrypto', '-ldl', '-o', binary], 'compile-' + label + '.log')
            for mode in ['normal', 'no-card', 'missing', 'malformed', 'removed', 'relocation']:
                raw = run([binary, work / 'internal', work / 'external', work / 'inputs.json', mode], label + '.log', 90)
                result['tests'].append(dict(json.loads(raw), sanitized=sanitized))
            installer = build / 'install'
            run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-missing-field-initializers', *sanitizers, *includes, '-MMD', '-MF', build / 'install.d', runtime / 'src/runtime/serial/Files.cpp', work / 'install.cpp', '-lcrypto', '-o', installer], 'compile-' + label + '.log')
            for scenario in ['clean', 'known-lora']:
                raw = run([installer, work / 'external', work / ('installed-' + label + '-' + scenario), scenario], 'install-' + label + '.log', 120)
                result['tests'].append(dict(json.loads(raw), sanitized=sanitized))
            for dep in build.glob('*.d'):
                body = dep.read_text().replace('\\\n', ' ').split(':', 1)[1]
                dependencies.update(Path(p).resolve() for p in shlex.split(body) if Path(p).resolve().is_relative_to(runtime))
        result['source_files'] = {str(p.relative_to(runtime)): sha(p.read_bytes()) for p in sorted(dependencies)}
        result['fixture_files'] = {name: sha((output / name).read_bytes()) for name in ['navigation.cpp', 'install.cpp', 'esp_dlfcn.h']}
        result['production_structural_validation'] = True
        result['production_serial_per_file_installation'] = True
        result['passed'] = True
    (output / 'qualification.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['runtime', 'internal', 'external', 'output']:
        p.add_argument('--' + name, required=True, type=Path)
    a = p.parse_args()
    result = qualify(a.runtime, directory(a.internal), directory(a.external), a.output)
    print(json.dumps({'passed': result['passed'], 'runtime_commit': result['runtime_commit'],
                      'test_count': len(result['tests']), 'receipt': str(a.output / 'qualification.json')}, indent=2))


NAVIGATION_CPP = r'''// Host instruction boundary only; Runtime and its boot metadata remain unchanged.
#include "bootstrap/Runtime.h"
#include "RuntimeFileFixture.h"
#include "waveshare-settings-profile.h"
#include <RiscProviderV2.h>
#include <RiscInternalPackageVolumeV1.h>
#include <RiscProvisionRequestV1.h>
#include <RiscUsbPhyResourceV1.h>
#include <esp_dlfcn.h>
#include <private/esp_dlcache.h>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <openssl/evp.h>
using R=RiscBoot::Runtime;namespace fs=std::filesystem;
static std::string root,sd,mode,selected;static JsonDocument boot,inputs;
static unsigned homes,children,failures,opens,closes,snapshots,kvChecks,dataChecks,catalogChecks,shim,priorReads;
static size_t nextApp;static std::vector<std::string> sequence;static bool present=true;
static const risc_runtime_api_v1* currentApi;static risc_app_catalog_v1 staleCatalog{};
static std::map<std::pair<unsigned,std::string>,std::string> values,dataValues;
static unsigned expectedNamespace;static bool checkingBackend;
static bool owner(){return true;}static bool health(risc_runtime_health_v1*){return true;}
static void delay(uint32_t){}static bool logger(const char*){return true;}
static std::string read(const std::string&p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static JsonDocument jsonFile(const std::string&p){JsonDocument d;assert(!deserializeJson(d,read(p)));return d;}
static std::string digest(const uint8_t*p,size_t n){uint8_t out[32];unsigned size=0;assert(EVP_Digest(p,n,out,&size,EVP_sha256(),nullptr)&&size==32);char hex[65]{};for(unsigned i=0;i<32;++i)snprintf(hex+2*i,3,"%02x",out[i]);return hex;}
static int32_t getValue(unsigned ns,const char*k,void*out,uint32_t cap,uint32_t*n){if(checkingBackend)assert(ns==expectedNamespace);*n=0;auto i=values.find({ns,k});if(i==values.end())return RISC_KEY_VALUE_NOT_FOUND;*n=i->second.size();if(cap<*n)return RISC_KEY_VALUE_BUFFER_SMALL;memcpy(out,i->second.data(),*n);return 0;}
static RiscBoot::KeyValueBackend kv{nullptr,[](void*,uint32_t ns,const char*k,void*out,uint32_t cap,uint32_t*n){return getValue(ns,k,out,cap,n);},[](void*,uint32_t ns,const char*k,const void*p,uint32_t n)->int32_t{if(checkingBackend)assert(ns==expectedNamespace);values[{ns,k}].assign((const char*)p,n);return 0;},2048};
static RiscBoot::AppDataBackend data{nullptr,
 [](void*,uint32_t ns,const char*k,uint32_t*n,uint64_t*v)->int32_t{if(checkingBackend)assert(ns==expectedNamespace);auto i=dataValues.find({ns,k});if(i==dataValues.end())return RISC_APP_DATA_NOT_FOUND;*n=i->second.size();*v=1;return 0;},
 [](void*,uint32_t ns,const char*k,uint64_t,void*out,uint32_t cap,uint32_t*n,uint64_t*v)->int32_t{if(checkingBackend)assert(ns==expectedNamespace);auto i=dataValues.find({ns,k});if(i==dataValues.end())return RISC_APP_DATA_NOT_FOUND;*n=i->second.size();*v=1;if(cap<*n)return RISC_APP_DATA_BUFFER_SMALL;memcpy(out,i->second.data(),*n);return 0;},
 [](void*,uint32_t ns,const char*k,uint64_t,const void*p,uint32_t n)->int32_t{if(checkingBackend)assert(ns==expectedNamespace);dataValues[{ns,k}].assign((const char*)p,n);return 0;},[](void*){return true;}};
struct Atomic {unsigned ns;uint64_t revision=1,token=0;};static Atomic a1{1},a6{6};
static const RiscBoot::AtomicSettingsEndpoint::Operations atomicOps{
 [](void*p){return ((Atomic*)p)->ns;},[](void*){return true;},[](void*){return false;},
 [](void*p,risc_key_value_atomic_state_v1*s)->int32_t{auto&a=*(Atomic*)p;*s={sizeof(*s),3,a.ns,16,2048,8192,2048,0,a.revision};return 0;},
 [](void*p,uint64_t rev,const char*k,void*out,uint32_t cap,uint32_t*n)->int32_t{auto&a=*(Atomic*)p;if(rev!=a.revision)return RISC_ATOMIC_STALE;const int r=getValue(a.ns,k,out,cap,n);return r==0?0:r==RISC_KEY_VALUE_NOT_FOUND?RISC_ATOMIC_NOT_FOUND:RISC_ATOMIC_BUFFER_SMALL;},
 [](void*p,uint64_t rev,const risc_key_value_atomic_mutation_v1*m,uint32_t n,const void*,uint32_t,uint64_t*t)->int32_t{auto&a=*(Atomic*)p;if(checkingBackend)assert(a.ns==expectedNamespace);if(rev!=a.revision)return RISC_ATOMIC_STALE;assert(n==1&&m->kind==RISC_ATOMIC_PUT);values[{a.ns,m->key}].assign((const char*)m->value,m->size);*t=++a.revision;a.token=*t;return 0;},
 [](void*p,uint64_t token,risc_key_value_atomic_receipt_v1*r)->int32_t{auto&a=*(Atomic*)p;assert(token==a.token);*r={sizeof(*r),0,a.revision,token};a.token=0;return 0;},[](void*,uint64_t)->int32_t{return RISC_ATOMIC_INVALID;}};
static RiscBoot::EntropyBackend entropy{nullptr,[](void*,uint64_t,void*,uint32_t)->int32_t{assert(false);return -1;},[](void*,uint64_t){return true;},[](void*){return true;}};
static RiscBoot::TcpListenerBackend tcp{nullptr,[](void*,uint64_t,const risc_tcp_listen_v1*,uint64_t*)->int32_t{assert(false);return -1;},[](void*,uint64_t,uint64_t,uint64_t*)->int32_t{assert(false);return -1;},[](void*,uint64_t,uint64_t,void*,uint32_t,uint32_t*)->int32_t{assert(false);return -1;},[](void*,uint64_t,uint64_t,const void*,uint32_t,uint32_t*)->int32_t{assert(false);return -1;},[](void*,uint64_t,uint64_t)->int32_t{assert(false);return -1;},[](void*,uint64_t){return true;},[](void*){return true;}};
static risc_realtime_control_api_v1 realtime{1,sizeof(realtime),nullptr,[](void*,risc_realtime_snapshot_v1*)->int32_t{assert(false);return -1;},[](void*,int64_t,uint32_t)->int32_t{assert(false);return -1;}};
static risc_usb_phy_resource_api_v1 usb{1,sizeof(usb),nullptr,1,0,[](void*){assert(false);return false;},[](void*,uint64_t*){assert(false);return false;},[](void*,uint64_t){assert(false);return false;}};
static risc_provision_request_api_v1 provision{1,sizeof(provision),nullptr,[](void*,risc_provision_request_status_v1*)->int32_t{assert(false);return -1;},[](void*,const risc_provision_request_v1*,uint8_t*)->int32_t{assert(false);return -1;}};
static risc_storage_volume_api_v1_download download{};static risc_internal_package_volume_v1 packages{1,sizeof(packages),nullptr,nullptr,[](void*){return true;}};
static void initPackage(){auto&v=*reinterpret_cast<risc_storage_volume_api_v1*>(&download);v.api_version=1;v.struct_size=sizeof(download);download.base.base.fs.state.state_tag=RISC_STORAGE_STATE_TAG;download.base.base.fs.state.state_version=1;download.base.base.fs.fs_tag=RISC_STORAGE_FS_TAG;download.base.base.fs.fs_version=1;
 download.base.base.fs.state.observe=[](void*)->int32_t{return 1;};
 download.base.base.fs.dir_tell=[](void*,uint32_t,uint64_t*){return false;};download.base.base.fs.dir_seek=[](void*,uint32_t,uint64_t){return false;};download.base.base.fs.metadata=[](void*,const char*,risc_storage_metadata_v1*)->int32_t{return -1;};download.base.base.fs.file_truncate=[](void*,uint32_t,uint64_t){return false;};download.base.base.fs.replace_file=[](void*,const char*,const char*){return false;};download.base.base.fs.recover_replace=[](void*,const char*){return false;};
 download.base.base.async_tag=RISC_STORAGE_ASYNC_TAG;download.base.base.async_version=RISC_STORAGE_ASYNC_VERSION;
 download.base.base.begin=[](void*,uint64_t*)->int32_t{return -1;};download.base.base.submit=[](void*,uint64_t,const risc_storage_async_request_v1*,uint64_t*)->int32_t{return -1;};download.base.base.collect=[](void*,uint64_t,uint64_t,risc_storage_async_result_v1*)->int32_t{return -1;};download.base.base.end=[](void*,uint64_t)->int32_t{return -1;};
 download.base.package_tag=RISC_STORAGE_PACKAGE_TAG;download.base.package_version=1;download.base.submit_package=[](void*,uint64_t,const risc_storage_package_request_v1*,uint64_t*)->int32_t{return -1;};download.download_tag=RISC_STORAGE_DOWNLOAD_TAG;download.download_version=2;packages.volume=&v;}
static bool bind(R&r){initPackage();assert(r.registerEntropy(&entropy));assert(r.registerTcpListener(&tcp));assert(r.registerRealtime(&realtime));
 static uint32_t generic[]={1,8};std::set<std::pair<std::string,unsigned>> platforms;
 for(JsonObjectConst row:boot["drivers"].as<JsonArrayConst>()){auto m=jsonFile(root+"/"+row["manifest"].as<const char*>());for(JsonObjectConst req:m["requires"].as<JsonArrayConst>()){
 std::string cap=req["capability"].as<const char*>();unsigned id=row["instance_id"]|0u;
 if(cap=="platform.clock"||cap=="platform.bank-store"||cap=="platform.http-client"||cap=="platform.radio.iq.resource"||cap=="platform.package-volume"||cap=="platform.provision-request"||cap=="platform.usb.phy.resource")id=0;
 if(cap.rfind("platform.",0)!=0||cap=="platform.entropy"||cap=="platform.tcp-listener"||cap=="platform.installation")continue;
 if(!platforms.insert({cap,id}).second)continue;const void*table=generic;
 if(cap=="platform.package-volume")table=&packages;else if(cap=="platform.provision-request")table=&provision;else if(cap=="platform.usb.phy.resource")table=&usb;
 if(!r.registerPlatform(cap.c_str(),req["api"],id?R::Scope::Device:R::Scope::Global,id,table)){fprintf(stderr,"platform %s %u failed\n",cap.c_str(),id);return false;}
 }}
 struct Writer{const char*id;unsigned ns;};static const Writer writers[]={RISC_NATIVE_SETTINGS_WRITERS};
 for(const auto&w:writers)assert(r.registerAtomicKeyValue(w.id,w.ns,{w.ns==6?&a6:&a1,&atomicOps}));
 for(unsigned ns:{1u,6u}){assert(r.registerAtomicKeyValueReadThrough(ns,{ns==6?&a6:&a1,&atomicOps}));assert(r.registerKeyValueAvailability(ns,{nullptr,[](void*,uint32_t n,risc_key_value_availability_state_v1*s)->int32_t{*s={sizeof(*s),n,RISC_KEY_VALUE_AVAILABLE,0,1};return 0;}}));}return true;}
static FILE* imageFile;static size_t imageOffset;static std::string imagePath;
static risc_storage_volume_api_v1 volume{};
static void initVolume(){volume.api_version=1;volume.struct_size=sizeof(volume);volume.refresh=[](void*){return true;};volume.ready=[](void*){return present;};
 volume.file_open_read=[](void*,const char*p,uint64_t*n)->uint32_t{assert(!imageFile);if(mode=="missing")return 0;imagePath=p;imageFile=fopen((sd+p).c_str(),"rb");if(!imageFile)return 0;++opens;imageOffset=0;assert(!fseek(imageFile,0,SEEK_END));*n=ftell(imageFile);rewind(imageFile);return 1;};
 volume.file_read=[](void*,uint32_t h,void*out,size_t n)->size_t{assert(h==1&&imageFile&&n<=4096);if(mode=="removed"&&imageOffset>=4096)return 0;n=std::min(n,size_t(337));const size_t got=fread(out,1,n,imageFile);if(mode=="malformed"&&!imageOffset&&got)((uint8_t*)out)[0]=0;imageOffset+=got;return got;};
 volume.file_close=[](void*,uint32_t h,bool commit){assert(h==1&&imageFile&&!commit);++closes;const bool ok=fclose(imageFile)==0;imageFile=nullptr;return ok;};}
struct Module {std::string name,id,cap;unsigned api=0;risc_driver_v2 descriptor{};};static std::map<void*,Module*> modules;static Module* forSymbol;static Module* appModule;
static bool start(const risc_provider_dependency_v1*,size_t){return true;}static void stop(){}static bool quiet(){return true;}
static const risc_driver_v2* driverGet(uint32_t abi){assert(abi==2&&forSymbol);return &forSymbol->descriptor;}
static void application();
extern "C" void* fixture_dlopen(const char*path,int){auto*m=new Module;m->name=fs::path(path).filename();const std::string parent=fs::path(path).parent_path();if(parent!=root){auto manifest=jsonFile(parent+"/manifest.json");m->id=manifest["id"].as<const char*>();m->cap=manifest["provides"][0]["capability"].as<const char*>();m->api=manifest["provides"][0]["api"];static uint32_t generic[]={1,8};m->descriptor={2,sizeof(risc_driver_v2),m->id.c_str(),m->cap.c_str(),m->api,m->cap=="storage.volume"?(void*)&volume:(void*)generic,start,stop,quiet};}modules[m]=m;return m;}
extern "C" void* fixture_dlsym(void*handle,const char*name){auto*m=modules.at(handle);forSymbol=m;if(!strcmp(name,"t5_driver_get"))return (void*)driverGet;if(!strcmp(name,"app_main")){appModule=m;return (void*)application;}return nullptr;}
extern "C" int fixture_dlclose(void*handle){auto*m=modules.at(handle);modules.erase(handle);delete m;return 0;}
extern "C" char* fixture_dlerror(){return nullptr;}
extern "C" void* esp_elf_malloc(uint32_t n,bool){return malloc(n);}extern "C" void esp_elf_free(void*p){free(p);}
extern "C" bool esp_elf_admit_managed_app(const char*,const uint8_t*,size_t){return true;}
extern "C" void* esp_dlopen_reader_instance(const char*path,esp_dl_image_reader reader,void*context){elf_file_t f{};if(reader(context,path,&f))return nullptr;assert(!imageFile);const std::string filename=fs::path(path).filename();const bool external=inputs["external_images"][filename].is<const char*>();if(external){assert(digest(f.payload,f.size)==inputs["external_images"][filename].as<std::string>());++snapshots;}free(f.payload);if(external&&mode=="relocation")return nullptr;return fixture_dlopen(path,0);}
static void checkCatalog(){risc_runtime_capability_v1 g{sizeof(g)};assert(currentApi->acquire("app.catalog",1,0,&g));const auto*a=(const risc_app_catalog_v1*)g.api;risc_app_catalog_snapshot_v1 s{sizeof(s)};assert(!a->snapshot(a->context,&s));assert(s.count==inputs["visible"].size());std::set<std::string> seen;const auto oldOpens=opens;
 for(unsigned i=0;i<s.count;++i){risc_app_catalog_entry_v1 e{sizeof(e)};assert(!a->get(a->context,s.generation,i,&e));assert(inputs["visible"][e.file_name].as<std::string>()==e.id);assert(e.flags==RISC_APP_CATALOG_AVAILABLE);assert(seen.insert(e.file_name).second);assert(strcmp(e.file_name,"clock.elf"));}assert(opens==oldOpens);staleCatalog=*a;assert(currentApi->release(&g));++catalogChecks;}
static void checkData(const std::string&filename){JsonObjectConst row=inputs["apps"][filename];unsigned index=0;for(JsonObjectConst g:row["grants"].as<JsonArrayConst>()){const std::string cap=g["capability"].as<const char*>();if(cap!="storage.key-value"&&cap!="storage.key-value.atomic"&&cap!="storage.preferences"&&cap!="storage.app-data")continue;bool declared=false;for(JsonObjectConst req:row["requires"].as<JsonArrayConst>())if(req["capability"].as<std::string>()==cap&&req["api"]==g["api"])declared=true;if(!declared)continue;
 const unsigned ns=g["instance_id"],api=g["api"];risc_runtime_capability_v1 grant{sizeof(grant)};if(!currentApi->acquire(cap.c_str(),api,ns,&grant)){fprintf(stderr,"acquire %s %s %u %u failed\n",filename.c_str(),cap.c_str(),api,ns);abort();}expectedNamespace=ns;checkingBackend=true;const std::string key="q"+std::to_string(inputs["apps"][filename]["index"].as<unsigned>())+"x"+std::to_string(index++);const std::string value=filename+"-saved";char out[128];uint32_t n=0;
 if(cap=="storage.key-value"){const auto*a=(const risc_key_value_v1*)grant.api;if(values.count({ns,key})){assert(!a->get(a->context,key.c_str(),out,sizeof(out),&n));assert(std::string(out,n)==value);++priorReads;}if(ns!=1&&ns!=6)assert(!a->put(a->context,key.c_str(),value.data(),value.size()));else values[{ns,key}]=value;assert(!a->get(a->context,key.c_str(),out,sizeof(out),&n));assert(std::string(out,n)==value);++kvChecks;}
 else if(cap=="storage.key-value.atomic"||cap=="storage.preferences"){const auto*a=(const risc_key_value_atomic_v1*)grant.api;risc_key_value_atomic_state_v1 s{sizeof(s)};assert(!a->state(a->context,&s)&&s.namespace_id==ns);if(values.count({ns,key})){assert(!a->get(a->context,s.revision,key.c_str(),out,sizeof(out),&n));assert(std::string(out,n)==value);++priorReads;}risc_key_value_atomic_mutation_v1 m{key.c_str(),RISC_ATOMIC_PUT,value.data(),(uint32_t)value.size()};uint64_t t=0;assert(!a->submit(a->context,s.revision,&m,1,"test",4,&t)&&t);risc_key_value_atomic_receipt_v1 receipt{sizeof(receipt)};assert(!a->collect(a->context,t,&receipt)&&!receipt.status);assert(!a->get(a->context,receipt.revision,key.c_str(),out,sizeof(out),&n));assert(std::string(out,n)==value);++kvChecks;}
 else{const auto*a=(const risc_app_data_v1*)grant.api;assert(!a->replace(a->context,"qualified",0,value.data(),value.size()));uint64_t v=0;assert(!a->read(a->context,"qualified",0,out,sizeof(out),&n,&v));assert(std::string(out,n)==value);++dataChecks;}
 checkingBackend=false;assert(currentApi->release(&grant));}
 risc_runtime_capability_v1 denied{sizeof(denied)};assert(!currentApi->acquire("storage.app-data",1,999999,&denied));assert(!currentApi->acquire("storage.key-value",1,999999,&denied));}
static void application(){assert(appModule);const std::string name=appModule->name;currentApi=risc_runtime_get_api(1);assert(currentApi);if(staleCatalog.context){risc_app_catalog_snapshot_v1 s{sizeof(s)};assert(staleCatalog.snapshot(staleCatalog.context,&s)==RISC_APP_CATALOG_CONTEXT);}
 if(name=="default.elf"){++homes;checkData(name);risc_runtime_launch_failure_v1 failure{sizeof(failure)};const bool failed=currentApi->take_launch_failure(&failure);if(failed){++failures;assert(failure.flags&RISC_LAUNCH_FAILURE_EXTERNAL_IMAGE);assert(failure.application==selected);}
 if(nextApp){const bool fault=mode!="normal"&&inputs["external_images"][selected].is<const char*>();assert(failed==fault);}
 if(nextApp<sequence.size()){selected=sequence[nextApp++];if(!currentApi->request_launch(selected.c_str())){fprintf(stderr,"Launch refused: %s\n",selected.c_str());abort();}}return;}
 ++children;assert(name==selected);if(name=="springboard.elf")checkCatalog();checkData(name);if(name=="clock.elf"){++shim;assert(currentApi->request_default());}else if(children%2)assert(currentApi->request_default());}
int main(int argc,char**argv){assert(argc==5);root=argv[1];sd=argv[2];inputs=jsonFile(argv[3]);mode=argv[4];boot=jsonFile(root+"/boot.json");present=mode!="no-card";initVolume();for(JsonObjectConst row:boot["app_capabilities"].as<JsonArrayConst>()){auto m=jsonFile(root+"/"+row["manifest"].as<const char*>());std::string file=m["file_name"].as<const char*>();if(file!="default.elf")sequence.push_back(file);}const auto again=sequence;sequence.insert(sequence.end(),again.begin(),again.end());
 RiscBoot::Port port{owner,health,delay,logger,bind,&kv};port.appData=&data;port.memoryHeap=[](risc_memory_heap_snapshot_v1*)->int32_t{return -1;};port.randomBytes=[](void*,uint32_t)->int32_t{return -1;};port.coldBoot=[](){return false;};
 RiscRetainedWake::Image image{};RiscRetainedWake::Store wake(image);port.retainedWake=&wake;static RiscBoot::FileSourceBackend source{nullptr,[](void*,uint64_t)->int32_t{return -1;},[](void*,const void*,uint32_t,uint32_t*)->int32_t{return -1;},[](void*)->int32_t{return -1;},[](void*,uint64_t,void*,uint32_t,uint32_t*)->int32_t{return -1;},[](void*)->int32_t{return -1;},[](void*){return true;}};port.fileSource=&source;
 RiscTest::FileSources files({root});R runtime(port);assert(files.bind(runtime));if(!runtime.prepare(root.c_str())){fprintf(stderr,"prepare: %s\n",runtime.error());return 1;}assert(runtime.appInventoryCount()==inputs["apps"].size());if(!runtime.run()){fprintf(stderr,"run: %s\n",runtime.error());return 1;}assert(homes==sequence.size()+1&&opens==closes&&!imageFile&&!runtime.retained()&&modules.empty());assert(priorReads>100);const unsigned ext=inputs["external_images"].size()*2;assert(failures==(mode=="normal"?0:ext));assert(children==sequence.size()-failures&&shim==2);
 printf("{\"mode\":\"%s\",\"home_invocations\":%u,\"child_invocations\":%u,\"external_failures_recovered\":%u,\"snapshot_mappings\":%u,\"catalog_checks\":%u,\"preference_checks\":%u,\"app_data_checks\":%u,\"prior_invocation_preference_reads\":%u,\"hidden_shim_returns\":%u,\"opens\":%u,\"closes\":%u}\n",mode.c_str(),homes,children,failures,snapshots,catalogChecks,kvChecks,dataChecks,priorReads,shim,opens,closes);}
'''

INSTALL_CPP = r'''#include "runtime/serial/Files.h"
#include "runtime/storage/PosixFiles.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdio>
#include <openssl/evp.h>
namespace fs=std::filesystem;
static std::string read(const fs::path&p){std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
static void save(const fs::path&p,const std::string&v){fs::create_directories(p.parent_path());std::ofstream f(p,std::ios::binary);f<<v;assert(f.good());}
static std::string sha(const std::string&v){unsigned char b[32];unsigned n=0;assert(EVP_Digest(v.data(),v.size(),b,&n,EVP_sha256(),nullptr)&&n==32);char out[65]{};for(unsigned i=0;i<32;++i)snprintf(out+2*i,3,"%02x",b[i]);return out;}
static uint32_t crc32(const std::string&s){uint32_t c=~0u;for(unsigned char b:s){c^=b;for(unsigned i=0;i<8;++i)c=(c>>1)^((c&1)?0xedb88320u:0);}return ~c;}
static std::string hex(const std::string&s){std::string r;for(unsigned char b:s){r+="0123456789abcdef"[b>>4];r+="0123456789abcdef"[b&15];}return r;}
struct Wire{RiscSerial::Files&f;unsigned seq=0,commands=0;
 std::string command(const std::string&cmd,int expected=0){const auto line="RTEF1 12345678 "+std::to_string(++seq)+" "+cmd+"\n";for(unsigned char c:line)f.input(c);f.checkpoint();std::string out;while(f.outputSize()){const size_t n=std::min(size_t(7),f.outputSize());out.append(f.output(),n);f.consumeOutput(n);}const auto prefix="RTEF1 12345678 "+std::to_string(seq)+" "+std::to_string(expected);if(out.rfind(prefix,0)!=0){fprintf(stderr,"%s -> %s",cmd.c_str(),out.c_str());abort();}assert(out[prefix.size()]==' '||out[prefix.size()]=='\n');++commands;return out;}
 void path(const std::string&p){for(size_t o=0;o<p.size();o+=48)command("PATH "+std::to_string(o)+" "+hex(p.substr(o,48)));}
 void put(const std::string&p,const std::string&v,bool replace){path(p);command("PUT 12 "+std::string(replace?"replace":"create")+" "+std::to_string(v.size()));size_t off=0;while(off<v.size()){auto response=command("WRITE "+std::to_string(off)+" "+hex(v.substr(off,48)));const auto at=response.find(" WRITE ");assert(at!=std::string::npos);auto next=std::stoull(response.substr(at+7));assert(next>off&&next<=off+48);off=next;}char crc[9];snprintf(crc,sizeof(crc),"%08x",crc32(v));command("COMMIT "+std::string(crc));}
 void verify(const std::string&p,const std::string&v){path(p);auto response=command("GET 12");assert(response.find(" GET "+std::to_string(v.size())+"\n")!=std::string::npos);size_t off=0;while(off<v.size()){response=command("READ "+std::to_string(off));const auto at=response.find(" READ ");assert(at!=std::string::npos);const size_t next=std::stoull(response.substr(at+6));assert(next>=off);const size_t n=next-off;assert(n&&n<=48&&off+n<=v.size());assert(response.find(" "+hex(v.substr(off,n))+"\n")!=std::string::npos);off+=n;}char crc[9];snprintf(crc,sizeof(crc),"%08x",crc32(v));assert(command("CLOSE").find(crc)!=std::string::npos);}
};
int main(int argc,char**argv){assert(argc==4);const std::string scenario=argv[3];assert(scenario=="clean"||scenario=="known-lora");const bool mixed=scenario=="known-lora";unsigned created=0,replaced=0,priorHashes=0;const fs::path source=argv[1],target=argv[2];fs::create_directories(target);std::vector<fs::path> files;for(const auto&e:fs::recursive_directory_iterator(source))if(e.is_regular_file())files.push_back(e.path().lexically_relative(source));std::sort(files.begin(),files.end());
 const std::vector<std::pair<std::string,std::string>> untouched={{"photos/keep.jpg","unrelated-user-photo"},{"Apps/custom/manifest.json","custom-app-manifest"},{"Apps/custom/custom.elf","unrelated-app"},{"Apps/alarms/app-data.bin","existing-SD-app-data"},{".riscrte/settings/ns1/checkpoint","existing-settings-checkpoint"}};for(const auto&e:untouched)save(target/e.first,e.second);
 const std::vector<std::pair<std::string,std::string>> prior={{"Apps/lora_messages/lora_messages.elf","81877ba548ae0c45f4ebbbe71c53753159a4b3a28282ac9ce3c5ef63ad90c0f5"},{"Apps/lora_messages/manifest.json","6a07f83bb276c6f662000ffec7fd68c19ed00d4de1889a14e012b5fa09466743"},{"suite-card.json","3e9c22cfd15605efa78640b86d6a1119be06fd65834b64d84c6b0020f0826cf3"}};if(mixed)for(const auto&e:prior){const auto bytes=read(source/e.first);assert(sha(bytes)==e.second);save(target/e.first,bytes);}
 const auto root=target.string();RiscStorage::PosixFiles provider(root.c_str());RiscBoot::RuntimeFiles runtimeFiles;assert(runtimeFiles.bind(provider.api(),[](){return true;},[](){return true;}));RiscSerial::Namespace ns{12,"SD card",&runtimeFiles,true};RiscSerial::Files endpoint;assert(endpoint.bind(&ns,1,{[](){return true;},[](){return true;},[]()->uint32_t{return 1;}}));Wire wire{endpoint};wire.command("HELLO");wire.command("NS 0");uint64_t bytes=0;
 for(unsigned pass=0;pass<2;++pass){for(const auto&relative:files){fs::path parent;for(const auto&part:relative.parent_path()){parent/=part;if(!fs::exists(target/parent)){wire.path("/"+parent.generic_string());wire.command("MKDIR 12");}}
 auto content=read(source/relative);bool replace=pass==1;if(mixed&&!pass)for(const auto&e:prior)if(relative.generic_string()==e.first){assert(sha(read(target/relative))==e.second);wire.verify("/"+relative.generic_string(),read(target/relative));++priorHashes;replace=true;}wire.put("/"+relative.generic_string(),content,replace);if(replace)++replaced;else ++created;wire.verify("/"+relative.generic_string(),content);assert(read(target/relative)==content);bytes+=content.size();}
 for(const auto&e:untouched)assert(read(target/e.first)==e.second);}
 assert(endpoint.shutdown()&&endpoint.exitSafe()&&provider.exitSafe());assert(priorHashes==(mixed?3u:0u));assert(created==files.size()-priorHashes&&replaced==files.size()+priorHashes);
 printf("{\"production_serial_protocol\":true,\"namespace\":12,\"scenario\":\"%s\",\"create_files\":%u,\"replace_files\":%u,\"verified_prior_hashes\":%u,\"verified_file_bytes\":%llu,\"preserved_sentinels\":%zu,\"commands\":%u,\"hardware_tested\":false}\n",scenario.c_str(),created,replaced,priorHashes,(unsigned long long)bytes,untouched.size(),wire.commands);}
'''

LOADER_HEADER = r'''#pragma once
#include <dlfcn.h>
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void* fixture_dlopen(const char*,int);void* fixture_dlsym(void*,const char*);int fixture_dlclose(void*);char* fixture_dlerror(void);
#define dlopen fixture_dlopen
#define dlsym fixture_dlsym
#define dlclose fixture_dlclose
#define dlerror fixture_dlerror
static inline void* esp_dlopen_instance(const char*p){return fixture_dlopen(p,RTLD_NOW);}
#ifdef __cplusplus
}
#endif
'''

if __name__ == "__main__":
    main()
