"""Provision the shared Home's existing native retained-wake API explicitly.

This changes product metadata only. The shared application keeps its cold-start
fallback for deployments that intentionally omit retained-wake provisioning.
"""
from copy import deepcopy

CAPABILITY = "runtime.retained-wake"
REQUIREMENT = {"capability": CAPABILITY, "api": 1}
GRANT = {"capability": CAPABILITY, "api": 1, "instance_id": 0}


def provision(manifest, policy):
    """Return copies with the exact v1 Home requirement and instance-0 grant.

    Reject conflicting existing authority instead of silently rewriting it.
    No unrelated requirement, optional capability, grant, or product field is
    removed or changed. Existing complete provisioning is idempotent.
    """
    if (manifest.get("type") != "application" or
            manifest.get("id") != "twatch-clock" or
            manifest.get("file_name") != "default.elf" or
            policy.get("manifest") != "default.json"):
        raise ValueError("Expected the shared default Home and its exact policy")
    result, authority = deepcopy(manifest), deepcopy(policy)
    required = result.get("requires")
    grants = authority.get("grants")
    if not isinstance(required, list) or not isinstance(grants, list):
        raise ValueError("Malformed Home requirements or grants")
    existing = [x for x in required if x.get("capability") == CAPABILITY]
    optional = [x for x in result.get("optional", []) if x.get("capability") == CAPABILITY]
    current = [x for x in grants if x.get("capability") == CAPABILITY]
    if (existing not in ([], [REQUIREMENT]) or optional or
            current not in ([], [GRANT])):
        raise ValueError("Conflicting or duplicate retained-wake authority")
    if not existing:
        required.append(deepcopy(REQUIREMENT))
    if not current:
        grants.append(deepcopy(GRANT))
    if len(required) + len(result.get("optional", [])) > 32 or len(grants) > 32:
        raise ValueError("Home capability policy exceeds the selected native bounds")
    return result, authority
