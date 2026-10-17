/* Production Home; injected API boundaries, never hardware timing. */
static unsigned checkpoints,busy_checkpoints,after_observed_window;
static bool forced_health,forced_frame;
static const char *probe_case;
static bool probe_health(risc_runtime_health_v1 *h){
 check_io();h->uptime_ms=clock_ms;
 if(clock_ms>=18227u)after_observed_window++;
 if(!strcmp(probe_case,"health-return")&&clock_ms>=18227u){forced_health=true;return false;}
 return clock_ms<30000u;
}
static bool probe_status(void*c,uint64_t token,risc_display_present_status_v1*out){
 if(!strcmp(probe_case,"frame-return")&&clock_ms>=18227u){
  check_io();assert(token==submitted&&pending);pending=false;out->state=RISC_DISPLAY_PRESENT_FAILED;forced_frame=true;return true;
 }
 return fast_status(c,token,out);
}
static int32_t probe_checkpoint(void){
 check_io();assert(first_seen&&!held&&!pending&&!owned&&last_complete==submitted);++checkpoints;
 if(!strcmp(probe_case,"context-return")&&clock_ms>=18227u)return RISC_RUNTIME_CHECKPOINT_CONTEXT;
 ++busy_checkpoints;return RISC_RUNTIME_CHECKPOINT_BUSY;
}
int main(int argc,char**argv){
 assert(argc==2);probe_case=argv[1];
 assert(!strcmp(probe_case,"busy-continues")||!strcmp(probe_case,"health-return")||!strcmp(probe_case,"frame-return")||!strcmp(probe_case,"context-return"));
 reset_case();probe_long=true;fixture_provision_mode=2;saved_radio(0);
 fast_runtime.health=probe_health;fast_runtime.service_checkpoint=probe_checkpoint;
 da.base.present_status=probe_status;
 app_main();assert(first_seen&&checkpoints>100&&hardware_brightness>0&&clock_ms>=18227u&&!retains);
 if(!strcmp(probe_case,"context-return")){assert(grants>ungrants&&clock_ms>=18227u&&clock_ms<30000u);}
 else {check_clean();assert(grants==ungrants);}
 if(!strcmp(probe_case,"busy-continues"))assert(clock_ms>=30000u&&!forced_health&&!forced_frame&&busy_checkpoints==checkpoints);
 if(!strcmp(probe_case,"health-return"))assert(forced_health&&!forced_frame&&clock_ms<30000u);
 if(!strcmp(probe_case,"frame-return"))assert(forced_frame&&!forced_health&&clock_ms<30000u);
 printf("HOME_NS_CONTROL case=%s clock_ms=%u checkpoint_calls=%u busy=%u after_window=%u grants=%u releases=%u health_failure=%d frame_failure=%d visible=%d PASS\n",probe_case,clock_ms,checkpoints,busy_checkpoints,after_observed_window,grants,ungrants,forced_health,forced_frame,hardware_brightness>0);
 return 0;
}
