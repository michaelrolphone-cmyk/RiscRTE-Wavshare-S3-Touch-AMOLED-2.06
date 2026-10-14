"""Explicit shared Contexts storage grants for the Spectrum watch build.

The full CFP1 service suffix loads Audio@2, RF@3 and rules@4 during startup.
These grants are application policy, not implicit Runtime privileges.
"""
import copy

def provision(manifest, policy):
    manifest, policy = copy.deepcopy(manifest), copy.deepcopy(policy)
    if manifest.get('id') != 'audio_spectrum':
        return manifest, policy
    if not any(r['capability'] == 'contexts.service' for r in manifest['requires']):
        return manifest, policy
    declaration = {'capability': 'storage.shared-data', 'api': 1}
    if declaration not in manifest['requires']:
        manifest['requires'].append(declaration)
    for namespace in (2, 3, 4):
        grant = {**declaration, 'instance_id': namespace}
        if grant not in policy['grants']:
            policy['grants'].append(grant)
    if len(policy['grants']) > 32:
        raise ValueError('Spectrum policy exceeds deployed Runtime capacity')
    return manifest, policy
