import pytest
from fastapi.testclient import TestClient

from api.routes import KnowledgeEntryRequest
from main import app
from storage.chroma_store import ChromaStore
from storage.chroma_client import embedded_client


def test_embedded_collection_has_no_server_authorization_or_remote_embedding_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('CHROMA_PERSIST_DIR', str(tmp_path / 'chroma'))
    store = ChromaStore()
    assert store.client is not None
    assert store.collection is not None
    settings = store.client.get_settings()
    assert settings.chroma_api_impl == 'chromadb.api.rust.RustBindingsAPI'
    assert settings.chroma_server_authn_provider is None
    assert settings.chroma_server_authz_provider is None
    assert type(store.client._server).__module__ == 'chromadb.api.rust'
    assert store.collection._embedding_function.name() == 'default'


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
    client = embedded_client(str(tmp_path / 'forced-local'))
    assert client.get_settings().chroma_api_impl == 'chromadb.api.rust.RustBindingsAPI'
    assert client.get_settings().chroma_server_authz_provider is None
    assert type(client._server).__module__ == 'chromadb.api.rust'
