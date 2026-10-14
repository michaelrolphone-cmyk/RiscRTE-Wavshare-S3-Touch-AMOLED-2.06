from pathlib import Path
import sys
r=Path(sys.argv[1]);o=Path(sys.argv[2]);o.mkdir(exist_ok=True,parents=True)
s=(r/'test/native_sd_port_test.cpp').read_text().replace('pin==5','pin==17').replace('c==41&&m==42&&d==40','c==2&&m==1&&d==3')
(o/'native_sd_port_test.cpp').write_text(s)
s=(r/'test/native_settings_maintenance_test.cpp').read_text()
s=s.replace('static const L::Writer writers[]={{"maintenance-test",1},{"maintenance-test",6}};','static const L::Writer writers[]={{"maintenance-test",6}};')
s=s.replace('},9);','},12);').replace('},9,writers,2,bootstrapClient);','},12,writers,1,bootstrapClient);').replace('Pin anchor(runtime,cpu,9)','Pin anchor(runtime,cpu,12)').replace('P fresh(runtime,cpu,1,9)','P fresh(runtime,cpu,6,12)')
s=s.replace('F::rootPath=argv[3];F::empty();','F::rootPath=argv[3];if(scenario=="wave-reload"||scenario=="wave-final"){F::reset();loadNvs();}else F::empty();')
s=s.replace(' {F::Fixture a(1),b(6);',' if(scenario=="wave-save"||scenario=="wave-first"){F::Fixture a(1),b(6);')
s=s.replace(' if(!noCard()){const auto*e=', ' if(!noCard()&&(scenario=="wave-save"||scenario=="wave-first")){const auto*e=')
s=s.replace('extern "C" void test_maintenance_app(){','''extern "C" void wave_wifi(const risc_runtime_api_v1*,unsigned);
extern "C" void wave_yield(){risc_runtime_get_api(1)->yield_ms(1);}
extern "C" void test_maintenance_app(){
 if(scenario.rfind("wave-",0)==0){
  assert(L::ready()&&!cores[0]->ready()&&cores[1]->ready());
  wave_wifi(risc_runtime_get_api(1),scenario=="wave-final"?3:scenario=="wave-reload"?1:0);settle();
  assert(!cores[1]->pendingCount());
  wave_wifi(risc_runtime_get_api(1),scenario=="wave-final"?3:1);settle();
  if(scenario=="wave-reload"){wave_wifi(risc_runtime_get_api(1),2);settle();assert(!cores[1]->pendingCount());}
  assert(!anchorPin->release()&&!f);return;
 }
''')
needle=' const bool hydrated=bootReady&&oneCore.ready()&&sixCore.ready()&&!L::retained();F::armed=false;'
s=s.replace(needle,needle+'''
 if(scenario.rfind("wave-",0)==0){
  assert(bootReady&&attached&&!oneCore.ready()&&sixCore.ready());
  const auto oneBefore=F::nvs.at("rnr00000001");
  assert(runtime.run());assert(L::exitSafe()&&!L::retained()&&!f);
  assert(F::nvs.at("rnr00000001")==oneBefore&&!oneCore.ready());saveNvs();
  printf("Wave actual Runtime/lifecycle/SD/FatFs + System Wi-Fi %s: save two profiles, app re-entry, SD acknowledgement, namespace 1 isolation PASS\\n",scenario.c_str());fflush(stdout);std::_Exit(0);
 }
''')
s=s.replace('scenario.rfind("first",0)==0','(scenario.rfind("first",0)==0||scenario=="wave-first")').replace('scenario.rfind("first",0)!=0','(scenario.rfind("first",0)!=0&&scenario!="wave-first")')
(o/'maintenance.cpp').write_text(s)
