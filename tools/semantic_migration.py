"""Explicit offline export and local import; never overwrite a legacy index."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

COLLECTIONS = ('policy_kb', 'voice_calls')
MAX_EXPORT_BYTES = 256 * 1024 * 1024


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object keys in semantic export')
        result[key] = value
    return result


def export_legacy(source: Path, destination: Path) -> dict:
    """Read a scratch copy with the old SDK; the original files are never opened by it."""
    if not source.is_dir() or source.is_symlink():
        raise ValueError('Expected a stopped legacy index directory')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Export destination already exists')
    if destination.resolve().is_relative_to(source.resolve()):
        raise ValueError('Export destination must be outside the legacy directory')
    # This command is for the old, isolated migration environment only. Chroma is
    # intentionally absent from the application runtime dependency declarations.
    import chromadb
    from chromadb.config import Settings

    if chromadb.__version__ != '1.5.9':
        raise ValueError('Use the reviewed 1.5.9 SDK in an isolated migration environment')
    with tempfile.TemporaryDirectory(prefix='voicescope-legacy-export-') as temporary:
        copied = Path(temporary) / 'index'
        shutil.copytree(source, copied, symlinks=True)
        if any(p.is_symlink() for p in copied.rglob('*')):
            raise ValueError('Legacy index must not contain symlinks')
        client = chromadb.PersistentClient(path=str(copied), settings=Settings(
            chroma_api_impl='chromadb.api.rust.RustBindingsAPI',
            chroma_server_authn_provider=None, chroma_server_authz_provider=None,
            anonymized_telemetry=False))
        try:
            names = {collection.name for collection in client.list_collections()}
            exported = {}
            for name in COLLECTIONS:
                if name in names:
                    rows = client.get_collection(name).get(include=['documents', 'metadatas'])
                    metadata = rows['metadatas']
                    if rows['documents'] is None or metadata is None:
                        raise ValueError('Legacy export is missing requested document fields')
                    exported[name] = {'ids': rows['ids'], 'documents': rows['documents'],
                                      'metadatas': [m or {} for m in metadata]}
            if names - set(COLLECTIONS):
                raise ValueError('Unrecognized collections require a separate reviewed export')
            if not exported:
                raise ValueError('No supported legacy collections found')
        finally:
            system = getattr(client, '_system', None)
            if system is None:
                raise RuntimeError('Legacy client cannot be closed safely')
            system.stop()
    payload = {'format': 'voicescope-semantic-export-v1', 'collections': exported}
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent) as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.link(stream.name, destination)
    return payload


def _merge_exports(sources: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Combine stopped indexes without selecting a side for duplicate-ID conflicts."""
    total_bytes = 0
    hashes: set[str] = set()
    merged: dict[str, dict[str, tuple[str, dict, str]]] = {}
    for source in sources:
        with source.open('rb') as stream:
            payload = stream.read(MAX_EXPORT_BYTES - total_bytes + 1)
        total_bytes += len(payload)
        if total_bytes > MAX_EXPORT_BYTES:
            raise ValueError('Combined exports exceed the 256 MiB import limit')
        data = json.loads(payload, object_pairs_hook=_unique_object)
        if (not isinstance(data, dict) or data.get('format') != 'voicescope-semantic-export-v1'
                or not isinstance(data.get('collections'), dict)
                or not data['collections'] or set(data['collections']) - set(COLLECTIONS)):
            raise ValueError('Unsupported semantic export')
        hashes.add(hashlib.sha256(payload).hexdigest())
        for name, rows in data['collections'].items():
            if (not isinstance(rows, dict) or set(rows) != {'ids', 'documents', 'metadatas'}
                    or any(not isinstance(rows[key], list) for key in rows)):
                raise ValueError('Invalid exported collection')
            ids, documents, metadata = rows['ids'], rows['documents'], rows['metadatas']
            if (len(ids) != len(documents) or len(ids) != len(metadata)
                    or any(not isinstance(i, str) or not i for i in ids)
                    or len(set(ids)) != len(ids)):
                raise ValueError('Invalid exported document IDs')
            target = merged.setdefault(name, {})
            for identity, document, item in zip(ids, documents, metadata, strict=True):
                if not isinstance(document, str) or not document.strip() or not isinstance(item, dict):
                    raise ValueError('Invalid exported document')
                canonical = json.dumps(item, sort_keys=True, allow_nan=False)
                previous = target.get(identity)
                if previous is not None and (previous[0] != document or previous[2] != canonical):
                    raise ValueError('conflicting document IDs across exports')
                target[identity] = document, item, canonical
    collections = {}
    for name, documents in merged.items():
        ids = sorted(documents)
        collections[name] = {'ids': ids, 'documents': [documents[i][0] for i in ids],
                             'metadatas': [documents[i][1] for i in ids]}
    return collections, sorted(hashes)


def import_export(source: Path, destination: Path, *, additional_sources: list[Path] | None = None) -> int:
    """Re-embed one or more exports and publish one complete new SQLite index."""
    from storage.semantic_index import MODEL_VERSION, SemanticCollection
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Index destination already exists')
    collections, source_hashes = _merge_exports([source, *(additional_sources or [])])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile(prefix='.semantic-import-', dir=destination.parent) as temporary:
        for name, rows in collections.items():
            collection = SemanticCollection(name, path=Path(temporary.name))
            collection.upsert(**rows)
            if collection.count() != len(rows['ids']):
                raise ValueError('Imported count does not match export')
            count += collection.count()
        with closing(sqlite3.connect(temporary.name)) as conn, conn:
            conn.execute('CREATE TABLE semantic_migrations (source_sha256 TEXT PRIMARY KEY, model TEXT NOT NULL)')
            conn.executemany('INSERT INTO semantic_migrations VALUES(?,?)',
                [(digest, MODEL_VERSION) for digest in source_hashes])
        os.link(temporary.name, destination)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['export', 'import'])
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--confirm-offline', action='store_true')
    parser.add_argument('--additional-source', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    try:
        if args.operation == 'export':
            if args.additional_source:
                raise ValueError('Additional sources are supported only for import')
            if not args.confirm_offline:
                raise ValueError('Stop the legacy application and confirm offline export')
            export_legacy(args.source, args.destination)
        else:
            import_export(args.source, args.destination, additional_sources=args.additional_source)
    except (OSError, ValueError, TypeError, ImportError, RuntimeError, sqlite3.Error) as exc:
        print(f'Semantic migration failed ({type(exc).__name__}); inspect private configuration.', file=sys.stderr)
        return 1
    print('Semantic migration completed. Source and destination contain private data.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
