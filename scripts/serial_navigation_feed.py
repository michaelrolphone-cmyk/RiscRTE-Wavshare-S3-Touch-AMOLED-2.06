#!/usr/bin/env python3
"""Build the .62 core feed and bind its controller proof to actual firmware bytes.

Production selection/queueing executes on the host. Native status, HTTP, prior
store state, and queue persistence are modeled; this does not execute target
instructions, install a store, or establish physical-device acceptance.
"""
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import tempfile

from package_minimal_sd import require, record, encoded

DOCS = Path(__file__).resolve().parents[1] / 'docs/serial-navigation-recovery'
BASELINE_FEED = DOCS / 'baseline-core-feed.json'
BASELINE_RECORD = {'bytes': 11462, 'sha256': 'a5f55456437515b20d49740b631fd9713b06dbdfdbeada7ee05e2d07c5c8529a'}
NATIVE_KEYS = {'layout', 'runtime_version', 'store_abi', 'firmware_size', 'firmware_sha256'}
NEGATIVE_CASES = ('released-0.1.61-feed', 'runtime-version', 'firmware-size',
                  'firmware-sha256', 'store-abi', 'layout')


def compiled_value(firmware, prefix):
    """Ignore empty parser literals; reject missing, conflicting or truncated IDs."""
    values = set()
    for match in re.finditer(re.escape(prefix), firmware):
        start = match.end()
        if firmware[start:start + 1] == b'\0':
            continue
        end = firmware.find(b'\0', start)
        require(end >= start and end - start < 32, 'Missing or truncated native marker')
        values.add(firmware[start:end])
    require(len(values) == 1, 'Missing or ambiguous native identity marker')
    try:
        return values.pop().decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('Non-ASCII native identity marker') from error


def actual_native_identity(firmware, cohort, p):
    """Derive size/hash/version/ABI from firmware, never from the feed under test."""
    require(isinstance(firmware, bytes) and 32 <= len(firmware) <= 0x260000,
            'Bounded native firmware bytes required')
    version = compiled_value(firmware, b'RISC_RUNTIME_VERSION:')
    abi = compiled_value(firmware, b'RISC_PAIRED_STORE_ABI:')
    require(re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version)
            and all(int(part) <= 0xffffffff for part in version.split('.')),
            'Native runtime version is malformed')
    require(abi == '3', 'Navigation product must retain paired store ABI 3')
    identity = dict(layout='riscrte-paired-appdata-v3', runtime_version=version,
                    store_abi=3, firmware_size=len(firmware),
                    firmware_sha256=record(firmware)['sha256'])
    require(isinstance(cohort, dict) and cohort.get('product') == p['feed_product']
            and cohort.get('version') == p['version'], 'Product cohort identity differs')
    require({key: cohort.get(key) for key in NATIVE_KEYS} == identity,
            'Cohort differs from actual native firmware bytes')
    return identity


