from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1]
if (r/'provenance/display-rail-013.json').exists():raise SystemExit(0)
# Short PMIC register sessions: even future display reinitialization may query the rail while the gauge is active.
p=r/'drivers/power_axp2101/driver.c';s=p.read_text()
a=s.index('static bool read_reg(');b=s.index('static bool pending(',a)
s=s[:a]+'''/* Register-level leases, not a lifetime claim on the whole PMIC. All calls
 * run synchronously on the provider owner. A failed release retains its token
 * and makes subsequent normal I/O refuse until cleanup succeeds. */
static bool register_io(const uint8_t *tx,size_t n,uint8_t *rx,size_t rn) {
    if(claim || !bus || !bus->claim_device(bus->context,config->address,&claim))return false;
    bool ok=bus->transact(bus->context,claim,tx,n,rx,rn,30);
    if(!bus->release_device(bus->context,claim))return false;
    claim=0;return ok;
}
static bool read_reg(uint8_t reg,uint8_t *out,size_t n) {return register_io(&reg,1,out,n);}
static bool write_reg(uint8_t reg,uint8_t value) {
    uint8_t bytes[]={reg,value};return register_io(bytes,2,NULL,0);
}
'''+s[b:]
s=s.replace('if(!bus->claim_device(bus->context,config->address,&claim) ||\n       !gpio_api->claim','if(!gpio_api->claim')
s=s.replace('if (!started || retained)','if (!started || retained || claim)')
p.write_text(s)
p=r/'drivers/power_axp2101/manifest.json';j=json.loads(p.read_text());j['version']='0.1.1';p.write_text(json.dumps(j,indent=2)+'\n')
# Use independent rail under reset. The shared Home and native Runtime stay unchanged.
p=r/'drivers/panel_co5300/driver.c';s=p.read_text().replace('#include "twatch_power.h"','#include "twatch_power.h"\n#include "RiscPowerRailV1.h"\n#include "ProviderLog.h"')
s=s.replace('static const garden_spi_v1 *spi;','static const garden_spi_v1 *spi;\nstatic const risc_power_rail_api_v1 *rail;')
s=s.replace('    if(!gpio_claim(config->reset,true,true))return false;', '''    rail=tw_dep(d,n,RISC_POWER_RAIL_CAPABILITY,sizeof(*rail));
    if(!rail || !rail->get_info || !rail->set_enabled)return false;
    /* Hold reset before rail configuration, then verify actual pad readback.
     * Rail selection is a generic dependency, never a cast of board.battery. */
    if(!gpio_claim(config->reset,true,false))return false;
    if(gpio_read(config->reset) || io_fault) {
        provider_log("PANEL_RESET stage=assert expected=0 result=failed");return false;
    }
    provider_log("PANEL_RESET stage=assert expected=0 readback=0");
    if(!rail->set_enabled(rail->context,true))return false;
    risc_power_rail_info_v1 supply={.struct_size=sizeof(supply)};
    if(!rail->get_info(rail->context,&supply) || !supply.configuration_verified || !supply.enabled) {
        provider_log("PANEL_POWER result=failed operation=consumer-readback");return false;
    }
    provider_log("PANEL_POWER result=ready consumer=display");''')
s=s.replace('    gpio_write(config->reset,true);timer->sleep_ms(timer->context,200);if(io_fault)return false;', '''    gpio_write(config->reset,true);timer->sleep_ms(timer->context,200);
    if(!gpio_read(config->reset) || io_fault) {
        provider_log("PANEL_RESET stage=release expected=1 result=failed");return false;
    }
    provider_log("PANEL_RESET stage=release expected=1 readback=1");''')
s=s.replace('    timer->sleep_ms(timer->context,250);','    provider_log("PANEL_PROBE phase=all-on brightness=64 duration_ms=750 control=write-only");\n    timer->sleep_ms(timer->context,750);')
s=s.replace('    if(!command(0x13,NULL,0)||!set_byte(0x51,0))return false;','    if(!command(0x13,NULL,0)||!set_byte(0x51,0))return false;\n    provider_log("PANEL_PROBE phase=normal-mode-restored control=write-only");')
s=s.replace('25% brightness for 250 ms','25% brightness for 750 ms')
s=s.replace('    brightness=requested;return true;', '''    if(!brightness && requested) {
        provider_log("PANEL_BRIGHTNESS transition=off-to-on transport=complete visibility=unverified");
    }
    brightness=requested;return true;''')
