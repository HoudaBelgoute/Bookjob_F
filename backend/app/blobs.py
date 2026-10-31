"""Stockage de fichiers privés dans Postgres (Supabase), table `user_files`.

`BlobPath` imite le sous-ensemble de `pathlib.Path` utilisé par l'application
(exists, read_bytes, write_text, unlink, stat, `/`…) afin que le code métier
fonctionne à l'identique sur Vercel, dont le disque est en lecture seule.
"""
import posixpath
import time
from types import SimpleNamespace

from . import db

GLOBAL_OWNER = "_global"


class BlobPath:
    __slots__ = ("owner", "key")

    def __init__(self, owner: str, key: str):
        self.owner = str(owner)
        self.key = posixpath.normpath(str(key).replace("\\", "/")).lstrip("/")
        if self.key == ".":
            self.key = ""

    # ---------- navigation ----------
    def __truediv__(self, other) -> "BlobPath":
        return BlobPath(self.owner, posixpath.join(self.key, str(other).replace("\\", "/")))

    def __repr__(self) -> str:
        return f"BlobPath({self.owner!r}, {self.key!r})"

    def __str__(self) -> str:
        return self.key

    def __eq__(self, other) -> bool:
        return isinstance(other, BlobPath) and (self.owner, self.key) == (other.owner, other.key)

    def __hash__(self) -> int:
        return hash((self.owner, self.key))

    @property
    def name(self) -> str:
        return posixpath.basename(self.key)

    @property
    def suffix(self) -> str:
        return posixpath.splitext(self.name)[1]

    @property
    def stem(self) -> str:
        return posixpath.splitext(self.name)[0]

    @property
    def parent(self) -> "BlobPath":
        return BlobPath(self.owner, posixpath.dirname(self.key))

    def with_name(self, name: str) -> "BlobPath":
        return self.parent / name

    def with_suffix(self, suffix: str) -> "BlobPath":
        return self.parent / (self.stem + suffix)

    def resolve(self) -> "BlobPath":
        return self

    def is_relative_to(self, other: "BlobPath") -> bool:
        return self.owner == other.owner and (not other.key or self.key.startswith(other.key + "/"))

    # ---------- no-op (pas de dossiers ni de permissions en base) ----------
    def mkdir(self, *args, **kwargs) -> None:
        return None

    def chmod(self, *args, **kwargs) -> None:
        return None

    # ---------- lecture ----------
    def _row(self, columns: str):
        with db.connection() as conn:
            return conn.execute(
                f"SELECT {columns} FROM user_files WHERE user_id = %s AND path = %s",
                (self.owner, self.key),
            ).fetchone()

    def exists(self) -> bool:
        return bool(self.key) and self._row("1 AS ok") is not None

    is_file = exists

    def is_dir(self) -> bool:
        return False

    def read_bytes(self) -> bytes:
        row = self._row("data")
        if row is None:
            raise FileNotFoundError(self.key)
        return bytes(row["data"])

    def read_text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        return self.read_bytes().decode(encoding, errors)

    def stat(self):
        row = self._row("octet_length(data) AS size, extract(epoch FROM updated_at) AS mtime")
        if row is None:
            raise FileNotFoundError(self.key)
        return SimpleNamespace(st_size=int(row["size"]), st_mtime=float(row["mtime"] or time.time()))

    # ---------- écriture ----------
    def write_bytes(self, data: bytes) -> int:
        data = bytes(data)
        with db.connection() as conn:
            conn.execute(
                """INSERT INTO user_files (user_id, path, data, updated_at)
                   VALUES (%s, %s, %s, now())
                   ON CONFLICT (user_id, path)
                   DO UPDATE SET data = EXCLUDED.data, updated_at = now()""",
                (self.owner, self.key, data),
            )
        return len(data)

    def write_text(self, text: str, encoding: str = "utf-8") -> int:
        return self.write_bytes(text.encode(encoding))

    def unlink(self, missing_ok: bool = False) -> None:
        with db.connection() as conn:
            deleted = conn.execute(
                "DELETE FROM user_files WHERE user_id = %s AND path = %s", (self.owner, self.key)
            ).rowcount
        if not deleted and not missing_ok:
            raise FileNotFoundError(self.key)

    def replace(self, target: "BlobPath") -> "BlobPath":
        with db.connection() as conn:
            conn.execute("DELETE FROM user_files WHERE user_id = %s AND path = %s", (target.owner, target.key))
            moved = conn.execute(
                "UPDATE user_files SET user_id = %s, path = %s, updated_at = now() WHERE user_id = %s AND path = %s",
                (target.owner, target.key, self.owner, self.key),
            ).rowcount
        if not moved:
            raise FileNotFoundError(self.key)
        return target

    rename = replace


def delete_owner(owner: str) -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM user_files WHERE user_id = %s", (owner,))