def prepare(sources, files, image, firmware, p, output):
    system, runtime = sources['system'], sources['runtime']
    require(p['version'] == '0.1.62' and p['release_tag'] == 'test-sd-apps-0.1.62'
            and p['feed_url'] == ('https://raw.githubusercontent.com/michaelrolphone-cmyk/'
                'RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/provisioning-index/0.1.62/native-packages-v1.json'),
            'Navigation provider must select its own exact-native feed')
    identity = actual_native_identity(firmware, json.loads(files['cohort.json']), p)
    path = system / 'scripts/build_boot_profile_feed.py'
    spec = importlib.util.spec_from_file_location('lifetime_boot_feed', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = ('https://github.com/michaelrolphone-cmyk/'
            'RiscRTE-Wavshare-S3-Touch-AMOLED-2.06/releases/download/' + p['release_tag'] + '/')
    with tempfile.TemporaryDirectory(prefix='wave-lifetime-feed-inputs-') as tmp:
        root = Path(tmp)
        store = root / 'store'
        store.mkdir()
        for name, data in files.items():
            target = store / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (root / 'store.bin').write_bytes(image)
        (root / 'firmware.bin').write_bytes(firmware)
        receipt = module.build(runtime, store, root / 'store.bin', root / 'firmware.bin',
                               base, p['feed_product'], 'core', [p['time_server']], output)
    feed_path = output / 'native-packages-v1.json'
    feed = json.loads(feed_path.read_bytes())
    core = feed['boot_profiles']['core']
    require(core['native'] == identity, 'Feed is not bound to actual native firmware')
    require(len(core['profile']['files']) == 111 and not core['mirrors'],
            'Complete internal-only core inventory required')
    require(receipt['file_count'] == 111 and receipt['credential_free'],
            'Feed bounds/credential contract differs')
    require(feed['apps'] == [] and feed['profiles'] == {'core': []},
            'Unrequested dynamic package scope')
    proof = exercise_controller(system, runtime, feed_path, p, identity, image)
    proof['cohort_sha256'] = record(files['cohort.json'])['sha256']
    (output / 'controller-proof.json').write_bytes(encoded(proof))
    return {'receipt': receipt, 'controller': proof, 'core_inventory_files': 111,
            'core_inventory_elfs': 43, 'dynamic_app_descriptors': 0, 'hardware_tested': False}


def exercise_controller(system, runtime, feed, p, identity, image):
    """Seed modeled native status only from independently measured build inputs."""
    require(set(identity) == NATIVE_KEYS, 'Complete actual native identity required')
    baseline = BASELINE_FEED.read_bytes()
    require(record(baseline) == BASELINE_RECORD, 'Released .61 feed custody differs')
    old = json.loads(baseline)['boot_profiles']['core']['native']
    require(identity != old and identity['firmware_sha256'] != old['firmware_sha256'],
            'Successor must have a distinct actual native firmware identity')
    actual_feed = json.loads(feed.read_bytes())
    core = actual_feed['boot_profiles']['core']
    require(core['native'] == identity, 'Controller feed/native identity differs')
    require(core['profile']['image']['bytes'] == len(image)
            and core['profile']['image']['sha256'] == record(image)['sha256'],
            'Controller target image differs from actual packed store')
    fixture = system / 'test/native_apps/installed_apps_boot_profile_test.cpp'
    original = fixture.read_text()
    require(original.count('int main(){') == 1, 'Controller fixture entry changed')
    source = original[:original.index('int main(){')]
    for anchor in ('static risc_provision_request_status_v1 requestStatus;',
                   '++queueCalls;assert(', 't["servers"][0]=="time.example.org"'):
        require(source.count(anchor) == 1, 'Controller fixture source anchor changed')
    source = source.replace('static risc_provision_request_status_v1 requestStatus;',
        'static std::string queuedProfile;\nstatic risc_provision_request_status_v1 requestStatus;')
    source = source.replace('++queueCalls;assert(',
        'queuedProfile.assign(static_cast<const char*>(q->profile_json),q->profile_size);++queueCalls;assert(', 1)
    source = source.replace('t["servers"][0]=="time.example.org"',
                            't["servers"][0]==' + json.dumps(p['time_server']))
    source += r'''
static std::string loadFile(const char*path){
 std::ifstream input(path,std::ios::binary);assert(input);
 return std::string(std::istreambuf_iterator<char>(input),{});
}
static void actualStatus(JsonVariantConst native,JsonVariantConst active,bool current){
 statusReset();requestStatus.store_abi=native["store_abi"].as<uint32_t>();
 requestStatus.firmware_size=native["firmware_size"].as<uint32_t>();
 assert(copy(requestStatus.layout,sizeof(requestStatus.layout),native["layout"]));
 assert(copy(requestStatus.runtime_version,sizeof(requestStatus.runtime_version),native["runtime_version"]));
 assert(bootDigest(native["firmware_sha256"],requestStatus.firmware_sha256));
 assert(bootDigest(active,requestStatus.active_store_sha256));
 // A different active store is modeled only for the queue positive. Exact
 // delivered image identity is used by the already-active no-op case.
 if(!current)requestStatus.active_store_sha256[0]^=1;
 queueCalls=0;queuedProfile.clear();queueResult=statusResult=0;
}
static void rejectFeed(const char*label){
 beginCore();assert(driveCore(nullptr)==INSTALLED_APPS_INVALID);
 assert(!bootSelected&&!bootQueued&&!bootWaitingWifi&&queueCalls==0);
 assert(bootApi.supply_wifi(nullptr,"saved default","saved-password")==INSTALLED_APPS_INVALID);
 assert(queueCalls==0&&queuedProfile.empty());closeCore();assert(!feedOpen);
 printf("PASS %s queue_calls=0\n",label);
}
int main(int argc,char**argv){
 assert(argc==4);staged_fixture::setup();staged_fixture::begin();assert(api.refresh(nullptr)==0);
 const auto candidateBody=loadFile(argv[1]);const auto oldBody=loadFile(argv[2]);
 JsonDocument measured;assert(!deserializeJson(measured,loadFile(argv[3])));
 const auto actual=measured["native"].as<JsonVariantConst>();
 const auto active=measured["active_store_sha256"].as<JsonVariantConst>();
 JsonDocument document;assert(!deserializeJson(document,candidateBody));
 const auto core=document["boot_profiles"]["core"];
 assert(core["native"]==actual);
 assert(core["profile"]["image"]["sha256"]==active);
 feedBody=oldBody;assert(parseBody());actualStatus(actual,active,false);
 rejectFeed("released-0.1.61-feed");
 feedBody=candidateBody;assert(parseBody());
 for(unsigned mutation=0;mutation<5;++mutation){
  actualStatus(actual,active,false);const char*label=nullptr;
  if(mutation==0){label="runtime-version";requestStatus.runtime_version[0]=requestStatus.runtime_version[0]=='9'?'8':'9';}
  if(mutation==1){label="firmware-size";++requestStatus.firmware_size;}
  if(mutation==2){label="firmware-sha256";requestStatus.firmware_sha256[0]^=1;}
  if(mutation==3){label="store-abi";++requestStatus.store_abi;}
  if(mutation==4){label="layout";requestStatus.layout[0]^=1;}
  rejectFeed(label);
 }
 actualStatus(actual,active,true);beginCore();assert(driveCore(nullptr)==INSTALLED_APPS_OK);
 assert(queueCalls==0&&queuedProfile.empty());closeCore();assert(!feedOpen);
 puts("PASS already-active-store queue_calls=0");
 actualStatus(actual,active,false);beginCore();assert(driveCore(nullptr)==INSTALLED_APPS_NEEDS_PROFILE_WIFI);
 assert(bootApi.supply_wifi(nullptr,"saved default","saved-password")==INSTALLED_APPS_PROFILE_QUEUED);
 assert(queueCalls==1);JsonDocument queued;assert(!deserializeJson(queued,queuedProfile));
 const auto expected=core["profile"];
 assert(queued["files"].size()==111&&queued["files"]==expected["files"]&&queued["image"]==expected["image"]);
 assert(requestStatus.state==RISC_PROVISION_REQUEST_PENDING);uint8_t target[32];
 assert(bootDigest(expected["image"]["sha256"],target));assert(!memcmp(target,requestStatus.target_store_sha256,32));
 assert(driveCore(nullptr)==INSTALLED_APPS_PROFILE_QUEUED&&queueCalls==1);
 closeCore();assert(!feedOpen);puts("PASS actual-native-feed queue_calls=1");
}
'''
    measured = {'native': identity, 'active_store_sha256': record(image)['sha256']}
    expected = ['PASS ' + name + ' queue_calls=0' for name in NEGATIVE_CASES]
    expected += ['PASS already-active-store queue_calls=0', 'PASS actual-native-feed queue_calls=1']
    with tempfile.TemporaryDirectory(prefix='wave-lifetime-controller-') as tmp:
        root = Path(tmp)
        (root / 'controller.cpp').write_text(source)
        (root / 'actual-native.json').write_bytes(encoded(measured))
        includes = [runtime / name for name in ('src', 'sdk/app', 'sdk/driver', 'sdk/hardware', 'lib/ArduinoJson/src')]
        includes += [system / name for name in ('lib/PortableApps/include', 'lib/InstalledCatalog/include', 'test/native_apps')]
        inc = ['-I' + str(path) for path in includes]
        commands = [
            ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', *inc, '-c',
             str(system / 'lib/InstalledCatalog/src/InstalledCatalog.c'), '-o', str(root / 'catalog.o')],
            ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
             '-DINSTALLED_APPS_FEED_PRODUCT="' + p['feed_product'] + '"', *inc,
             str(root / 'controller.cpp'), str(runtime / 'src/runtime/storage/PackageFiles.cpp'),
             str(root / 'catalog.o'), '-o', str(root / 'controller')]]
        for command in commands:
            subprocess.run(command, check=True)
        result = subprocess.run([str(root / 'controller'), str(feed), str(BASELINE_FEED),
                                 str(root / 'actual-native.json')],
                                check=True, capture_output=True, text=True)
        require(result.stdout.splitlines() == expected and not result.stderr,
                'Actual-native controller observation matrix differs')
    return {'production_feed_sha256': record(feed.read_bytes())['sha256'],
            'fixture_sha256': record(source.encode())['sha256'],
            'files_selected': 111, 'queue_calls': 1,
            'exact_image_url_size_digest_selected': True,
            'native_firmware_identity_matched': True,
            'actual_native_bound': True,
            'native_identity_source': 'firmware-binary-markers-size-and-sha256',
            'actual_native_identity': identity,
            'actual_native_status_sha256': record(encoded(measured))['sha256'],
            'actual_store_sha256': record(image)['sha256'],
            'baseline_feed': BASELINE_RECORD,
            'baseline_feed_rejected_without_queue': True,
            'independent_native_mismatch_rejections': list(NEGATIVE_CASES[1:]),
            'negative_case_count': len(NEGATIVE_CASES),
            'negative_queue_calls': 0,
            'already_active_store_noop': True, 'already_active_queue_calls': 0,
            'matching_pending_no_duplicate_queue': True,
            'queue_positive_prior_store_is_modeled': True,
            'hardware_tested': False, 'target_instructions_executed': False,
            'result': result.stdout.strip()}


