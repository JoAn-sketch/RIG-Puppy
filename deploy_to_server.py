from __future__ import annotations

import argparse
import fnmatch
import os
import posixpath
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import paramiko


HOST = "122.51.155.114"
USERNAME = "ubuntu"
PASSWORD = "Zzyr@2026"
LOCAL_ROOT = Path("/Users/joan/RIG-Puppy")


@dataclass(frozen=True)
class SyncTarget:
    name: str
    local_path: Path
    remote_path: str
    exclude_globs: tuple[str, ...]


TARGETS = (
    SyncTarget(
        name="source",
        local_path=LOCAL_ROOT / "xiaozhi-esp32-server-main",
        remote_path="/home/ubuntu/xiaozhi-esp32-server-main",
        exclude_globs=(
            ".git",
            "__pycache__",
            "*.pyc",
            "*.log",
            "*.tar.gz",
            "*.tmp",
            "*.swp",
            ".DS_Store",
        ),
    ),
    SyncTarget(
        name="kb-admin",
        local_path=LOCAL_ROOT / "kb-admin",
        remote_path="/home/ubuntu/kb-admin",
        exclude_globs=(
            ".env",
            "__pycache__",
            "*.pyc",
            "*.log",
            "data/files",
            "data/files/*",
            "data/prompts",
            "data/prompts/*",
            ".DS_Store",
        ),
    ),
    SyncTarget(
        name="deploy",
        local_path=LOCAL_ROOT / "xiaozhi-server",
        remote_path="/home/ubuntu/xiaozhi-server",
        exclude_globs=(
            "mysql",
            "mysql/*",
            "models",
            "models/*",
            "uploadfile",
            "uploadfile/*",
            "web-html.bak*",
            ".config.yaml",
            "data/.config.yaml",
            "__pycache__",
            "*.pyc",
            "*.log",
            ".DS_Store",
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally sync local RIG-Puppy code to the server."
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=[target.name for target in TARGETS],
        help="Sync only selected target(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without modifying the server.",
    )
    return parser.parse_args()


def should_exclude(relative_path: str, patterns: tuple[str, ...]) -> bool:
    normalized = relative_path.strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    for part in parts:
        if part in {".git", "__pycache__"}:
            return True
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    current = ""
    for segment in remote_dir.strip("/").split("/"):
        current = f"{current}/{segment}"
        try:
            attrs = sftp.stat(current)
            if not stat.S_ISDIR(attrs.st_mode):
                raise RuntimeError(f"Remote path is not a directory: {current}")
        except FileNotFoundError:
            sftp.mkdir(current)


def remote_file_needs_update(
    sftp: paramiko.SFTPClient, local_file: Path, remote_file: str
) -> bool:
    try:
        attrs = sftp.stat(remote_file)
    except FileNotFoundError:
        return True

    local_stat = local_file.stat()
    local_size = local_stat.st_size
    local_mtime = int(local_stat.st_mtime)
    remote_size = attrs.st_size
    remote_mtime = int(attrs.st_mtime)
    return local_size != remote_size or local_mtime > remote_mtime


def upload_file(
    sftp: paramiko.SFTPClient, local_file: Path, remote_file: str, dry_run: bool
) -> bool:
    if not remote_file_needs_update(sftp, local_file, remote_file):
        return False

    if dry_run:
        print(f"UPLOAD {local_file} -> {remote_file}")
        return True

    remote_dir = posixpath.dirname(remote_file)
    ensure_remote_dir(sftp, remote_dir)
    temp_remote = f"{remote_file}.codex-uploading"
    sftp.put(str(local_file), temp_remote)

    local_stat = local_file.stat()
    sftp.chmod(temp_remote, stat.S_IMODE(local_stat.st_mode))
    sftp.utime(temp_remote, (int(local_stat.st_atime), int(local_stat.st_mtime)))
    try:
        if hasattr(sftp, "posix_rename"):
            sftp.posix_rename(temp_remote, remote_file)
        else:
            raise IOError("posix_rename unavailable")
    except Exception:
        try:
            sftp.remove(remote_file)
        except FileNotFoundError:
            pass
        sftp.rename(temp_remote, remote_file)
    print(f"UPLOADED {local_file} -> {remote_file}")
    return True


def sync_target(
    sftp: paramiko.SFTPClient, target: SyncTarget, dry_run: bool
) -> tuple[int, int]:
    uploaded = 0
    scanned = 0

    if not target.local_path.exists():
        print(f"SKIP {target.name}: missing local path {target.local_path}")
        return uploaded, scanned

    for local_path in sorted(target.local_path.rglob("*")):
        if local_path.is_dir():
            continue
        relative = local_path.relative_to(target.local_path).as_posix()
        if should_exclude(relative, target.exclude_globs):
            continue
        scanned += 1
        remote_path = posixpath.join(target.remote_path, relative)
        if upload_file(sftp, local_path, remote_path, dry_run):
            uploaded += 1

    return uploaded, scanned


def main() -> int:
    args = parse_args()
    selected = set(args.only or [target.name for target in TARGETS])
    targets = [target for target in TARGETS if target.name in selected]

    start = time.time()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USERNAME, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    try:
        total_uploaded = 0
        total_scanned = 0
        for target in targets:
            uploaded, scanned = sync_target(sftp, target, args.dry_run)
            total_uploaded += uploaded
            total_scanned += scanned
            print(
                f"TARGET {target.name}: scanned={scanned} uploaded={uploaded}"
            )
    finally:
        sftp.close()
        client.close()

    elapsed = time.time() - start
    mode = "DRY-RUN" if args.dry_run else "DONE"
    print(
        f"{mode} scanned={total_scanned} uploaded={total_uploaded} "
        f"elapsed={elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
