/* Production Home; injected API boundaries, never hardware timing. */
static unsigned checkpoints,busy_checkpoints,after_observed_window;
static bool forced_health,forced_frame;
static const char *probe_case;
static uint16_t probe_completed_snapshot[TEST_WIDTH*TEST_HEIGHT];
static unsigned probe_completed_token;
static bool probe_return_pending,probe_snapshot_frozen;
static void probe_snapshot_completed(void){
 assert(last_complete&&!pending&&!owned);
 memcpy(probe_completed_snapshot,completed_pixels,sizeof(probe_completed_snapshot));
 probe_completed_token=last_complete;probe_snapshot_frozen=true;
}
static void probe_return_boundary(void){
 if(probe_snapshot_frozen)return;
 probe_return_pending=true;
 /* Home drains an accepted transfer after a failed health sample. Freeze its
  * completed pixels when that transfer finishes, before cleanup can run. */
 if(!pending)probe_snapshot_completed();
}
static bool probe_health(risc_runtime_health_v1 *h){
 check_io();h->uptime_ms=clock_ms;
 if(clock_ms>=18227u)after_observed_window++;
 if(!strcmp(probe_case,"health-return")&&clock_ms>=18227u){forced_health=true;probe_return_boundary();return false;}
 if(clock_ms>=30000u){probe_return_boundary();return false;}
 return true;
}
static bool probe_status(void*c,uint64_t token,risc_display_present_status_v1*out){
 if(!strcmp(probe_case,"frame-return")&&clock_ms>=18227u){
  check_io();assert(token==submitted&&pending);pending=false;out->state=RISC_DISPLAY_PRESENT_FAILED;forced_frame=true;probe_return_boundary();return true;
 }
 bool ok=fast_status(c,token,out);
 if(ok&&out->state==RISC_DISPLAY_PRESENT_COMPLETE&&probe_return_pending&&!probe_snapshot_frozen)probe_snapshot_completed();
 return ok;
}
static int32_t probe_checkpoint(void){
 check_io();assert(first_seen&&!held&&!pending&&!owned&&last_complete==submitted);++checkpoints;
 if(!strcmp(probe_case,"context-return")&&clock_ms>=18227u){probe_return_boundary();return RISC_RUNTIME_CHECKPOINT_CONTEXT;}
 ++busy_checkpoints;return RISC_RUNTIME_CHECKPOINT_BUSY;
}
int main(int argc,char**argv){
 assert(argc==2);probe_case=argv[1];
 assert(!strcmp(probe_case,"busy-continues")||!strcmp(probe_case,"health-return")||!strcmp(probe_case,"frame-return")||!strcmp(probe_case,"context-return"));
 reset_case();probe_long=true;fixture_provision_mode=2;saved_radio(0);
 fast_runtime.health=probe_health;fast_runtime.service_checkpoint=probe_checkpoint;
 da.base.present_status=probe_status;
 app_main();assert(first_seen&&checkpoints>100&&hardware_brightness>0&&clock_ms>=18227u&&!retains);
 assert(probe_snapshot_frozen&&probe_completed_token==last_complete);
 assert(!memcmp(probe_completed_snapshot,completed_pixels,sizeof(probe_completed_snapshot)));
 if(!strcmp(probe_case,"context-return")){assert(grants>ungrants&&clock_ms>=18227u&&clock_ms<30000u);}
 else {check_clean();assert(grants==ungrants);}
 if(!strcmp(probe_case,"busy-continues"))assert(clock_ms>=30000u&&!forced_health&&!forced_frame&&busy_checkpoints==checkpoints);
 if(!strcmp(probe_case,"health-return"))assert(forced_health&&!forced_frame&&clock_ms<30000u);
 if(!strcmp(probe_case,"frame-return"))assert(forced_frame&&!forced_health&&clock_ms<30000u);
 printf("HOME_NS_CONTROL case=%s clock_ms=%u checkpoint_calls=%u busy=%u after_window=%u grants=%u releases=%u health_failure=%d frame_failure=%d visible=%d pixels_preserved=1 completed_token=%u PASS\n",probe_case,clock_ms,checkpoints,busy_checkpoints,after_observed_window,grants,ungrants,forced_health,forced_frame,hardware_brightness>0,probe_completed_token);
 return 0;
}
