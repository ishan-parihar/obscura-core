"""Runtime detection and ID generation for shared use across CLI tools."""

from __future__ import annotations

import os
import platform
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RuntimeInfo:
    """Information about the current runtime environment."""
    runtime_id: str
    platform: str
    architecture: str
    is_container: bool
    container_type: str | None
    python_version: str
    hostname: str


def get_runtime_info() -> RuntimeInfo:
    """Detect and return runtime information."""
    # Generate a stable runtime ID based on machine characteristics
    machine_id = _get_machine_id()
    runtime_id = f"{platform.system()}-{platform.machine()}-{machine_id[:8]}"

    # Detect if running in a container
    is_container, container_type = _detect_container()

    return RuntimeInfo(
        runtime_id=runtime_id,
        platform=platform.system(),
        architecture=platform.machine(),
        is_container=is_container,
        container_type=container_type,
        python_version=platform.python_version(),
        hostname=platform.node(),
    )


def _get_machine_id() -> str:
    """Get a unique machine identifier."""
    # Try various sources for machine ID
    candidates = []

    # Docker container ID
    if Path("/proc/self/cgroup").exists():
        try:
            cgroup = Path("/proc/self/cgroup").read_text()
            for line in cgroup.splitlines():
                if "/docker/" in line:
                    candidates.append(line.split("/docker/")[-1][:12])
                    break
        except Exception:
            pass

    # Machine-id from /etc/machine-id (Linux)
    if Path("/etc/machine-id").exists():
        try:
            candidates.append(Path("/etc/machine-id").read_text().strip())
        except Exception:
            pass

    # D-Bus machine-id
    if Path("/var/lib/dbus/machine-id").exists():
        try:
            candidates.append(Path("/var/lib/dbus/machine-id").read_text().strip())
        except Exception:
            pass

    # Fallback to hostname
    candidates.append(platform.node())

    # Use the first available candidate
    for candidate in candidates:
        if candidate:
            return candidate

    # Ultimate fallback
    return str(uuid.uuid4())


def _detect_container() -> tuple[bool, str | None]:
    """Detect if running in a container and return container type."""
    # Check for .dockerenv file
    if Path("/.dockerenv").exists():
        return True, "docker"

    # Check cgroup for docker
    if Path("/proc/self/cgroup").exists():
        try:
            cgroup = Path("/proc/self/cgroup").read_text()
            if "/docker/" in cgroup:
                return True, "docker"
            if "/kubepods/" in cgroup:
                return True, "kubernetes"
            if "/lxc/" in cgroup:
                return True, "lxc"
        except Exception:
            pass

    # Check environment variables
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return True, "kubernetes"
    if os.getenv("DOCKER_CONTAINER"):
        return True, "docker"

    return False, None


def get_runtime_id() -> str:
    """Get a short runtime ID for use in file paths and configuration."""
    info = get_runtime_info()
    return info.runtime_id


def get_profile_path(base_dir: Path, platform: str) -> Path:
    """Get the runtime-specific profile path for a platform."""
    runtime_id = get_runtime_id()
    return base_dir / "runtime-profiles" / runtime_id / platform


def is_same_runtime(runtime_id: str) -> bool:
    """Check if the given runtime ID matches the current runtime."""
    return runtime_id == get_runtime_id()
