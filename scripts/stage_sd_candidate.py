#!/usr/bin/env python3
"""Add the existing generic SD volume, preserving every app and prior grant."""
from pathlib import Path
import argparse,json,shutil,sys
p=argparse.ArgumentParser()
for n in ('store','providers','home','output','compactor','cc'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
assert not a.output.exists();shutil.copytree(a.store,a.output);(a.output/'cohort.json').unlink()
boot=json.loads((a.output/'boot.json').read_text());board=json.loads((a.output/'board.json').read_text());full=json.loads((root/'hardware/board.json').read_text())
assert not any(d['instance_id']==12 for d in board['devices']);board['devices'].append(next(d for d in full['devices'] if d['instance_id']==12))
shutil.copytree(a.providers/'storage_sdmmc',a.output/'sd-volume',ignore=shutil.ignore_patterns('exports.map'))
boot['drivers'].append({'manifest':'sd-volume/manifest.json','instance_id':12})
# Expose the generic volume independently of file.open. Existing app-data and
# installed-files authorities are preserved. UI/handoff changes are separate.
for name in ('file_browser.json','model_viewer.json'):
 m=json.loads((a.output/name).read_text());r={'capability':'storage.volume','api':1};g={**r,'instance_id':12}
 if r not in m['requires']:m['requires'].append(r)
 row=next(x for x in boot['app_capabilities'] if x['manifest']==name)
 if g not in row['grants']:row['grants'].append(g)
 (a.output/name).write_text(json.dumps(m,separators=(',',':'))+'\n')
(a.output/'boot.json').write_text(json.dumps(boot,separators=(',',':'))+'\n');(a.output/'board.json').write_text(json.dumps(board,separators=(',',':'))+'\n')
shutil.copy2(a.home/'default.elf',a.output/'default.elf')
assert (a.home/'clock.elf').read_bytes()==(a.output/'clock.elf').read_bytes()
# Preserve JSON values exactly while reclaiming whitespace, never ELF features.
for f in a.output.rglob('*.json'):
 value=json.loads(f.read_text());f.write_text(json.dumps(value,separators=(',',':'))+'\n');assert json.loads(f.read_text())==value
sys.path.insert(0,str(a.compactor.resolve()))
from compact_current_elf import compact
proof=compact(a.output/'contexts.elf',str(a.cc),debug_path=a.output.parent/'contexts-original.elf')
assert proof['retained_loader_sections_symbols_relocations_unchanged']
(a.output.parent/'contexts-compaction.json').write_text(json.dumps(proof,indent=2)+'\n')
old=json.loads((a.store/'boot.json').read_text())
for row in old['app_capabilities']:
 current=next(x for x in boot['app_capabilities'] if x['manifest']==row['manifest']);assert all(g in current['grants'] for g in row['grants'])
print('SD instance12 added; existing25apps and all grants retained; Home replaced; Contexts loader semantics preserved by metadata compaction; JSON whitespace compacted')
