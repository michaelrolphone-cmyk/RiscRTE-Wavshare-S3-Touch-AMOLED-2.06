"""Exact split admission plus a new unauthorized namespace negative control."""
import copy
import json
from package_minimal_sd import require, encoded

def factory_admission(run_cohort,before,after,elf_count,store_digest):
    require(elf_count==43,'Expected internal ELF inventory differs')
    transition=run_cohort(before,after,True)
    require(transition['prepared'] and transition['cohort_validated'] and transition['elf_count']==43,
            'Placement-only transition admission failed')
    boot=json.loads(after['boot.json']);grant={'capability':'storage.key-value','api':1,'instance_id':6}
    owner=next(r for r in boot['app_capabilities'] if r['manifest']=='default.json')
    borrower=next(r for r in boot['app_capabilities'] if r['manifest']=='calculator.json')
    require(grant in owner['grants'] and grant not in borrower['grants'],'Namespace negative-control precondition differs')
    borrower['grants'].append(grant)
    negative=run_cohort(before,dict(after,**{'boot.json':encoded(boot)}),False)
    require(negative['prepared'] and not negative['cohort_validated'] and negative['elf_count']==0 and
            not negative['hardware_calls'] and not negative['storage_calls'],'Unauthorized namespace control admitted')
    result=run_cohort(after,after,True)
    require(result['prepared'] and result['cohort_validated'] and result['elf_count']==43 and
            result['active_store_sha256']==result['candidate_store_sha256']==store_digest(after) and
            not result['hardware_calls'] and not result['storage_calls'],'Factory self-admission differs')
    result.update(mode='factory-bootstrap-self-admission',placement_transition=transition,
                  unauthorized_namespace_control=dict(negative,expected_rejection=True,control_packaged=False),
                  preserving_update_kit_emitted=False)
    return result
