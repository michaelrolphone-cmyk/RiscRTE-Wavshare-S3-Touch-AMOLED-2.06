static void serialNativeApp(){
 const auto*api=risc_runtime_get_api(1);assert(api&&f);
 file("/ordinary.txt","keep",4);file("/old.txt","old",3);file("/unrelated.txt","untouched",9);
 auto drain=[&](){std::string out;while(serialEndpoint.outputSize()){out.append(serialEndpoint.output(),serialEndpoint.outputSize());serialEndpoint.consumeOutput(serialEndpoint.outputSize());}return out;};
 auto submit=[&](const char*cmd){assert(!serialEndpoint.outputSize());std::string q="RTEF1 12345678 "+std::to_string(++serialSequence)+" "+cmd+"\n";for(unsigned char b:q)serialEndpoint.input(b);};
 const bool stalled=scenario.find("stall")!=std::string::npos;
 const unsigned cadence=scenario.find("pace8")!=std::string::npos?8:scenario.find("pace16")!=std::string::npos?16:scenario.find("pace32")!=std::string::npos?32:scenario.find("slow")!=std::string::npos?50:1;
 const bool expectBusy=stalled||cadence>=50;
 auto request=[&](const char*cmd,int expected=0){
  const auto start=nowMs;submit(cmd);std::string out;unsigned checkpoints=0;
  while(out.empty()&&nowMs-start<5000&&checkpoints<20000){
   const auto rc=api->service_checkpoint();++checkpoints;assert(rc==RISC_RUNTIME_CHECKPOINT_OK||rc==RISC_RUNTIME_CHECKPOINT_BUSY);
   out=drain();if(!out.empty())break;api->yield_ms(cadence);assert(risc_runtime_get_api(1));
  }
  printf("EXCHANGE op=%s elapsed_ms=%llu checkpoints=%u continuing=%d session=%llu pin=%d pending=%d wire=%s\n",cmd,(unsigned long long)(nowMs-start),checkpoints,L::continuing(),(unsigned long long)f->session(),port->nativeStorageAttached(),serialEndpoint.pending(),out.c_str());fflush(stdout);
  assert(!out.empty()&&nowMs-start<5000);const auto prefix="RTEF1 12345678 "+std::to_string(serialSequence)+" "+std::to_string(expected);
  assert(out.rfind(prefix,0)==0&&(out[prefix.size()]==' '||out[prefix.size()]=='\n'));return out;
 };
 risc_runtime_capability_v1 atomic{sizeof(atomic)};assert(api->acquire(RISC_KEY_VALUE_ATOMIC_CAPABILITY,1,1,&atomic));
 for(unsigned i=0;i<20000&&!(L::continuing()&&port->nativeStorageAttached()&&f->session());++i)api->yield_ms(1);
 assert(L::continuing()&&port->nativeStorageAttached()&&f->session());
 const auto confirmBefore=confirmCalls;assert(!api->confirm_boot());assert(confirmCalls==confirmBefore+1);
 printf("CONFIRM_ACTIVE accepted=0 callback=1 strict=%d discovery_safe=%d continuing=%d session=%llu pin=%d retained=%d\n",port->providerStorageSafe(),port->nativeDiscoveryProviderSafe(),L::continuing(),(unsigned long long)f->session(),port->nativeStorageAttached(),L::retained());
 const auto start=nowMs;if(stalled)holdUntil=nowMs+5100;
 assert(request("HELLO").find("HELLO 48 511 2")!=std::string::npos);
 assert(request("NS 0").find("NS 2 1")!=std::string::npos);assert(request("NS 1").find("NS 12 1")!=std::string::npos);
 assert(nowMs==start&&L::continuing());request("PATH 0 2f6f6c642e747874");
 if(expectBusy){
  request("STAT 12",RISC_FILES_BUSY);assert(!serialClient.retained()&&L::continuing());
  serialEndpoint.disconnect();holdUntil=0;assert(!serialEndpoint.pending());
 }else{
  assert(request("STAT 12").find("STAT 6 3")!=std::string::npos);
  assert(request("GET 12").find("GET 3")!=std::string::npos);assert(request("READ 0").find("READ 3 6f6c64")!=std::string::npos);request("CLOSE");
  // Guarded replacement is admitted only after exact old bytes matched.
  request("PUT 12 replace 4");request("WRITE 0 6e657721");request("COMMIT 98b6a988");
  request("GET 12");assert(request("READ 0").find("READ 4 6e657721")!=std::string::npos);request("CLOSE");
  request("PATH 0 2f6e65772e747874");request("STAT 12",RISC_FILES_NOT_FOUND);
  request("PUT 12 create 4");request("WRITE 0 6e657721");request("COMMIT 98b6a988");
  request("GET 12");assert(request("READ 0").find("READ 4 6e657721")!=std::string::npos);request("CLOSE");
  request("PATH 0 2f756e72656c617465642e747874");request("GET 12");assert(request("READ 0").find("READ 9 756e746f7563686564")!=std::string::npos);request("CLOSE");
  printf("FULL_TRANSFER guarded-replace=1 create=1 readback=1 unrelated-preserved=1\n");
 }
 for(unsigned i=0;i<20000&&L::continuing();++i)api->yield_ms(1);
 assert(L::exitSafe()&&!L::retained());
 assert(api->confirm_boot());printf("CONFIRM_SETTLED accepted=1 strict=%d continuing=%d pin=%d\n",port->providerStorageSafe(),L::continuing(),port->nativeStorageAttached());
 printf("DISCOVERY_END elapsed_ms=%llu retained=%d exit=%d pinned=%d\n",(unsigned long long)(nowMs-start),L::retained(),L::exitSafe(),port->nativeStorageAttached());
 assert(api->release(&atomic));
}
