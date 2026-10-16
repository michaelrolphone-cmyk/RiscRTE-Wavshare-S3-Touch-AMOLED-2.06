#include "runtime/drivers/NativeProviderPolicyValidationV1.h"
#include "runtime/packages/ElfAdmission.h"
#include <cassert>
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
static const Export exports[]={{"__divdf3",1073750608u},{"__errno",1108524052u},{"__fixunsdfsi",1073750776u},{"__floatunsidf",1073750884u},{"__getreent",1108635232u},{"__gtdf2",1073750944u},{"__ltdf2",1073751004u},{"_ctype_",1008266392u},{"calloc",1077433264u},{"clock_gettime",1107808128u},{"free",1077433252u},{"getopt_long",1108512840u},{"isalpha",1073746576u},{"longjmp",1108591636u},{"malloc",1077433216u},{"memchr",1073746756u},{"memcmp",1073746444u},{"memcpy",1073746420u},{"memmove",1073746432u},{"memset",1073746408u},{"optarg",1070266292u},{"opterr",1070222344u},{"optind",1070266288u},{"optopt",1070222340u},{"qsort",1073747080u},{"realloc",1077433232u},{"risc_runtime_get_api",1107381096u},{"setjmp",1073747020u},{"snprintf",1108516944u},{"strcasecmp",1073746780u},{"strcat",1073746804u},{"strchr",1073746828u},{"strcmp",1073746480u},{"strcpy",1073746456u},{"strcspn",1073746840u},{"strerror",1108519160u},{"strftime",1108522160u},{"strlen",1073746504u},{"strncasecmp",1073746900u},{"strncat",1073746912u},{"strncmp",1073746492u},{"strncpy",1073746468u},{"strnlen",1073746936u},{"strrchr",1073746948u},{"strstr",1073746516u},{"strtod",1108510680u},{"strtof",1108510712u},{"strtol",1073747176u},{"strtoul",1073747188u},{"tolower",1073746720u},{"vsnprintf",1108517472u}};
static const char* imports[]={"free","malloc","memchr","memcmp","memcpy","memset","risc_runtime_get_api","snprintf","strcmp","strcpy","strlen"};
static uintptr_t elf_find_sym_default(const char* name){
 if(missing&&!strcmp(missing,name))return 0;
 for(const auto& e:exports)if(!strcmp(e.name,name))return e.address;
 return 0;
}
bool allowedImport(const char*name){return RiscPackages::ordinaryImport(name);}
enum class ElfRole {Application,Driver,Either};
bool admitElf(const uint8_t*bytes,size_t n,ElfRole role=ElfRole::Application,
              const RuntimeProviders::NativeProviderPolicyV1*policy=nullptr){
 if(!operationSafe()||n>RISC_BANK_APP_MAX)return false;
 if(role!=ElfRole::Driver)policy=nullptr;
 if(policy&&!RuntimeProviders::nativeProviderImageValid(*policy,bytes,n))return false;
 return RiscPackages::admitElf(bytes,n,role,policy!=nullptr,{esp_elf_validate_file,
   [](const char*name){return allowedImport(name)&&elf_find_sym_default(name);},
   operationSafe,[](){vTaskDelay(1);},[]()->uint32_t{return RiscPlatform::millis();}});
}
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
 printf("{\"production_structural_validation\":true,\"production_application_admission\":true,\"driver_role_rejected\":true,\"unsafe_rejected\":true,\"missing_import_rejections\":%zu,\"malformed_or_truncated_rejections\":4,\"production_removable_image_snapshots\":%u,\"volume_reads\":%u,\"target_instructions_executed\":false}\n",sizeof(imports)/sizeof(imports[0]),snapshots,reads);
}
