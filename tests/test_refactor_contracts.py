"""Public contracts and configuration boundaries frozen before extraction."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from resolveguard.configuration import load_environment_entries, REPLY_ENVIRONMENT_KEYS
from resolveguard.reply_generation import ReplyGenerator, ReplySettings
from resolveguard.web import create_app, WebTurn, DemoSettings
from resolveguard import web_contracts

FIXTURES = Path(__file__).parent/'fixtures'


class RefactorContractTests(unittest.TestCase):
    def test_openapi_matches_pre_refactor_contract(self):
        expected=json.loads((FIXTURES/'web_openapi.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'web.sqlite3',ReplyGenerator(ReplySettings(mode='off')))
            self.assertEqual(app.openapi(),expected)

    def test_legacy_web_model_imports_and_identity(self):
        self.assertIs(WebTurn,web_contracts.WebTurn)
        self.assertIs(DemoSettings,web_contracts.DemoSettings)
        self.assertEqual(WebTurn.__module__,'resolveguard.web')
        self.assertEqual(DemoSettings().profile,'signed-out')

    def test_browser_assets_are_byte_identical(self):
        expected=json.loads((FIXTURES/'web_asset_sha256.json').read_text(encoding='utf-8'))
        package=Path(__file__).resolve().parents[1]/'resolveguard'
        actual={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (package/'static').rglob('*') if p.is_file()}
        self.assertEqual(actual,expected)

    def test_configuration_preserves_existing_values_and_first_occurrence(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'KEEP':'process'},clear=True):
            path=Path(tmp)/'settings';path.write_text('KEEP=file\nNEW=first\nNEW=second\n',encoding='utf-8-sig')
            load_environment_entries(path,{'KEEP','NEW'})
            self.assertEqual(dict(os.environ),{'KEEP':'process','NEW':'first'})

    def test_runtime_allowlist_cannot_load_cloud_or_unknown_settings(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            path=Path(tmp)/'settings'
            path.write_text('LANGSMITH_TRACING=true\nLANGSMITH_API_KEY=not-a-real-key\nUNKNOWN=x\nRESOLVEGUARD_REPLY_MODE=all\n',encoding='utf-8')
            load_environment_entries(path,REPLY_ENVIRONMENT_KEYS)
            self.assertEqual(dict(os.environ),{'RESOLVEGUARD_REPLY_MODE':'all'})

    def test_literal_configuration_does_not_expand_or_execute(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
            path=Path(tmp)/'settings'
            path.write_text('VALUE="$(never_run)=literal"\nEMPTY=\n# COMMENT=ignored\n',encoding='utf-8')
            load_environment_entries(path,{'VALUE','EMPTY'})
            self.assertEqual(os.environ['VALUE'],'$(never_run)=literal')
            self.assertEqual(os.environ['EMPTY'],'')
            self.assertNotIn('# COMMENT',os.environ)