p.write_text(s)
p=r/'drivers/panel_co5300/manifest.json';j=json.loads(p.read_text());j['version']='0.1.2';j['requires'].append({'capability':'power.rail','api':1});p.write_text(json.dumps(j,indent=2)+'\n')
# Include Runtime API for bounded diagnostic-only imports, explicitly allow this one import.
for name in ['build_drivers.py','test_drivers.py']:
 p=r/'scripts'/name;s=p.read_text().replace("w/'sdk/driver',w/'include'","w/'sdk/driver',w/'sdk/app',w/'include'").replace("a.watch/'sdk/driver',a.watch/'include'","a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include'")
 if name=='build_drivers.py':
  s=s.replace("'strchr','malloc'","'strchr','snprintf','risc_runtime_get_api','malloc'")
 p.write_text(s)
p=r/'scripts/build_boot_test.py';s=p.read_text().replace('Waveshare-0.1.2-','Waveshare-0.1.3-').replace("'version':'0.1.2'","'version':'0.1.3'")
s=s.replace("[S/'sdk/driver',S/'include',device/'include']","[S/'sdk/driver',S/'sdk/app',S/'include',device/'include']")
needle=" build(G/'Drivers/legacy_power_key/driver.c'"
a=s.index(needle)
s=s[:a]+''' source=device/'drivers/display_rail_axp2101'
 build(source/'driver.c',store/'rail/driver.elf',[S/'sdk/driver',S/'sdk/app',S/'include',device/'include'],'t5_driver_get')
 shutil.copy2(source/'manifest.json',store/'rail/manifest.json')
 boot['drivers'].append({'manifest':'rail/manifest.json'})
'''+s[a:]
s=s.replace('len(expected)!=28','len(expected)!=30').replace("n.endswith('.elf') for n in expected)!=13","n.endswith('.elf') for n in expected)!=14")
s=s.replace("'panel_driver':'0.1.1'","'panel_driver':'0.1.2','power_rail':'0.1.0','battery_driver':'0.1.1'").replace('ALLPON 25 percent 250 ms','ALDO2 register verification then ALLPON 25 percent 750 ms')
s=s.replace("('missing-provider',lambda:(damaged/'touch/manifest.json').unlink())]","('missing-provider',lambda:(damaged/'touch/manifest.json').unlink()),\n         ('missing-power-rail',lambda:(damaged/'rail/manifest.json').unlink())]")
p.write_text(s)
p=r/'tests/test_panel.c';s=p.read_text().replace('#include "DriverSupport.h"','#include "DriverSupport.h"\n#include "RiscPowerRailV1.h"\n#include "provider_log_mock.h"')
s=s.replace('static bool reset_claimed,bus_claimed,bus_active,reset_high,held_reset;', 'static bool reset_claimed,bus_claimed,bus_active,reset_high,held_reset;\nstatic bool rail_ready,rail_refuse,rail_bad,stuck_low,stuck_high;\nstatic int rail_context;')
s=s.replace('bus_active&&t==100&&tx', 'bus_active&&rail_ready&&t==100&&tx')
s=s.replace('(void)c;(void)t;*v=reset_high;return true;', '(void)c;(void)t;if(!pass())return false;*v=stuck_low?false:stuck_high?true:reset_high;return true;')
s=s.replace('static risc_hw_spi_display_v2 cfg;', '''static bool rail_enable(void *context,bool value) {
 assert(context==&rail_context && value && reset_claimed && !reset_high && !bus_active);
 if(!pass()||rail_refuse)return false;rail_ready=true;return true;
}
static bool rail_info(void *context,risc_power_rail_info_v1 *out) {
 assert(context==&rail_context && rail_ready && out->struct_size==sizeof(*out));
 if(!pass())return false;
 *out=(risc_power_rail_info_v1){.struct_size=sizeof(*out),.configured_millivolts=3300,.enabled=!rail_bad,.configuration_verified=true};return true;
}
static risc_power_rail_api_v1 rail_api={1,sizeof(rail_api),&rail_context,rail_info,rail_enable};
static risc_hw_spi_display_v2 cfg;''')
s=s.replace('{"spi.bus",1,&qs}};','{"spi.bus",1,&qs},{"power.rail",1,&rail_api}};')
s=s.replace('start(deps,4)','start(deps,5)')
s=s.replace('fail_io=io_calls=commands=quad_calls=0;', 'rail_ready=rail_refuse=rail_bad=stuck_low=stuck_high=false;diagnostics_[0]=0;fail_io=io_calls=commands=quad_calls=0;')
s=s.replace(' puts("CO5300 production', ''' setup();assert(!start(deps,4));assert(quiesce()&&!commands); /* no rail capability */
 setup();rail_refuse=true;assert(!start(deps,5));assert(quiesce()&&!commands);
 setup();rail_bad=true;assert(!start(deps,5));assert(quiesce()&&!commands);
 setup();stuck_high=true;assert(!start(deps,5));assert(quiesce()&&!commands);
 setup();stuck_low=true;assert(!start(deps,5));assert(quiesce()&&!commands);
 setup();assert(start(deps,5));assert(strstr(diagnostics_,"readback=0")&&strstr(diagnostics_,"readback=1"));assert(quiesce());
 puts("CO5300 production''')
