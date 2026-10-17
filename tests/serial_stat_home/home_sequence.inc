/* Native scheduling is injected here; provider/adapter results are real. */

extern void home_probe_start(void),home_probe_ready(void),home_probe_finish(void);
extern int home_probe_stat(void);
static unsigned serial_calls,unavailable_calls,recovered_calls,stopped_grants,stopped_ungrants;
static const char *sequence;
static int32_t sequence_checkpoint(void){
 check_io();assert(first_seen&&!held&&!pending&&!owned&&last_complete==submitted);++serial_calls;
 if(serial_calls==1)home_probe_start();
 if(serial_calls==4)home_probe_ready();
 if(serial_calls<4&&!strcmp(sequence,"busy"))return RISC_RUNTIME_CHECKPOINT_BUSY;
 int rc=home_probe_stat();
 if(serial_calls<4){assert(rc==-3);++unavailable_calls;}else{assert(rc==0);++recovered_calls;}
 if(serial_calls==7&&!strcmp(sequence,"late-retained")){
  stopped_grants=grants;stopped_ungrants=ungrants;retained_fence=true;
  return RISC_RUNTIME_CHECKPOINT_RETAINED;
 }
 return RISC_RUNTIME_CHECKPOINT_OK;
}
int main(int argc,char**argv){
 assert(argc==2);sequence=argv[1];assert(!strcmp(sequence,"unavailable")||!strcmp(sequence,"busy")||!strcmp(sequence,"late-retained"));
 reset_case();fixture_provision_mode=2;saved_radio(0);fast_runtime.service_checkpoint=sequence_checkpoint;
 app_main();assert(first_seen&&serial_calls>=7&&!pending&&!held&&!owned);
 if(!strcmp(sequence,"late-retained")){assert(retained_fence&&serial_calls==7&&grants==stopped_grants&&ungrants==stopped_ungrants&&grants>ungrants);}
 else{check_clean();fprintf(stderr,"observed confirmations=%u scans=%u checkpoint_calls=%u time=%u\n",confirmations,fixture_provision_scans,serial_calls,clock_ms);assert(confirmations==2&&fixture_provision_scans==5);}
 assert(unavailable_calls==(!strcmp(sequence,"busy")?0:3)&&recovered_calls>0);
 home_probe_finish();printf("Home actual provider sequence=%s checkpoint_calls=%u unavailable=%u recovered=%u retained=%d clean=%d PASS\n",sequence,serial_calls,unavailable_calls,recovered_calls,retained_fence,!retained_fence);
 return 0;
}
