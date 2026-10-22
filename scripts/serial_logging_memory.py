"""Actual linked Xtensa workspace/IQ proof; never substitute host sizeof results."""
import io
from elftools.elf.elffile import ELFFile
from package_serial_logging import require, record

SUFFIXES = {
 'serial_workspace': ('NativeSerialFiles', 'L16workspaceStorageE', '.ext_ram.bss'),
 'serial_state': ('NativeSerialFiles', 'L5stateE', '.dram0.bss'),
 'live_log_queue': ('RiscDiagnostics', 'L14liveLogStorageE', '.ext_ram.bss'),
 'diagnostic_workspace': ('RiscDiagnostics', 'L13replayStorageE', '.ext_ram.bss'),
}

def measure(raw):
    elf = ELFFile(io.BytesIO(raw))
    require(elf['e_machine']=='EM_XTENSA' and elf.elfclass==32, 'Actual 32-bit Xtensa artifact required')
    symbols = elf.get_section_by_name('.symtab')
    require(symbols is not None, 'Linked symbol evidence missing')
    rows = {}
    for label,(scope,suffix,placement) in SUFFIXES.items():
        found=[x for x in symbols.iter_symbols() if scope in x.name and x.name.endswith(suffix) and isinstance(x['st_shndx'],int)]
        require(len(found)==1,'Linked workspace identity differs: '+label)
        s=found[0];section=elf.get_section(s['st_shndx'])
        require(section.name==placement and s['st_size']>0,'Linked workspace placement differs: '+label)
        rows[label]={'symbol':s.name,'bytes':s['st_size'],'address':s['st_value'],'section':section.name}
    sections={s.name:{'bytes':s['sh_size'],'address':s['sh_addr']} for s in elf.iter_sections() if s['sh_flags']&2}
    return {'elf':record(raw),'machine':'Xtensa32','workspaces':rows,'allocated_sections':sections}

def compare(candidate,baseline,iq,baseline_iq,expected):
    require(candidate['machine']==baseline['machine']=='Xtensa32','Target machine differs')
    require(candidate['elf']['sha256']==iq['elf_sha256'] and baseline['elf']['sha256']==baseline_iq['elf_sha256'],'IQ/linked ELF custody differs')
    require(set(expected)==set(SUFFIXES),'Expected Xtensa workspace locks missing')
    for name,size in expected.items():
        require(candidate['workspaces'][name]['bytes']==size,'Actual linked target workspace differs: '+name)
        require(candidate['workspaces'][name]['section']==(baseline['workspaces'][name]['section'] if name in baseline['workspaces'] else '.ext_ram.bss'),'Workspace escaped retained placement')
    require(iq['bank_base']==baseline_iq['bank_base'] and iq['bank_bytes']==baseline_iq['bank_bytes']==65536,'Retained IQ bank changed')
    require(iq['heap_start']<=iq['bank_base'] and iq['iram_end']<=iq['iram_alias'],'Final static memory overlaps retained IQ bank')
    reservations = iq['reservation_table']
    require(isinstance(reservations, (list, tuple)) and all(isinstance(row, (list, tuple)) and len(row)==2 and all(type(value) is int for value in row) for row in reservations), 'Malformed IQ reservation table')
    require([tuple(row) for row in reservations].count((iq['bank_base'],iq['bank_base']+iq['bank_bytes']))==1,'IQ pre-heap reservation missing or duplicated')
    deltas={n:candidate['workspaces'][n]['bytes']-baseline['workspaces'].get(n,{'bytes':0})['bytes'] for n in expected}
    section_deltas={n:candidate['allocated_sections'].get(n,{'bytes':0})['bytes']-baseline['allocated_sections'].get(n,{'bytes':0})['bytes'] for n in sorted(set(candidate['allocated_sections'])|set(baseline['allocated_sections']))}
    return {'schema':1,'actual_linked_xtensa':True,'candidate':candidate,'baseline':baseline,
            'workspace_deltas':deltas,'section_byte_deltas':section_deltas,
            'iq_bank_base':iq['bank_base'],'iq_bank_bytes':iq['bank_bytes'],
            'internal_gap_before_iq':iq['bank_base']-iq['heap_start'],
            'baseline_internal_gap_before_iq':baseline_iq['bank_base']-baseline_iq['heap_start'],
            'iram_gap_before_alias':iq['iram_alias']-iq['iram_end'],
            'target_instructions_executed':False,'hardware_tested':False,
            'scope':'Final linked static placement and IQ reservation; not physical heap availability or device acceptance'}