p.write_text(s)
# Battery sharing under repeated samples + release failures. Preserve last retained-sleep case.
p=r/'tests/test_power.c';s=p.read_text()
s=s.replace('int main(void) {','''static bool release_failure;
static bool release_test(void *c,uint64_t token) {
 if(release_failure)return false;
 return bus_release_(c,token);
}
int main(void) {''')
s=s.replace('    risc_battery_sample_v1 value;','''    assert(!bus_token_);
    uint64_t rail_session=0;assert(bus_claim_(NULL,0x34,&rail_session));assert(bus_release_(NULL,rail_session));
    risc_battery_sample_v1 value;''',1)
s=s.replace('assert(value.flags&PORTABLE_POWER_STATUS_VALID);','assert(!bus_token_);assert(value.flags&PORTABLE_POWER_STATUS_VALID);',1)
needle='    setup();assert(start(deps_,4));assert(prepare_sleep(NULL));sleep_result=RISC_LIGHT_SLEEP_RETAINED;'
s=s.replace(needle,'''    setup();assert(start(deps_,4));bus_.release_device=release_test;release_failure=true;
    assert(!read_sample(NULL,&value));assert(claim&&bus_token_);assert(!quiesce());
    release_failure=false;assert(quiesce());bus_.release_device=bus_release_;no_claims_();
'''+needle)
p.write_text(s)

expected={'drivers/power_axp2101/driver.c': '020a461476b665be58f5b12310718cbf81864f7adb25ceb3ced282e2d0c35a54', 'drivers/power_axp2101/manifest.json': 'ee38e36fcb08f2afbce497036a1b6be4d12bc388161a52f84e2b8e5be0cb6575', 'drivers/panel_co5300/driver.c': 'e7ea2d9e2f248ddded1a46acddb25e9c3e9240dd4f07e321bb04161f225e248b', 'drivers/panel_co5300/manifest.json': 'b5740d726b5f49611048b9501ad78d8dcded1a9a026976c3f036235c47059f0f', 'scripts/build_drivers.py': '7674bec49b29b847f0be5c93a6436978334de1a3276b64852430fabc0399f142', 'scripts/test_drivers.py': 'af93cf6bff32eaa5353eebc035c7b15883bc4f4fa890ab46de17cf18ec6b9d7c', 'scripts/build_boot_test.py': '45919994feed97fb8db7452ddfcfc0d509ed110a675d27de54951e9d8c3e43a8', 'tests/test_panel.c': '38097d426c324c1448a00d7cd68f01b0b87a88d2ac5ae3800c3b9253984530ac', 'tests/test_power.c': 'e5e1079a9df4e8803e699e4ea3b2dd54ccde7a990ab27f664c2edd0c2277bb67'}
for name,wanted in expected.items():
    assert hashlib.sha256((r/name).read_bytes()).hexdigest()==wanted,name
(r/'provenance/display-rail-013.json').write_text(json.dumps({'schema':1,'base':'8f4a0fbc9c924cae7e887f95a113d4db1198388e','files':expected},indent=2)+'\n')
