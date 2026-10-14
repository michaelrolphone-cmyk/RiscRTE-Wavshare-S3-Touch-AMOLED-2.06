from pathlib import Path
import json,subprocess,sys
root=Path.cwd();sys.path.insert(0,str(root/'Shared-t023/scripts'))
from compact_current_elf import compact
from normalize_xtensa_relocations import normalize
for device,volume in [('wave',12)]:
 out=root/'wave-custody-build/springboard';out.mkdir(exist_ok=True)
 c=json.loads((root/f't054-build/{device}-components/springboard-command.json').read_text())
 c=[x.replace(str(root/'System-rgb-t054'),str(root/'System-wave-custody')) for x in c];c[c.index('-o')+1]=str(out/'springboard.elf')
 mapping=out/'exports.map';mapping.write_text('{global: app_main; app_module_init; app_module_fini;local:*;};\n')
 c=[('-Wl,--version-script='+str(mapping)) if x.startswith('-Wl,--version-script=') else x for x in c]
 (out/'command.json').write_text(json.dumps(c,indent=2)+'\n')
 with (out/'target.log').open('w') as log:subprocess.run(c,check=True,stdout=log,stderr=subprocess.STDOUT)
 normalize(out/'springboard.elf');compact(out/'springboard.elf',c[0],debug_path=out/'springboard.debug.elf')
 subprocess.run([str(root/'t023-build/wave-home-compressed-final/validate-elf'),str(out/'springboard.elf')],check=True)
 m=json.loads((root/f't064-build/{device}/store/springboard.json').read_text());m['version']='1.7.15'
 (out/'springboard.json').write_text(json.dumps(m,indent=2)+'\n');print(device,(out/'springboard.elf').stat().st_size)
