import pytest
from fastapi.testclient import TestClient

from api.routes import KnowledgeEntryRequest
from main import app
from storage.transcript_store import TranscriptStore
from storage.semantic_index import MODEL_NAME


def test_runtime_dependencies_do_not_install_the_legacy_server_package():
    from pathlib import Path
    import tomllib

    root = Path(__file__).resolve().parents[1]
    dependencies = tomllib.loads((root / 'pyproject.toml').read_text())['project']['dependencies']
    assert not any(d.startswith('chromadb') for d in dependencies)
    assert not any(line.startswith('chromadb') for line in (root / 'requirements.txt').read_text().splitlines())


def test_new_storage_overrides_cannot_escape_the_synthetic_demo_directory(monkeypatch, tmp_path):
    from core.staging import validate_demo_environment

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path.parent / 'outside-demo.sqlite'))
    with pytest.raises(ValueError, match='storage'):
        validate_demo_environment()


def test_embedded_collection_has_no_server_authorization_or_remote_embedding_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path / 'semantic.sqlite'))
    store = TranscriptStore()
    assert store.collection is not None
    assert store.collection.path.is_file()
    assert MODEL_NAME == 'sentence-transformers/all-MiniLM-L6-v2'
    assert not list(tmp_path.glob('**/chroma*'))


@pytest.mark.parametrize('method,path', [
    ('PUT', '/api/v2/tenants/default_tenant/databases/default_database/collections/synthetic'),
    ('POST', '/api/v2/tenants/default_tenant/databases/default_database/collections'),
    ('GET', '/api/v2/auth/identity'),
    ('PUT', '/api/v1/collections/synthetic'),
])
def test_authenticated_requests_cannot_reach_chroma_server_routes(monkeypatch, method, path):
    import middleware.auth
    monkeypatch.setattr(middleware.auth, '_VALID_KEYS', frozenset({'synthetic-boundary-key'}))
    response = TestClient(app).request(method, path,
        headers={'X-API-Key': 'synthetic-boundary-key'},
        json={'new_configuration': {'embedding_function': {
            'name': 'sentence_transformer',
            'config': {'model_name': 'synthetic/untrusted', 'trust_remote_code': True},
        }}})
    assert response.status_code == 404


def test_policy_input_does_not_accept_model_configuration():
    request = KnowledgeEntryRequest.model_validate({
        'title': 'Synthetic policy', 'content': 'Treat this as text only.',
        'configuration': {'embedding_function': {'trust_remote_code': True}},
        'tenant': 'another-company',
    })
    assert request.model_dump() == {
        'title': 'Synthetic policy', 'content': 'Treat this as text only.',
    }


def test_environment_cannot_select_unreviewed_chroma_server_transport(monkeypatch, tmp_path):
    monkeypatch.setenv('CHROMA_API_IMPL', 'chromadb.api.fastapi.FastAPI')
    monkeypatch.setenv('CHROMA_SERVER_AUTHZ_PROVIDER', 'chromadb.auth.simple_rbac_authz.SimpleRBACAuthorizationProvider')
    monkeypatch.setenv('SEMANTIC_DB_PATH', str(tmp_path / 'semantic.sqlite'))
    store = TranscriptStore()
    assert store.collection.path == tmp_path / 'semantic.sqlite'
    assert store.collection.count() == 0
