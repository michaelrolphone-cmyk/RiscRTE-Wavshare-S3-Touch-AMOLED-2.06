"""One-time readable migration. The workflow commits the resulting C/header sources."""
from pathlib import Path
import json,shutil
D=Path(__file__).resolve().parents[1];R=D/'.source/runtime'
if 'quad->exchange_frame' in (D/'drivers/panel_co5300/driver.c').read_text():raise SystemExit(0)
for h in ['RiscSpiFrameV1.h','RiscSpiQuadV1.h']:shutil.copy2(R/'sdk/driver'/h,D/'include'/h)
p=D/'drivers/panel_co5300/driver.c';s=p.read_text()
a=s.index('    /* Match the vendor\'s command+address');b=s.index('\nstatic bool set_byte',a)
s=s[:a]+'''    /* Keep header and register parameters in one hardware SPI transaction,
     * using the framed path corresponding to the successful vendor A/B test. */
    if(n>4 || (n&&!data) || !begin_bus())return false;
    const risc_spi_frame_v1 frame={sizeof(frame),0x02,8,24,(uint64_t)cmd<<8,0,1,0};
    bool ok=quad->exchange_frame(spi->context,spi_claim,&frame,data,n);
    bool ended=end_bus();return ok&&ended;
}'''+s[b:]
s=s.replace('!quad->claim_quad||!quad->exchange_quad','!quad->claim_quad||!quad->exchange_frame')
s=s.replace('!spi->begin||!spi->exchange||!spi->end||!spi->release','!spi->begin||!spi->end||!spi->release')
s=s.replace('    rail=tw_dep(d,n,RISC_POWER_RAIL_CAPABILITY,sizeof(*rail));','    provider_log("PANEL_LINK transport=framed-spi header=hardware-command-address completion=polling");\n    rail=tw_dep(d,n,RISC_POWER_RAIL_CAPABILITY,sizeof(*rail));')
s=s.replace('    if(ok){const uint8_t header[]={0x32,0,0x3c,0};ok=spi->exchange(spi->context,spi_claim,header,NULL,sizeof(header));}\n','')
s=s.replace('        ok=quad->exchange_quad(spi->context,spi_claim,wire,count);','''        const risc_spi_frame_v1 frame={sizeof(frame),offset?0:0x32,offset?0:8,
            offset?0:24,offset?0:0x3c00,0,4,0};
        ok=quad->exchange_frame(spi->context,spi_claim,&frame,wire,count);''')
p.write_text(s)
p=D/'drivers/panel_co5300/manifest.json';m=json.loads(p.read_text());m['version']='0.1.3';m['notes']='Requires spi.bus@1 with RISC_SPI_QUAD_FRAME_V1_SIZE';p.write_text(json.dumps(m,indent=2)+'\n')
p=D/'tests/test_panel.c';s=p.read_text();idx=s.index('static bool endq(')
s=s[:idx]+'''static bool frameq(void*c,uint64_t t,const risc_spi_frame_v1*f,const uint8_t*data,size_t n) {
 assert(f && f->struct_size==sizeof(*f) && !f->reserved && !f->dummy_bits);
 if(f->command_bits || f->address_bits) {
  assert(f->command_bits==8 && f->address_bits==24 && !(f->address&0xff00ff));
  if(f->command==2) {
   assert(f->data_lines==1 && n<=4 && (!n || data));
   uint8_t bytes[8]={2,0,(uint8_t)(f->address>>8),0};if(n)memcpy(bytes+4,data,n);
   return exchange(c,t,bytes,NULL,n+4);
  }
  assert(f->command==0x32 && f->data_lines==4 && n==512 && !received);
  const uint8_t bytes[]={0x32,0,0x3c,0};assert(f->address==0x3c00);
  if(!exchange(c,t,bytes,NULL,4))return false;
 } else {assert(!f->command && !f->address && f->data_lines==4 && received==512 && n==308);}
 return pixelsq(c,t,data,n);
}
'''+s[idx:]
s=s.replace('.exchange=exchange,','').replace('.exchange_quad=pixelsq','.exchange_frame=frameq')
s=s.replace(' setup();cfg.data3=cfg.data2;', ''' setup();qs.base.struct_size=RISC_SPI_QUAD_RAW_V1_SIZE;assert(!start(deps,5));assert(quiesce()&&!commands);qs.base.struct_size=sizeof(qs);
 setup();qs.exchange_frame=NULL;assert(!start(deps,5));assert(quiesce()&&!commands);qs.exchange_frame=frameq;
 setup();cfg.data3=cfg.data2;''')
p.write_text(s)
for name in ['scripts/test_drivers.py','scripts/build_drivers.py']:
 p=D/name;s=p.read_text();s=s.replace("(a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include',ROOT/'include')", "(ROOT/'include',a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include')").replace("(w/'sdk/driver',w/'sdk/app',w/'include',R/'include')","(R/'include',w/'sdk/driver',w/'sdk/app',w/'include')");p.write_text(s)
p=D/'scripts/build_boot_test.py';s=p.read_text().replace("[S/'sdk/driver',S/'sdk/app',S/'include',device/'include']","[device/'include',S/'sdk/driver',S/'sdk/app',S/'include']").replace('0.1.3','0.1.4');p.write_text(s)
p=D/'scripts/validate_boot_test.py';s=p.read_text();needle='  h.spiOpenQuad=[](uint8_t,int16_t,int16_t,int16_t,int16_t,int16_t){++hardwareCalls;return false;};'
assert needle in s;s=s.replace(needle,needle+'\n  h.spiTransferFrame=[](uint8_t,const risc_spi_frame_v1*,const uint8_t*,size_t,uint32_t){++hardwareCalls;return false;};');p.write_text(s)
for name in ['scripts/build_boot_test.py','hardware/providers.json']:
 p=D/name;s=p.read_text();assert '8aae8df4f9139bea06ff43888ed628c45ed8a057' in s;p.write_text(s.replace('8aae8df4f9139bea06ff43888ed628c45ed8a057','97336e63ce1eac40364893e0ddf5b9fe61b648b7'))
