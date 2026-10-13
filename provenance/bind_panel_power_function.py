"""Complete explicit parent/function selection; no Runtime binding rules are bypassed."""
from pathlib import Path
import json,shutil
r=Path(__file__).resolve().parents[1]
if (r/'provenance/panel-power-function.json').exists():raise SystemExit(0)
n=r/'.source/runtime'
shutil.copy2(n/'sdk/hardware/RiscI2cFunctionV1.h',r/'include/RiscI2cFunctionV1.h')
p=r/'drivers/display_rail_axp2101/driver.c';s=p.read_text()
s=s.replace('#include "RiscPowerRailV1.h"','#include "RiscPowerRailV1.h"\n#include "RiscI2cFunctionV1.h"')
s=s.replace('static uint64_t session;','static uint64_t session;\nstatic const risc_hw_i2c_function_v1 *function;')
s=s.replace('bus->claim_device(bus->context,PMIC_ADDRESS,&session)','bus->claim_device(bus->context,function->address,&session)')
s=s.replace('    if(active || session)return false;\n    bus=tw_dep','''    if(active || session)return false;
    function=tw_config(deps,n,"x-powers,axp2101-aldo2","peripheral.i2c-function",sizeof(*function));
    if(!function || !function->parent_instance_id || function->function_id!=2 ||
       function->address!=PMIC_ADDRESS || function->chip_id!=PMIC_ID || function->reserved ||
       !tw_bus_limit(&function->bus,RISC_HW_BUS_I2C,400000))return false;
    bus=tw_dep''')
p.write_text(s)
p=r/'drivers/display_rail_axp2101/manifest.json';m=json.loads(p.read_text());m['requires'].insert(0,{'capability':'hardware.device','api':1});m['hardware_compatibility']=[{'compatible':'x-powers,axp2101-aldo2','revisions':['unspecified'],'config_type':'peripheral.i2c-function','config_version':1}];p.write_text(json.dumps(m,indent=2)+'\n')
p=r/'tests/test_rail.c';s=p.read_text().replace('static const risc_provider_dependency_v1 supply_deps[]={{"i2c.bus",1,&bus_},{"platform.clock",1,&clock_}};','''static risc_hw_i2c_function_v1 function_config;
static risc_hardware_device_v1 function_device={.api_version=1,.struct_size=sizeof(function_device),.instance_id=13,.compatible="x-powers,axp2101-aldo2",.revision="unspecified",.config_type="peripheral.i2c-function",.config_version=1,.config_size=sizeof(function_config),.config=&function_config};
static const risc_provider_dependency_v1 supply_deps[]={{"hardware.device",1,&function_device},{"i2c.bus",1,&bus_},{"platform.clock",1,&clock_}};''')
s=s.replace(' (void)deps_;(void)i2c_config_;',' (void)deps_;\n function_config=(risc_hw_i2c_function_v1){.struct_size=sizeof(function_config),.bus=i2c_config_,.parent_instance_id=4,.function_id=2,.address=0x34,.chip_id=0x4a};')
s=s.replace('start(supply_deps,2)','start(supply_deps,3)')
s=s.replace(' puts("Power rail:', ''' setup();function_config.function_id=1;assert(!start(supply_deps,3)&&!transactions_);
 setup();function_config.address=0x35;assert(!start(supply_deps,3)&&!transactions_);
 setup();assert(!start(supply_deps+1,2)&&!transactions_);
 puts("Power rail:''')
p.write_text(s)
p=r/'hardware/board.json';m=json.loads(p.read_text());panel=next(d for d in m['devices'] if d['instance_id']==5);panel['bindings']['power.rail']=13
m['devices'].append({'instance_id':13,'chip':{'vendor':'x-powers','model':'axp2101-aldo2','revision':'unspecified'},'compatible':'x-powers,axp2101-aldo2','config_type':'peripheral.i2c-function','config_version':1,'config':{'parent_instance_id':4,'function_id':2},'bindings':{'i2c.bus':2}})
p.write_text(json.dumps(m,separators=(',',':'))+'\n')
p=r/'scripts/build_boot_test.py';s=p.read_text().replace("boot['drivers'].append({'manifest':'rail/manifest.json'})","boot['drivers'].append({'manifest':'rail/manifest.json','instance_id':13})").replace("in (1,2,4,5,6,7,8,9)","in (1,2,4,5,6,7,8,9,13)")
s=s.replace('5323d1e834bdcc8e5e9fb0e8f76c383e46626801','8aae8df4f9139bea06ff43888ed628c45ed8a057');p.write_text(s)
p=r/'hardware/providers.json';j=json.loads(p.read_text());j['physical']['display_rail_axp2101']=13;p.write_text(json.dumps(j,indent=2)+'\n')
p=r/'scripts/test_board_profile.py';s=p.read_text().replace("len(p['physical'])==8","len(p['physical'])==9").replace("print('Eight provider","assert devices[5]['bindings']['power.rail']==13\nassert devices[13]['config']=={'parent_instance_id':4,'function_id':2}\nprint('Nine provider");p.write_text(s)
(r/'provenance/panel-power-function.json').write_text(json.dumps({'runtime':'8aae8df4f9139bea06ff43888ed628c45ed8a057','parent_instance_id':4,'function_instance_id':13,'function_id':2,'capability':'power.rail','physical_verified':False},indent=2)+'\n')
