from pathlib import Path
import sys
r=Path(sys.argv[1]);o=Path(sys.argv[2]);o.mkdir(exist_ok=True,parents=True)
s=(r/'test/native_sd_port_test.cpp').read_text().replace('pin==5','pin==17').replace('c==41&&m==42&&d==40','c==2&&m==1&&d==3')
(o/'native_sd_port_test.cpp').write_text(s)
s=(r/'test/native_settings_maintenance_test.cpp').read_text().replace('},9);','},12);').replace('},9,writers,2,bootstrapClient);','},12,writers,2,bootstrapClient);').replace('Pin anchor(runtime,cpu,9)','Pin anchor(runtime,cpu,12)').replace('P fresh(runtime,cpu,1,9)','P fresh(runtime,cpu,1,12)')
(o/'maintenance.cpp').write_text(s)
