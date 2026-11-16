"""Release configuration contracts; no hosting credentials or network required."""

import tomllib
from pathlib import Path

import yaml


MANIFEST = Path(__file__).resolve().parents[1] / 'railway.toml'


def test_railway_uses_documented_builder_and_restart_policy():
    config = tomllib.loads(MANIFEST.read_text())
    assert config['build']['builder'] == 'DOCKERFILE'
    assert config['deploy']['restartPolicyType'] == 'ON_FAILURE'


def test_staging_requires_persistent_storage_and_one_replica():
    config = tomllib.loads(MANIFEST.read_text())
    staging = config['environments']['staging']['deploy']
    assert staging['requiredMountPath'] == '/app/data'
    assert staging['numReplicas'] == 1


def test_staging_startup_budget_does_not_change_production_default():
    config = tomllib.loads(MANIFEST.read_text())
    assert config['deploy']['healthcheckPath'] == '/api/v1/health'
    assert config['deploy']['healthcheckTimeout'] == 30
    staging = config['environments']['staging']['deploy']
    assert 60 <= staging['healthcheckTimeout'] <= 120


def test_render_demo_is_free_and_separate_from_production():
    config = yaml.safe_load((MANIFEST.parent / 'render.staging.yaml').read_text())
    assert set(config) == {'services'}
    assert len(config['services']) == 1
    service = config['services'][0]
    assert service['name'] == 'voicescope-staging-demo'
    assert service['plan'] == 'free'
    assert service['branch'] == 'feat/voicescope-reliability-stt-demo'
    assert service['autoDeployTrigger'] == 'off'
    assert 'disk' not in service
    assert 'id' not in service


def test_render_demo_requires_separate_auth_and_has_no_live_provider_credentials():
    config = yaml.safe_load((MANIFEST.parent / 'render.staging.yaml').read_text())
    service = config['services'][0]
    assert service['healthCheckPath'] == '/api/v1/health'
    assert service['numInstances'] == 1
    variables = {item['key']: item for item in service['envVars']}
    assert variables['STAGING_DEMO_ONLY']['value'] == 'true'
    for key in ['VALID_API_KEYS', 'BOLNA_WEBHOOK_SECRET']:
        assert variables[key] == {'key': key, 'sync': False}
    assert not {'DATABASE_URL', 'BOLNA_API_KEY', 'DEEPGRAM_API_KEY', 'GROQ_API_KEY'} & variables.keys()
    assert all('fromGroup' not in item and 'fromDatabase' not in item and 'fromService' not in item
               for item in service['envVars'])
