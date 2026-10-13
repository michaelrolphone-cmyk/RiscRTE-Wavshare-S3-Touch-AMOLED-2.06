#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#define UPDATE_FIRMWARE 1
#include UPDATE_SERVICE_SOURCE
static unsigned calls;
static const char *installedProduct=WatchUpdate::Product;
static int32_t cohortInfo(void*,risc_bank_cohort_status_v1 *out){++calls;strcpy(out->product,installedProduct);strcpy(out->version,"0.1.12");strcpy(out->source_repo,WatchUpdate::Repository);memset(out->source_revision,'a',40);out->source_revision[40]=0;return 0;}
static int32_t denyBegin(void*,const risc_bank_cohort_v1*,uint64_t*){assert(false);return RISC_BANK_INVALID;}
static std::string read(const char *p){std::ifstream f(p);assert(f.good());return std::string(std::istreambuf_iterator<char>(f),{});}
int main(int argc,char **argv){
 assert(argc==2);const auto good=read(argv[1]);WatchUpdate::Catalog data;
 auto parse=[&](const std::string&s){return WatchUpdate::parse({s.data(),s.size()},true,data,nullptr,nullptr);};
 assert(parse(good)&&data.count==1&&data.rows[0].pairedCohort);
 for(auto pair:{std::pair<std::string,std::string>{WatchUpdate::Product,"twatch-s3"},{WatchUpdate::Repository,"michaelrolphone-cmyk/RiscRTE-T-Watch-S3"},{"paired-cohort","runtime-image"},{"firmware-v0.1.13","firmware-v0.1.14"}}){auto bad=good;auto at=bad.find(pair.first);assert(at!=std::string::npos);bad.replace(at,pair.first.size(),pair.second);assert(!parse(bad));}
 assert(parse(good));catalog=&data;risc_bank_store_v1 backend={};backend.struct_size=sizeof(backend);backend.cohort_status=cohortInfo;backend.begin_cohort=denyBegin;bank=&backend;
 risc_bank_status_v1 current={};current.struct_size=sizeof(current);current.store_abi=2;current.firmware_capacity=0x260000;current.store_capacity=0x510000;strcpy(current.layout,"riscrte-paired-appdata-v2");strcpy(current.runtime_version,"0.3.3");
 assert(classifyCohort(data.rows[0],current));
 current.store_abi=1;assert(!classifyCohort(data.rows[0],current));current.store_abi=2;
 strcpy(current.layout,"riscrte-paired-16m-v1");assert(!classifyCohort(data.rows[0],current));strcpy(current.layout,"riscrte-paired-appdata-v2");
 current.store_capacity-=4096;assert(!classifyCohort(data.rows[0],current));current.store_capacity+=4096;
 current.firmware_capacity=32;assert(!classifyCohort(data.rows[0],current));current.firmware_capacity=0x260000;
 installedProduct="twatch-s3";assert(!classifyCohort(data.rows[0],current));installedProduct=WatchUpdate::Product;
 strcpy(data.cohort.runtime_version,"0.0.1");assert(!classifyCohort(data.rows[0],current));assert(parse(good));
 auto usb=good;auto at=usb.find(",\"ota\":");assert(at!=std::string::npos);usb.erase(at,usb.find("},\"apps\":",at)-at);assert(parse(usb)&&data.rows[0].view.availability==SOFTWARE_UPDATE_USB_ONLY&&!data.rows[0].url[0]);
 assert(!WatchUpdate::CatalogUrl[0]);catalog=&catalog_storage;started=true;unsigned before=calls;
 assert(refresh(nullptr,0)&&view.state==SOFTWARE_UPDATE_LIST&&!catalog->count&&calls==before&&!http_handle&&!bank_handle);
 assert(!begin(nullptr,0,1800000000));assert(cancel(nullptr));assert(quiesce());
 puts("Waveshare policy: actual paired payload metadata, identity/ABI/layout/capacity/downgrade refusal; empty feed performs zero I/O PASS");
}
