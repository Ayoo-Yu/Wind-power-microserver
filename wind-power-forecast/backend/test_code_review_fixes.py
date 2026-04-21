"""
Tests for code review fixes: security (no hardcoded secrets), dedup logic, error sanitization.
"""
import re
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT)
AUTOPREDICT_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'backend-autopredict')


class TestNoHardcodedSecrets(unittest.TestCase):
    """C1, C2: Verify no hardcoded passwords or JWT secrets in source files."""

    FORBIDDEN_PATTERNS = [
        (r"DB_PASSWORD.*=.*['\"]12345678ab['\"]", "hardcoded DB_PASSWORD"),
        (r"JWT_SECRET_KEY.*['\"]wind-power-forecast-secret", "hardcoded JWT secret"),
        (r"SECRET_KEY.*['\"]wind-power-forecast-secret-key", "hardcoded SECRET_KEY default"),
    ]

    def _read_file(self, filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def test_backend_app_no_hardcoded_secrets(self):
        content = self._read_file(os.path.join(BACKEND_DIR, 'app.py'))
        for pattern, desc in self.FORBIDDEN_PATTERNS:
            with self.subTest(pattern=desc, file='app.py'):
                self.assertNotRegex(content, pattern, f"Found {desc} in backend/app.py")

    def test_autopredict_app_no_hardcoded_secrets(self):
        filepath = os.path.join(AUTOPREDICT_DIR, 'app.py')
        if not os.path.exists(filepath):
            self.skipTest("autopredict app.py not found")
        content = self._read_file(filepath)
        for pattern, desc in self.FORBIDDEN_PATTERNS:
            with self.subTest(pattern=desc, file='app.py'):
                self.assertNotRegex(content, pattern, f"Found {desc} in backend-autopredict/app.py")

    def test_compose_no_plaintext_password(self):
        filepath = os.path.join(os.path.dirname(PROJECT_ROOT), 'frontend-backend-compose.yaml')
        if not os.path.exists(filepath):
            self.skipTest("compose file not found")
        content = self._read_file(filepath)
        # Check that no line has the raw password without variable substitution
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if 'DB_PASSWORD' in stripped and stripped.startswith('-'):
                self.assertIn('${', stripped,
                    f"Line {i}: DB_PASSWORD should use env var substitution, not plaintext")


class TestBareExcept(unittest.TestCase):
    """H4: Verify no bare except: clauses in app.py files."""

    def test_backend_app_no_bare_except(self):
        filepath = os.path.join(BACKEND_DIR, 'app.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Match "except:" not followed by any exception type
        bare_excepts = re.findall(r'^\s*except\s*:\s*$', content, re.MULTILINE)
        self.assertEqual(len(bare_excepts), 0,
            f"Found {len(bare_excepts)} bare except: in backend/app.py")

    def test_autopredict_app_no_bare_except(self):
        filepath = os.path.join(AUTOPREDICT_DIR, 'app.py')
        if not os.path.exists(filepath):
            self.skipTest("autopredict app.py not found")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        bare_excepts = re.findall(r'^\s*except\s*:\s*$', content, re.MULTILINE)
        self.assertEqual(len(bare_excepts), 0,
            f"Found {len(bare_excepts)} bare except: in backend-autopredict/app.py")


class TestDedupLogic(unittest.TestCase):
    """H2: Verify dedup uses composite key (timestamp, farm_code)."""

    def test_dedup_uses_composite_key(self):
        filepath = os.path.join(BACKEND_DIR, 'routes', 'actual_power_router.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the dedup section
        self.assertIn("(record['timestamp'], record['farm_code'])",
            content,
            "Dedup should use (timestamp, farm_code) composite key")

    def test_dedup_no_timestamp_only_key(self):
        filepath = os.path.join(BACKEND_DIR, 'routes', 'actual_power_router.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Should NOT have the old pattern: key on timestamp alone
        old_pattern = "if record['timestamp'] not in seen_timestamps_in_chunk"
        self.assertNotIn(old_pattern, content,
            "Dedup should not use timestamp-only key")


class TestErrorSanitization(unittest.TestCase):
    """H3: Verify error responses don't leak str(e) to client."""

    def test_no_str_e_in_error_responses(self):
        filepath = os.path.join(BACKEND_DIR, 'routes', 'actual_power_router.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find jsonify error responses that include str(e)
        lines = content.splitlines()
        leaks = []
        for i, line in enumerate(lines, 1):
            if 'jsonify' in line and 'str(e)' in line and '500' in content[max(0, content.find(line)-200):content.find(line)+200]:
                leaks.append((i, line.strip()))

        self.assertEqual(len(leaks), 0,
            f"Found str(e) in error responses at lines: {leaks}")


class TestEcmwfImportGuard(unittest.TestCase):
    """H1: Verify ecmwf_ingest_service import is guarded."""

    def test_ecmwf_import_is_guarded(self):
        filepath = os.path.join(BACKEND_DIR, 'routes', 'ecmwf_data_router.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # The import block should be wrapped in try/except ImportError
        import_block = content[content.find("try:"):content.find("except ImportError")]
        self.assertIn("from services.ecmwf_ingest_service", import_block,
            "ecmwf_ingest_service import should be inside try block")

        self.assertIn("except ImportError", content,
            "Import should catch ImportError specifically")

    def test_ecmwf_routes_check_service_available(self):
        filepath = os.path.join(BACKEND_DIR, 'routes', 'ecmwf_data_router.py')
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("_require_service", content,
            "Route handlers should call _require_service() to check availability")


if __name__ == '__main__':
    unittest.main()
