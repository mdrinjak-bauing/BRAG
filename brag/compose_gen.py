"""Generate docker-compose.override.yml from the project registry.

Each ADDITIONAL project's host folder is bind-mounted into the app container at
/projects/<slug>, so the watcher + bridge can reach every project's vault while
the program and the ~3 GB models stay a single shared container. The DEFAULT
project keeps the base compose `/vault` mount, so a single-project install needs
no override at all. Docker Compose merges docker-compose.override.yml
automatically, appending these mounts to the base service's volumes.

Safety: host paths are forward-slashed and quoted (spaces are fine); a path
containing '$' is SKIPPED with a visible comment, because Docker Compose would
interpolate it and mount the wrong/empty folder (same hazard the folder picker
already rejects). A project whose host path is missing/empty is skipped too, so
one unplugged drive never breaks `compose up` for the others.
"""

from pathlib import Path

OVERRIDE_NAME = "docker-compose.override.yml"


def render_override(projects: list[dict]) -> str:
    """Return the override YAML for the given registry projects."""
    mounts: list[str] = []
    skips: list[str] = []
    for proj in projects:
        slug = proj.get("slug")
        host = str(proj.get("host_path") or "").strip()
        if slug in (None, "", "default"):
            continue  # the default project uses the base /vault mount
        if not host:
            skips.append(f"      # SKIPPED {slug}: no host path recorded")
            continue
        if "$" in host:
            skips.append(f"      # SKIPPED {slug}: host path contains '$' (unsupported)")
            continue
        host_q = host.replace("\\", "/")
        mounts.append(f'      - "{host_q}:/projects/{slug}"')

    header = "# AUTO-GENERATED from projects.json by brag.compose_gen — do not edit.\n"
    if not projects:
        # No registry at all (a truly single-project install that never migrated):
        # a valid no-op override; the app keeps just the base /vault mount and the
        # bare 'brag' connector.
        return header + "services: {}\n"
    # As long as the registry EXISTS, bind it read-only into the app so the app's
    # claude_sync/watcher/bridge see EXACTLY the registered projects — INCLUDING a
    # default-only registry, so its connector stays the named 'brag-<folder>' and
    # never collapses to a phantom bare 'brag'. Additional projects also get their
    # vault bind-mounts. Compose appends these to the base service's volumes; the
    # base /vault mount stays for the default project.
    body = ["services:", "  app:", "    volumes:",
            '      - "./projects.json:/registry/projects.json:ro"']
    body.extend(mounts)
    body.extend(skips)
    return header + "\n".join(body) + "\n"


def write_override(workspace=None, projects=None) -> Path:
    """Write docker-compose.override.yml next to docker-compose.yml. Reads the
    live registry unless `projects` is supplied (tests)."""
    if projects is None:
        from brag import registry
        projects = registry.projects()
    path = Path(workspace or ".") / OVERRIDE_NAME
    path.write_text(render_override(projects), encoding="utf-8")
    return path
