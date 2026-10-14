"""Optional checked compaction of explicit new providers and rebuilt app copies."""
import hashlib
import importlib
import json
import os
from pathlib import Path

PROVIDERS = ('installed-apps/driver.elf', 'pkg-internal/driver.elf')
REBUILT_APPS = ('default.elf', 'springboard.elf')


def prepare(product, compiler, debug_dir, report, output, inputs, images=PROVIDERS):
    """Reject missing inputs and output aliases before composing or running tools."""
    if compiler is None or debug_dir is None or report is None:
        raise ValueError('Checked compaction requires --compiler, --debug-sidecar-dir and --composition-report')
    if not images or len(set(images)) != len(images) or not set(images) <= set(PROVIDERS + REBUILT_APPS):
        raise ValueError('Compaction is limited to explicit new providers and rebuilt Home/Springboard')
    compiler = Path(compiler).absolute()
    if not compiler.name.endswith('gcc'):
        raise ValueError('--compiler must name the gcc executable used for the provider toolchain')
    objcopy = compiler.with_name(compiler.name[:-3] + 'objcopy')
    if not all(path.is_file() and os.access(path, os.X_OK) for path in [compiler, objcopy]):
        raise ValueError('Caller compiler and matching objcopy must exist and be executable')
    output, debug_dir, report = map(lambda p: Path(p).resolve(), [output, debug_dir, report])
    roots = [Path(path).resolve() for path in inputs]
    if debug_dir.is_relative_to(output) or output.is_relative_to(debug_dir):
        raise ValueError('Debug sidecar directory must be outside and separate from the store')
    if any(debug_dir.is_relative_to(root) or root.is_relative_to(debug_dir) for root in roots):
        raise ValueError('Debug sidecar directory must not overlap an input tree')
    if report.is_relative_to(output) or any(report.is_relative_to(root) for root in roots):
        raise ValueError('Compaction report must be outside the store and input trees')
    if debug_dir.exists() and not debug_dir.is_dir():
        raise ValueError('Debug sidecar output must be a directory')
    for relative in images:
        sidecar = debug_dir / relative
        if not sidecar.resolve().is_relative_to(debug_dir):
            raise ValueError('Debug sidecar path escapes its output directory')
        if sidecar.parent.exists() and not sidecar.parent.is_dir():
            raise ValueError('Debug sidecar parent must be a directory')
        if sidecar.exists() or sidecar.is_symlink():
            raise ValueError('Refuse to overwrite an existing debug sidecar: ' + str(sidecar))
        if report == sidecar.resolve():
            raise ValueError('Compaction report aliases a debug sidecar')
    module_name = 'compact_cohort_elf' if product == 'wave' else 'compact_current_elf'
    # Import the existing reviewed checker unchanged, only when explicitly used.
    module = importlib.import_module(module_name)
    return {'compiler': compiler, 'debug_dir': debug_dir, 'module': module, 'images': tuple(images)}


def validate_rebuilt_apps(baseline, home, springboard):
    """Bind only replacement inputs to their original build receipts before copying."""
    baseline = Path(baseline).resolve()
    receipts = {}
    for relative, folder in zip(REBUILT_APPS, [home, springboard]):
        folder = Path(folder).resolve()
        if folder.is_relative_to(baseline) or baseline.is_relative_to(folder):
            raise ValueError('Rebuilt app compaction inputs must be separate from the baseline')
        image = folder / relative
        if image.is_symlink():
            raise ValueError('Rebuilt app compaction input must not be a symlink')
        receipt_path = folder / 'build.json'
        if not receipt_path.is_file():
            raise ValueError('Rebuilt app compaction requires the original build receipt: ' + relative)
        receipt = json.loads(receipt_path.read_text())
        artifact = receipt.get('artifacts', {}).get('default', {}) if relative == 'default.elf' else receipt
        data = image.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if artifact.get('sha256') != digest or artifact.get('bytes') != len(data):
            raise ValueError('Rebuilt app ELF does not match its original build receipt: ' + relative)
        receipts[relative] = {'elf_sha256': digest, 'elf_bytes': len(data),
                              'build_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    return receipts


def semantic_record(value):
    """Keep every semantic field; represent raw section/segment bytes by hashes."""
    if isinstance(value, bytes):
        return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
    if isinstance(value, dict):
        return {key: semantic_record(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [semantic_record(child) for child in value]
    return value


def compact_images(output, plan):
    module = plan['module']
    proofs = {}
    for relative in plan['images']:
        path, sidecar = Path(output) / relative, plan['debug_dir'] / relative
        if sidecar.exists() or sidecar.is_symlink():
            raise ValueError('Debug sidecar appeared after preflight: ' + str(sidecar))
        original = path.read_bytes()
        expected = module.evidence(original)
        proof = module.compact(path, plan['compiler'], debug_path=sidecar)
        actual = module.evidence(path.read_bytes())
        if expected != actual or sidecar.read_bytes() != original:
            raise ValueError('Compaction semantic/original-sidecar verification failed: ' + relative)
        before_record, after_record = semantic_record(expected), semantic_record(actual)
        digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        proof.update({
            'input_elf': relative,
            'debug_sidecar': str(sidecar),
            'compiler': str(plan['compiler']),
            'checker': module.__name__,
            'checker_sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
            'semantic_equivalence': {
                'components_unchanged': {key: expected[key] == actual[key] for key in expected},
                'before_sha256': digest(before_record), 'after_sha256': digest(after_record),
                'retained_semantics': before_record,
            },
        })
        proofs[relative] = proof
    return proofs


def compact_new_providers(output, plan):
    return compact_images(output, plan)
