/* ES8311 DAC / ES7210 stereo microphone ADC, selected by board metadata.
 * Codec sequences derived from Espressif's Apache-2.0 esp_codec_dev sources and
 * Waveshare's ES8311 reference. See THIRD_PARTY_NOTICES.md. The shared physical
 * clock/session is exposed as generic audio.pcm, not a private battery suffix
 * or a device-specific audio capability. */
#include "DriverSupport.h"
#include "RiscAudioPcmV1.h"
#include "RiscI2sStandardV1.h"
#include "RiscI2sStandardConfigV1.h"
static const risc_hw_i2s_standard_v1 *config;
static const risc_i2c_bus_api_v1 *bus;
static const garden_gpio_v1 *gpio;
static const risc_i2s_standard_api_v1 *transport;
static uint64_t claims[2],amp,raw_token,tokens[2],next_token;
static uint32_t sample_rate,warmup;
static uint16_t gain=1,gain_maximum=1;
static bool started,fault,dirty[2],muted=true;
static bool read_reg(unsigned chip,uint8_t reg,uint8_t *value) {
    return claims[chip]&&bus->transact(bus->context,claims[chip],&reg,1,value,1,20);
}
static bool put(unsigned chip,uint8_t reg,uint8_t value) {
    const uint8_t bytes[]={reg,value};
    return claims[chip]&&bus->transact(bus->context,claims[chip],bytes,2,NULL,0,20);
}
static bool sequence(unsigned chip,const uint8_t (*registers)[2],size_t count) {
    for(size_t i=0;i<count;i++)if(!put(chip,registers[i][0],registers[i][1]))return false;
    return true;
}
#define SEQUENCE(chip,table) sequence(chip,table,sizeof(table)/sizeof(table[0]))
static bool amplifier(bool enabled) {
    return !amp || gpio->write(gpio->context,amp,enabled==!!config->enable_active_high);
}
static bool standby(unsigned chip) {
    if(!dirty[chip])return true;
    if(!chip) {
        if(!amplifier(false))return false;
        const uint8_t registers[][2]={{0x32,0},{0x17,0},{0x0e,0xff},{0x12,2},{0x14,0},{0x0d,0xfa},
            {0x15,0},{2,0x10},{0,0},{0,0x1f},{1,0x30},{1,0},{0x45,0},{0x0d,0xfc},{2,0}};
        if(!SEQUENCE(0,registers))return false;
        muted=true;
    } else {
        const uint8_t registers[][2]={{0x47,0xff},{0x48,0xff},{0x49,0xff},{0x4a,0xff},
            {0x4b,0xff},{0x4c,0xff},{0x40,0xc0},{1,0x7f},{6,7}};
        if(!SEQUENCE(1,registers))return false;
    }
    dirty[chip]=false;return true;
}
static bool initialize(unsigned chip) {
    dirty[chip]=true;
    if(!chip) {
        /* The 256*Fs coefficient is the same for every admitted rate. Output
         * starts muted at unity analog gain (0xbf), never the +32 dB register
         * maximum. Public gain scales the copied PCM samples linearly. */
        const uint8_t registers[][2]={{0,0x1f},{0,0},{0,0x80},{1,0x3f},{2,0},{3,0x10},{4,0x10},
            {5,0},{6,3},{7,0},{8,0xff},{9,0x0c},{0x0a,0x0c},{0x0d,1},{0x0e,2},{0x12,0},
            {0x13,0x10},{0x1c,0x6a},{0x37,8},{0x31,0x60},{0x32,0xbf}};
        if(!amplifier(false)||!SEQUENCE(0,registers))return false;
        muted=true;
    } else {
        /* Slave, external MCLK, 16-bit standard I2S, MIC1/MIC2 at 30 dB.
         * MIC3 echo reference is not enabled; this does not claim software AEC. */
        const uint8_t registers[][2]={{0,0xff},{0,0x41},{1,0x3f},{9,0x30},{0x0a,0x30},
            {0x23,0x2a},{0x22,0x0a},{0x20,0x0a},{0x21,0x2a},{8,0},{0x40,0x43},
            {0x41,0x70},{0x42,0x70},{7,0x20},{2,0xc1},{0x11,0x60},{0x12,0},
            {0x43,0x1a},{0x44,0x1a},{0x45,0},{0x46,0},{0x4b,0},{0x4c,0xff},
            {1,0x34},{6,0},{0x47,8},{0x48,8},{0x49,0xff},{0x4a,0xff},
            {0x14,0},{0x15,0},{0x40,0x43},{0,0x71},{0,0x41}};
        if(!SEQUENCE(1,registers))return false;
        /* Discard queued samples collected before the ADC's new session, in
         * bounded ordinary read calls. Successful short/zero reads are legal. */
        warmup=512;
    }
    return true;
}
static int slot(uint64_t token) {
    if(!token)return -1;
    if(tokens[0]==token)return 0;
    return tokens[1]==token?1:-1;
}
static bool close_stream(void *context,uint64_t token) {
    (void)context;int index=slot(token);if(index<0)return false;
    if(!standby((unsigned)index)){fault=true;return false;}
    if(!tokens[1-index] && raw_token) {
        if(!transport->close(transport->context,raw_token)){fault=true;return false;}
        raw_token=0;sample_rate=0;fault=false;
    }
    tokens[index]=0;return true;
}
static bool open_stream(void *context,uint8_t direction,uint32_t rate,uint64_t *out) {
    (void)context;if(out)*out=0;
    if(!started||fault||!out||(direction!=1&&direction!=2)||
       (rate!=8000&&rate!=16000&&rate!=22050&&rate!=32000&&rate!=44100&&rate!=48000))return false;
    const unsigned index=direction-1;
    if(tokens[index] || (raw_token&&sample_rate!=rate) || next_token==UINT64_MAX)return false;
    tokens[index]=++next_token;*out=tokens[index];
    if(!raw_token) {
        sample_rate=rate;
        if(!transport->open(transport->context,RISC_I2S_DUPLEX,rate,&raw_token)||!raw_token) {
            fault=raw_token!=0;
            if(!raw_token || close_stream(NULL,*out)){tokens[index]=0;*out=0;sample_rate=0;}
            return false;
        }
    }
    if(!initialize(index)) {
        fault=true;
        if(close_stream(NULL,*out))*out=0;
        return false;
    }
    return true;
}
static bool mute(void *context,uint64_t token,bool value) {
    (void)context;if(!started||fault||slot(token)!=0)return false;
    if(value==muted)return true;
    if(value && !amplifier(false)){fault=true;return false;}
    if(!put(0,0x31,value?0x60:0)){fault=true;(void)amplifier(false);return false;}
    if(!value && !amplifier(true)){fault=true;(void)amplifier(false);return false;}
    muted=value;return true;
}
static bool set_gain(void *context,uint64_t token,uint16_t value,uint16_t maximum) {
    (void)context;if(!started||fault||slot(token)!=0||!maximum||value>maximum)return false;
    gain=value;gain_maximum=maximum;return true;
}
static bool write_pcm(void *context,uint64_t token,const int16_t *pcm,size_t frames,size_t *done,uint32_t ms) {
    (void)context;if(done)*done=0;
    if(!started||fault||slot(token)!=0||!pcm||!frames||frames>256||!done||!ms||ms>40)return false;
    int16_t copy[512];
    for(size_t i=0;i<frames*2;i++)copy[i]=(int16_t)((int32_t)pcm[i]*gain/gain_maximum);
    if(!transport->write(transport->context,raw_token,copy,frames,done,ms)||*done!=frames) {
        fault=true;(void)amplifier(false);return false;
    }
    return true;
}
static bool read_pcm(void *context,uint64_t token,int16_t *pcm,size_t frames,size_t *done,uint32_t ms) {
    (void)context;if(done)*done=0;
    if(!started||fault||slot(token)!=1||!pcm||!frames||frames>256||!done||!ms||ms>40)return false;
    if(!transport->read(transport->context,raw_token,pcm,frames,done,ms)||*done>frames) {
        fault=true;(void)amplifier(false);return false;
    }
    size_t discard=warmup<*done?warmup:*done;
    warmup-=(uint32_t)discard;*done-=discard;
    if(*done && discard)memmove(pcm,pcm+discard*2,*done*4);
    return true;
}
static bool quiesce(void) {
    if(tokens[0]&&!close_stream(NULL,tokens[0]))return false;
    if(tokens[1]&&!close_stream(NULL,tokens[1]))return false;
    if(!standby(0)||!standby(1)||!amplifier(false))return false;
    if(raw_token){if(!transport->close(transport->context,raw_token))return false;raw_token=0;}
    for(unsigned i=0;i<2;i++)if(claims[i]) {
        if(!bus->release_device(bus->context,claims[i]))return false;
        claims[i]=0;
    }
    if(amp){if(!gpio->release(gpio->context,amp))return false;amp=0;}
    started=fault=false;sample_rate=warmup=0;return true;
}
static bool start(const risc_provider_dependency_v1 *deps,size_t n) {
    if(started||raw_token||amp||claims[0]||claims[1])return false;
    config=tw_config(deps,n,"everest,es8311-es7210","audio.i2s-standard",sizeof(*config));
    if(!config||config->output_address==config->input_address||config->enable_active_high>1||
       !tw_bus_limit(&config->bus,RISC_HW_BUS_I2C,400000))return false;
    bus=tw_dep(deps,n,"i2c.bus",sizeof(*bus));
    gpio=tw_dep(deps,n,"platform.gpio",offsetof(garden_gpio_v1,deep_sleep_hold));
    transport=tw_dep(deps,n,RISC_I2S_STANDARD_CAPABILITY,sizeof(*transport));
    if(!tw_i2c_valid(bus)||!gpio||!gpio->claim||!gpio->write||!gpio->release||!transport||
       !transport->open||!transport->read||!transport->write||!transport->close)return false;
    if(config->enable>=0 && !gpio->claim(gpio->context,config->enable,true,!config->enable_active_high,false,&amp))goto fail;
    if(!bus->claim_device(bus->context,config->output_address,&claims[0])||
       !bus->claim_device(bus->context,config->input_address,&claims[1]))goto fail;
    uint8_t response;
    if(!read_reg(0,0,&response)||!read_reg(1,0,&response))goto fail;
    dirty[0]=dirty[1]=true;
    if(!standby(0)||!standby(1))goto fail;
    gain=gain_maximum=1;started=true;return true;
fail:
    (void)quiesce();return false;
}
static const risc_audio_pcm_api_v1 api={1,sizeof(api),NULL,open_stream,write_pcm,read_pcm,set_gain,mute,close_stream};
TW_DRIVER("es83xx-audio","audio.pcm",1,api)
