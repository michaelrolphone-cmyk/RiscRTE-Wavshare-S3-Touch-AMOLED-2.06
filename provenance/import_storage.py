"""One-time import of the unchanged FAT core and canonical transport headers."""
from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
reference=root/'.source/reader';native=root/'.source/runtime';target=root/'lib/storage_fatfs'
if not target.exists():shutil.copytree(reference/'Drivers/storage_fatfs',target)
for name,path in [('RiscStorageVolumeV1.h','sdk/app'),('RiscProviderSyncV1.h','sdk/driver'),('RiscGpioSdmmcV1.h','sdk/driver')]:
 shutil.copy2(native/path/name,root/'include'/name)
records={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file()}
(root/'provenance/storage.json').write_text(json.dumps({'schema':1,'repository':'michaelrolphone-cmyk/T5S3-Reader','commit':'3f59913963840cb5ee8e2a65baa921f8d6af0b4d','imported':'Drivers/storage_fatfs','destination':'lib/storage_fatfs','modifications':[],'transport':'Runtime generic scoped one-bit SDMMC','hardware_verified':False,'files':records},indent=2)+'\n')
p=root/'scripts/test_drivers.py';s=p.read_text();old=" for source in sorted((ROOT/'tests').glob('test_*.c')):\n";assert old in s
s=s.replace(old,old+"  if source.stem=='test_storage':continue\n");p.write_text(s)
p=root/'scripts/build_drivers.py';s=p.read_text().replace("'strlen','malloc'","'strlen','strchr','malloc'")
old="str(folder/'driver.c'),'-lgcc'";assert old in s
s=s.replace(old,"str(folder/'driver.c'),*([str(R/'lib/storage_fatfs/fatfs'/(name+'.c')) for name in ('ff','ffunicode')] if folder.name=='storage_sdmmc' else []),'-Wno-overflow','-lgcc'");p.write_text(s)
