#include "codec_model.h"
#include "../drivers/codec_es83xx/driver.c"
static void clean_(void){assert(!owned_[0]&&!owned_[1]&&!amp_owned_&&!raw_owned_&&!claims[0]&&!claims[1]&&!amp&&!raw_token&&!tokens[0]&&!tokens[1]);}
static void reset_(void){clean_();memset(registers_,0,sizeof(registers_));calls_=fail_at_=raw_opens_=raw_closes_=0;fail_raw_open_=retain_raw_open_=fail_raw_close_=fail_write_=fail_read_=short_write_=short_read_=false;}
int main(void){
 reset_();assert(start(deps_,4));assert(!amp_level_&&registers_[0][0x0d]==0xfc&&registers_[1][1]==0x7f);unsigned start_count=calls_;
 uint64_t out=0,in=0,bad=99;assert(!open_stream(NULL,3,16000,&bad)&&bad==0);assert(!open_stream(NULL,1,12000,&bad));
 assert(open_stream(NULL,1,16000,&out)&&out&&raw_owned_&&rate_==16000&&directions_==3&&raw_opens_==1);
 assert(registers_[0][0x32]==0xbf&&registers_[0][8]==0xff&&registers_[0][9]==0x0c&&!amp_level_);
 assert(!open_stream(NULL,1,16000,&bad));assert(!open_stream(NULL,2,8000,&bad));assert(open_stream(NULL,2,16000,&in)&&in!=out&&raw_opens_==1);
 assert(registers_[1][0x11]==0x60&&registers_[1][0x12]==0&&registers_[1][0x43]==0x1a&&registers_[1][0x44]==0x1a&&registers_[1][0x4c]==0xff);
 int16_t samples[512];size_t done=0;
 assert(!set_gain(NULL,in,1,1)&&set_gain(NULL,out,1,2)&&mute(NULL,out,false)&&amp_level_);
 for(unsigned i=0;i<512;i++)samples[i]=i&1?-30000:32000;
 assert(write_pcm(NULL,out,samples,256,&done,40)&&done==256&&wire_[0]==16000&&wire_[1]==-15000);
 assert(samples[0]==32000&&samples[1]==-30000);assert(!read_pcm(NULL,out,samples,1,&done,1));
 assert(read_pcm(NULL,in,samples,256,&done,40)&&done==0);assert(read_pcm(NULL,in,samples,256,&done,40)&&done==0);
 short_read_=true;assert(read_pcm(NULL,in,samples,256,&done,40)&&done==128&&samples[0]==1000&&samples[1]==-2000);short_read_=false;
 assert(mute(NULL,out,true)&&!amp_level_);assert(close_stream(NULL,out)&&raw_owned_&&tokens[1]==in);
 assert(read_pcm(NULL,in,samples,32,&done,40)&&done==32);assert(close_stream(NULL,in)&&!raw_owned_&&raw_closes_==1);
 assert(!close_stream(NULL,in));assert(quiesce());clean_();
 /* Every peripheral startup I/O error can be retried only as cleanup. */
 for(unsigned n=1;n<=start_count;n++){reset_();fail_at_=n;assert(!start(deps_,4));fail_at_=0;assert(quiesce());clean_();}
 for(unsigned dir=1;dir<=2;dir++){
  reset_();assert(start(deps_,4));unsigned before=calls_;assert(open_stream(NULL,dir,16000,&out));unsigned count=calls_-before;assert(close_stream(NULL,out)&&quiesce());
  for(unsigned n=1;n<=count;n++){reset_();assert(start(deps_,4));fail_at_=calls_+n;assert(!open_stream(NULL,dir,16000,&out));fail_at_=0;if(out)assert(close_stream(NULL,out));assert(quiesce());clean_();}
 }
 for(unsigned dir=1;dir<=2;dir++){
  reset_();assert(start(deps_,4)&&open_stream(NULL,dir,44100,&out));unsigned before=calls_;assert(close_stream(NULL,out));unsigned count=calls_-before;assert(quiesce());
  for(unsigned n=1;n<=count;n++){reset_();assert(start(deps_,4)&&open_stream(NULL,dir,44100,&out));fail_at_=calls_+n;assert(!close_stream(NULL,out)&&raw_owned_);fail_at_=0;assert(close_stream(NULL,out)&&quiesce());clean_();}
 }
 for(unsigned dir=1;dir<=2;dir++){
  reset_();assert(start(deps_,4));fail_raw_open_=true;assert(!open_stream(NULL,dir,16000,&out)&&!out&&!raw_owned_);fail_raw_open_=false;assert(quiesce());
  reset_();assert(start(deps_,4));fail_raw_open_=retain_raw_open_=fail_raw_close_=true;
  assert(!open_stream(NULL,dir,16000,&out)&&out&&raw_owned_&&fault);assert(!quiesce());fail_raw_close_=false;assert(close_stream(NULL,out)&&quiesce());
 }
 reset_();assert(start(deps_,4)&&open_stream(NULL,1,48000,&out));short_write_=true;
 assert(!write_pcm(NULL,out,samples,128,&done,40)&&done==127&&fault);assert(!write_pcm(NULL,out,samples,128,&done,40)&&done==0);short_write_=false;assert(close_stream(NULL,out)&&quiesce());
 reset_();assert(start(deps_,4)&&open_stream(NULL,2,8000,&in));fail_read_=true;assert(!read_pcm(NULL,in,samples,256,&done,40)&&fault);fail_read_=false;assert(close_stream(NULL,in)&&quiesce());
 reset_();assert(start(deps_,4)&&open_stream(NULL,1,32000,&out));assert(mute(NULL,out,false)&&amp_level_);fail_at_=calls_+1;assert(!mute(NULL,out,true)&&fault);fail_at_=0;assert(close_stream(NULL,out)&&quiesce());clean_();
 puts("ES8311/ES7210: shared duplex clock, stereo PCM/gain/mute, no analog boost, warmup, all startup/codec-close faults and retained transport PASS");
}