def self_test():
    """Fast identity-parser rejection tests; these bytes are not firmware evidence."""
    p = {'version': '0.1.62', 'feed_product': 'waveshare-s3-touch-amoled-206'}
    firmware = (b'synthetic-marker-test-only\0RISC_RUNTIME_VERSION:\0'
                b'RISC_RUNTIME_VERSION:0.4.14\0RISC_PAIRED_STORE_ABI:3\0')
    cohort = dict(product=p['feed_product'], version=p['version'],
                  layout='riscrte-paired-appdata-v3', runtime_version='0.4.14',
                  store_abi=3, firmware_size=len(firmware),
                  firmware_sha256=record(firmware)['sha256'])
    identity = actual_native_identity(firmware, cohort, p)
    require(identity['firmware_sha256'] == record(firmware)['sha256'], 'Positive identity test failed')
    cases = [
        ('cohort-sha256', firmware, dict(cohort, firmware_sha256='0' * 64)),
        ('cohort-size', firmware, dict(cohort, firmware_size=len(firmware) + 1)),
        ('cohort-runtime-version', firmware, dict(cohort, runtime_version='0.4.13')),
        ('cohort-layout', firmware, dict(cohort, layout='foreign')),
        ('cohort-abi', firmware, dict(cohort, store_abi=2)),
        ('cohort-product', firmware, dict(cohort, product='foreign')),
        ('cohort-release', firmware, dict(cohort, version='0.1.61')),
        ('conflicting-marker', firmware + b'RISC_RUNTIME_VERSION:0.4.15\0', cohort),
        ('truncated-marker', firmware + b'RISC_RUNTIME_VERSION:0.4.14', cohort),
        ('missing-marker', firmware.replace(b'RISC_RUNTIME_VERSION:', b'XISC_RUNTIME_VERSION:'), cohort),
        ('malformed-version', firmware.replace(b'0.4.14', b'0.4.x4'), cohort),
        ('changed-native-abi', firmware.replace(b'STORE_ABI:3', b'STORE_ABI:2'), cohort),
    ]
    rejected = []
    for label, raw, candidate in cases:
        try:
            actual_native_identity(raw, candidate, p)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError('Accepted invalid actual-native identity: ' + label)
    require(record(BASELINE_FEED.read_bytes()) == BASELINE_RECORD, 'Baseline fixture custody differs')
    return {'status': 'passed', 'positive_cases': 1, 'rejection_count': len(rejected),
            'rejections': rejected, 'hardware_tested': False,
            'scope': 'Synthetic marker parser tests only; no native release qualification'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', required=True)
    parser.parse_args()
    require(__debug__, 'Controller assertions cannot be disabled')
    print(json.dumps(self_test(), indent=2, sort_keys=True))
