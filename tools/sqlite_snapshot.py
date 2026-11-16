"""Create or restore one SQLite snapshot without overwriting an existing file."""

import argparse
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path


def snapshot_sqlite(source: Path, destination: Path) -> None:
    """Copy committed state, including WAL data, into a private new database."""
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError('Source must be a SQLite database file')
    with source.open('rb') as stream:
        if stream.read(16) != b'SQLite format 3\x00':
            raise ValueError('Source is not a SQLite database')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Destination already exists')
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    deadline = time.monotonic() + 30

    def check_deadline(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise TimeoutError('SQLite snapshot timed out')

    with tempfile.NamedTemporaryFile(prefix='.sqlite-snapshot-', dir=destination.parent) as temporary:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(temporary.name)) as snapshot:
                original.backup(snapshot, pages=128, progress=check_deadline, sleep=0.01)
                if snapshot.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Snapshot integrity check failed')
        # Linking publishes only a completed snapshot and cannot overwrite a file
        # created by another operator while the backup was running.
        os.link(temporary.name, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot_sqlite(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'SQLite snapshot failed ({type(exc).__name__}); source was not modified.', file=sys.stderr)
        return 1
    print('SQLite snapshot created. Keep it private; it may contain call data.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
