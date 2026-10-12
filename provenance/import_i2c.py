"""Readable one-time migration from the pinned T-Watch ABI/provider sources."""
from pathlib import Path
import shutil,json
V=Path(__file__).resolve().parents[1];W=V/'.source/twatch'
for src,dst in [('twatch_support.h','DriverSupport.h'),('twatch_hardware.h','DriverHardware.h'),('twatch_util.h','DriverUtil.h')]:
 p=V/'include'/dst;p.parent.mkdir(exist_ok=True)
 s=(W/'include'/src).read_text().replace('"twatch_support.h"','"DriverSupport.h"').replace('"twatch_hardware.h"','"DriverHardware.h"').replace('"twatch_util.h"','"DriverUtil.h"');p.write_text(s)
for name in ['rtc_pcf85063','touch_ft3168','power_axp2101','panel_co5300']:(V/'drivers'/name).mkdir(parents=True,exist_ok=True)
rtc=(W/'drivers/twatch_rtc/driver.c').read_text();rtc=rtc[rtc.index('#include'):].replace('"twatch_support.h"','"DriverSupport.h"').replace('nxp,pcf8563','nxp,pcf85063a').replace('"twatch-rtc"','"waveshare-rtc"')
rtc=rtc.replace('read_regs(0x02u, raw, 7)','read_regs(0x04u, raw, 7)').replace('write_regs(0x02u, raw, 7)','write_regs(0x04u, raw, 7)')
rtc=rtc.replace('if ((raw[0] & 0x80u) || (raw[5] & 0x80u))','if (raw[0] & 0x80u)')
rtc=rtc.replace('/* 255 disables that alarm compare field. PCF8563 minute-resolution alarm. */','/* Keep rtc.clock@2 minute resolution: seconds are matched at 00, disabled fields use AE=1. */')
rtc=rtc.replace('uint8_t fields[] = {minute','uint8_t fields[] = {0, minute')
rtc=rtc.replace('status & ~0x0a','status & ~(0xc0u)').replace('write_regs(9, fields, 4)','write_regs(0x0b, fields, 5)').replace('enable ? 2 : 0','enable ? 0x80u : 0')
rtc=rtc.replace('(v & 8) != 0','(v & 0x40u) != 0').replace('v &= ~8;','v &= ~0x40u;').replace('v &= ~2;','v &= ~0x80u;')
rtc=rtc.replace('uint8_t control = 0, clkout = 0;','uint8_t control = 0;').replace('control &= ~0x20;','/* Select 24-hour mode and start oscillator; do not write CTRL2 here.\n     * CTRL2 carries live alarm state on this chip, not a separate clock-out register. */\n    control &= ~(0x20u | 0x02u);').replace(' || !write_regs(0x0d, &clkout, 1)','')
rtc=rtc.replace('out->second =','twatch_rtc_time_v1 value={0};\n    value.second =',1)
for n in ['minute','hour','day','weekday','month','year']:rtc=rtc.replace(f'out->{n} =',f'value.{n} =',1)
rtc=rtc.replace('return tw_valid_time(out);','if (!tw_valid_time(&value)) return false;\n    *out=value;\n    return true;',1)
rtc=rtc.replace('if (!bus || !bus->claim_device(bus->context, config->address, &claim))\n        return false;','if (!bus->claim_device(bus->context, config->address, &claim)) {\n        (void)quiesce(); return false;\n    }')
rtc='/* PCF85063A: preserves the deployed rtc.clock@2 ABI. Register mapping follows\n * NXP PCF85063A and the pinned Waveshare SensorLib example; no PCF8563 assumptions. */\n'+rtc
(V/'drivers/rtc_pcf85063/driver.c').write_text(rtc)
m=json.loads((W/'drivers/twatch_rtc/manifest.json').read_text());m.update(id='waveshare-rtc',version='0.1.0',status='development');m['hardware_compatibility'][0]['compatible']='nxp,pcf85063a';(V/'drivers/rtc_pcf85063/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
s=(W/'drivers/current/twatch_touch/driver.c').read_text();s=s[s.index('#include'):].replace('"twatch_support.h"','"DriverSupport.h"').replace('"twatch_util.h"','"DriverUtil.h"').replace('focaltech,ft6336u','focaltech,ft3168').replace('"twatch-touch"','"waveshare-touch"')
s=s.replace('static uint64_t claim, irq;','static uint64_t claim, irq, reset;').replace('if (started || claim || irq)','if (started || claim || irq || reset)')
s=s.replace('config->reset != -1 || !tw_pin(config->irq)','!tw_pin(config->reset) || !tw_pin(config->irq)')
s=s.replace('config->irq == config->bus.scl || config->irq_pull_up > 1 || config->irq_active_high > 1)','config->irq == config->bus.scl || config->irq_pull_up > 1 || config->irq_active_high > 1 ||\n        config->reset_active_high > 1 || !config->reset_assert_ms || config->reset_assert_ms>500 ||\n        !config->reset_recovery_ms || config->reset_recovery_ms>500)')
s=s.replace('    bus = tw_dep(deps, count, "i2c.bus", sizeof(*bus));','    int16_t pins[]={config->bus.sda,config->bus.scl,config->irq,config->reset};\n    if (!tw_unique(pins,4)) return false;\n    bus = tw_dep(deps, count, "i2c.bus", sizeof(*bus));',1)
s=s.replace('    claim = irq = 0;','    if (reset) {\n        if (!gpio_api->release(gpio_api->context,reset)) return false;\n        reset=0;\n    }\n    claim = irq = 0;',1)
s=s.replace('    started = true;\n    return true;','    if (!gpio_api->claim(gpio_api->context,config->reset,RISC_GPIO_OUTPUT,&reset) ||\n        !gpio_api->write(gpio_api->context,reset,config->reset_active_high)) {\n        (void)quiesce_impl();return false;\n    }\n    clock_api->sleep_ms(clock_api->context,config->reset_assert_ms);\n    if (!gpio_api->write(gpio_api->context,reset,!config->reset_active_high)) {\n        (void)quiesce_impl();return false;\n    }\n    clock_api->sleep_ms(clock_api->context,config->reset_recovery_ms);\n    uint8_t report[13];\n    if (!read_reg(FT_TD_STATUS,report,sizeof(report)) || (report[0]&15)>2) {\n        (void)quiesce_impl();return false;\n    }\n    started = true;\n    return true;',1)
start=s.index('        for (uint8_t i = 0; i < count; ++i) {\n            if (next_c[i].x');end=s.index('        contact_count = count;',start);block=s[start:end];split=block.index('        for (uint8_t j = 0; j < contact_count; ++j) {\n            bool still');s=s[:start]+block[split:]+block[:split]+s[end:]
s=s.replace('            bool seen = false;\n            for (uint8_t j = 0; j < contact_count; ++j)\n                if (contacts[j].id == next_c[i].id)\n                    seen = true;\n            push(seen ? RISC_TOUCH_EVENT_MOVE : RISC_TOUCH_EVENT_DOWN, next_c[i].id, next_c[i].x,\n                 next_c[i].y);','            bool seen=false,changed=true;\n            for (uint8_t j=0;j<contact_count;++j)\n                if (contacts[j].id==next_c[i].id) {\n                    seen=true;changed=contacts[j].x!=next_c[i].x || contacts[j].y!=next_c[i].y;\n                }\n            if (changed) push(seen?RISC_TOUCH_EVENT_MOVE:RISC_TOUCH_EVENT_DOWN,\n                              next_c[i].id,next_c[i].x,next_c[i].y);')
s='/* FT3168 capacitive touch. Coherent 12-bit coordinate reports; reset, IRQ and\n * dimensions come from the board descriptor. No watch-resolution constants. */\n'+s
(V/'drivers/touch_ft3168/driver.c').write_text(s)
m=json.loads((W/'drivers/current/twatch_touch/manifest.json').read_text());m.update(id='waveshare-touch',version='0.1.0',status='development');m['requires']=[x for x in m['requires'] if x['capability']!='board.battery'];m['hardware_compatibility'][0]['compatible']='focaltech,ft3168';(V/'drivers/touch_ft3168/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(V/'include/common').mkdir(exist_ok=True)
for name in ('gpio.h','dependency.h','display.h'):shutil.copy2(W/'include/common'/name,V/'include/common'/name)
p=V/'include/common/display.h';p.write_text(p.read_text().replace(',.nominal_refresh_millihz = config->bus.frequency_hz==40000000 ? 20000 : 0',',.nominal_refresh_millihz = 0'))
for name in ('RiscSpiQuadV1.h','RiscDisplaySpiV2.h'):shutil.copy2(V/'.source/shared/sdk/driver'/name,V/'include'/name)
(V/'provenance/sources.json').write_text(json.dumps({'schema':1,'watch_source':{'repository':'michaelrolphone-cmyk/RiscRTE-T-Watch-S3','commit':'851b8998e804c57b2c9f42d9f8fd0a69e79f2b41'},'vendor_reference':{'repository':'waveshareteam/ESP32-S3-Touch-AMOLED-2.06','commit':'b099739ad0e33b34e5fbaae77f02bd84805d79a3'},'physical_verification':False},indent=2)+'\n')
