"""Oracle falsification and transported receipt controls, not target execution."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xtensa_qualification', ROOT / 'scripts/qualify_t039_xtensa_relocations.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


class SourceContract(unittest.TestCase):
    def test_actual_production_backend(self):
        self.assertIn('arch/esp_elf_xtensa.c', q.SOURCES)
        self.assertIn('esp_elf_adapter.c', q.SOURCES)
        self.assertIn('dlso/dlmod.c', q.SOURCES)
        self.assertIn('esp_privileged_os_cpu.c', q.SOURCES)
        self.assertEqual(q.PARENT, '30ef8d4fbe7bf63072c72988e3711880672d1196')
        source = (ROOT / 'tests/t039-relocation/runner.c').read_text()
        self.assertNotIn('int esp_elf_arch_relocate(', source)
        self.assertNotIn('uintptr_t elf_remap_text(', source)
        self.assertNotIn('PROT_EXEC', source)
        self.assertIn('MAP_FIXED_NOREPLACE', source)
        self.assertIn('__asan_poison_memory_region', source)


@unittest.skipUnless(os.environ.get('T039_RELOCATION_ARTIFACT'), 'requires qualification output')
class OracleControls(unittest.TestCase):
    def setUp(self):
        self.source = Path(os.environ['T039_RELOCATION_ARTIFACT'])
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.data = (self.source / 'candidate-0.1.31/input.elf').read_bytes()
        self.exports = json.loads((self.source / 'released-public-exports.json').read_bytes())
        shutil.copytree(self.source / 'candidate-0.1.31/normal', self.work / 'run')
        self.work /= 'run'
        self.meta = json.loads((self.work / 'first.json').read_bytes())
        self.elf, self.sections, self.rows, self.symbols = q.model(self.data)

    def check(self):
        return q.check_dump(self.data, self.exports, self.work, 'first')

    def patch_word(self, row, value):
        name, section = next((n, s) for n, s in self.sections.items()
                             if s['sh_addr'] <= row['site'] < s['sh_addr'] + s['sh_size'])
        path = self.work / f'first-{q.SLOTS[name]}.bin'
        blob = bytearray(path.read_bytes()); at = row['site'] - section['sh_addr']
        blob[at:at+4] = value.to_bytes(4, 'little'); path.write_bytes(blob)

    def test_unmodified(self):
        self.assertEqual(self.check()['relocations'], {'2': 2, '4': 142, '5': 2826})

    def test_no_op_relocator_rejected(self):
        for name, section in self.sections.items():
            (self.work / f'first-{q.SLOTS[name]}.bin').write_bytes(section.data())
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ'):
            self.check()

    def test_identity_text_remapper_rejected(self):
        text = self.sections['.text']
        for row in self.rows:
            if row['type'] != 5:
                continue
            section = next(s for s in self.sections.values() if s['sh_addr'] <= row['site'] < s['sh_addr'] + s['sh_size'])
            at = row['site'] - section['sh_addr']; value = int.from_bytes(section.data()[at:at+4], 'little')
            if text['sh_addr'] <= value < text['sh_addr'] + text['sh_size']:
                self.patch_word(row, self.meta['ptext'] + value - text['sh_addr'])
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ'):
            self.check()

    def test_wrong_released_import_address_rejected(self):
        row = next(r for r in self.rows if r['type'] == 4 and not r['defined'])
        self.patch_word(row, self.exports[row['name']] ^ 4)
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ'):
            self.check()

    def test_wrong_rtld_write_rejected(self):
        self.patch_word(next(r for r in self.rows if r['type'] == 2), 0x12345678)
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ'):
            self.check()

    def test_dirty_bss_rejected(self):
        path = self.work / 'first-1.bin'; b = bytearray(path.read_bytes()); b[-1] = 1; path.write_bytes(b)
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ: .bss'):
            self.check()

    def test_non_relocation_byte_rejected(self):
        path = self.work / 'first-0.bin'; b = bytearray(path.read_bytes()); b[-1] ^= 1; path.write_bytes(b)
        with self.assertRaisesRegex(ValueError, 'Relocated section bytes differ'):
            self.check()

    def test_entry_requires_alias(self):
        self.meta['entry'] -= 0x6000000; q.write(self.work / 'first.json', self.meta)
        with self.assertRaisesRegex(ValueError, 'Entry address differs'):
            self.check()

    def test_exports_require_alias(self):
        self.meta['exports']['app_main'] -= 0x6000000; q.write(self.work / 'first.json', self.meta)
        with self.assertRaisesRegex(ValueError, 'Export addresses differ'):
            self.check()

    def test_high_pointer_rejected(self):
        self.meta['sections'][0]['address'] += 1 << 32; q.write(self.work / 'first.json', self.meta)
        with self.assertRaisesRegex(ValueError, 'Not a low 32-bit'):
            self.check()

    def test_layout_corruption_rejected(self):
        self.meta['sections'][3]['address'] += 4; q.write(self.work / 'first.json', self.meta)
        with self.assertRaisesRegex(ValueError, 'Data placement mismatch'):
            self.check()


if __name__ == '__main__':
    unittest.main()
