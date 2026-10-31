"""Keep Chroma embedded; server transports are outside the reviewed security boundary."""

import chromadb
from chromadb.config import Settings


def embedded_client(path: str):
    return chromadb.PersistentClient(path=path, settings=Settings(
        chroma_api_impl='chromadb.api.rust.RustBindingsAPI',
        chroma_server_authn_provider=None,
        chroma_server_authz_provider=None,
        anonymized_telemetry=False,
    ))
