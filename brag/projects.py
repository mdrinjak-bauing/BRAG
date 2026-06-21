"""CLI to manage BRAG projects — the single orchestration point shared by the
"add project" launchers and the wizard's Projects page.

Run inside the one-shot setup container, which mounts the BRAG Assistent folder at
/workspace (read-write) and sets BRAG_REGISTRY=/workspace/projects.json:

  docker compose run --rm setup python -m brag.projects add "My Thesis" "D:/Arbeit/Thesis"
  docker compose run --rm setup python -m brag.projects remove my-thesis
  docker compose run --rm setup python -m brag.projects remove-interactive
  docker compose run --rm setup python -m brag.projects list
  docker compose run --rm setup python -m brag.projects migrate

It updates projects.json AND regenerates docker-compose.override.yml (next to the
registry). The host then runs `docker compose up -d` (to (re)mount the projects)
and the connector merge. Collection creation is left to the watcher's startup
reconcile, so this CLI needs no Qdrant connection.
"""

import sys

from brag import compose_gen, config, registry


def _regen_override() -> None:
    # Write the override next to the registry file (the BRAG Assistent folder, mounted
    # at /workspace in the setup container).
    compose_gen.write_override(workspace=registry.registry_path().parent)


def cmd_add(name: str, host_path: str) -> int:
    if not name.strip() or not host_path.strip():
        print("usage: projects add <name> <host_path>", file=sys.stderr)
        return 2
    try:
        rec = registry.register(name, host_path, config.COLLECTION_NAME)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _regen_override()
    print(rec["slug"])  # the host launcher reads this to name the connector
    return 0


def cmd_remove(slug: str, delete_index: bool = False) -> int:
    slug = slug.strip()
    rec = registry.get(slug)  # capture the collection BEFORE removing the record
    if not registry.remove(slug):
        print(f"no such project: {slug}", file=sys.stderr)
        return 1
    _regen_override()
    # The connector + mount go always (registry + override above); the Qdrant
    # collection only when explicitly requested. The project's documents on disk
    # are never touched here.
    if delete_index and rec and rec.get("collection"):
        try:
            from brag import storage
            client = storage.get_client()
            try:
                client.delete_collection(rec["collection"])
            finally:
                client.close()
            print(f"deleted index: {rec['collection']}")
        except Exception as e:  # noqa: BLE001 — index delete is best-effort
            print(f"warning: could not delete index {rec.get('collection')}: {e}",
                  file=sys.stderr)
    return 0


def cmd_remove_interactive() -> int:
    """Numbered picker for the uninstall launchers' [1] path: the user removes a
    connection by choosing '1'/'2' (not by typing a slug), and ANY project can be
    removed — INCLUDING the default. Runs in the one-shot setup container (it owns
    the registry + reaches Qdrant), so the same prompt works on Windows and macOS.
    Exit 0 = removed (host then re-mounts + re-syncs the connectors); 2 =
    cancel/invalid (host stops); 1 = removal error."""
    from brag import setup_core
    projs = registry.projects()
    if not projs:
        print("No projects are registered - nothing to remove here.")
        print("(To remove BRAG itself, choose the full uninstall.)")
        return 2
    if len(projs) == 1:
        # Removing the only project would empty the registry, which the connector
        # sync treats as a single-project install and re-adds a bare 'brag' - i.e.
        # NOT "no connections". Refuse and send the user to the full uninstall, so
        # the [1] path always means "keep BRAG + the others".
        only = setup_core.connector_key_for_project(projs[0])
        print(f"{only} is your only project. Removing a connection here is meant to")
        print("leave BRAG and your OTHER projects in place - but there are no others.")
        print("To remove BRAG entirely, cancel and choose the FULL uninstall instead.")
        return 2
    if not sys.stdin.isatty():
        # No interactive terminal was forwarded into the container - don't hang on
        # input(); point the user at the explicit, scriptable form instead.
        print("This picker needs an interactive terminal. List your projects with:")
        print("  docker compose run --rm setup python -m brag.projects list")
        print("then remove one by its slug:")
        print("  docker compose run --rm setup python -m brag.projects "
              "remove <slug> [--delete-index]")
        return 2
    print()
    print("Which connection do you want to remove?")
    for i, p in enumerate(projs, 1):
        key = setup_core.connector_key_for_project(p)
        print(f"  [{i}] {key}   (folder: {p.get('host_path', '')})")
    print("  [C] Cancel")
    try:
        choice = input("Choose a number (or C to cancel): ").strip()
    except EOFError:
        choice = ""
    if not choice or choice.lower() == "c":
        print("Cancelled - nothing was changed.")
        return 2
    try:
        n = int(choice)
        if n < 1:
            raise IndexError
        sel = projs[n - 1]
    except (ValueError, IndexError):
        print("Invalid choice - nothing was changed.")
        return 2
    slug = sel["slug"]
    key = setup_core.connector_key_for_project(sel)
    try:
        di = input(f"Also delete the search index for {key}? "
                   "Your documents stay. (y/N): ").strip().lower()
    except EOFError:
        di = ""
    rc = cmd_remove(slug, delete_index=(di == "y"))
    if rc == 0:
        # The host launcher greps this line to report what it just unwired.
        print(f"REMOVED\t{key}")
    return rc


def cmd_list() -> int:
    projects = registry.projects()
    if not projects:
        print("(no projects registered)")
        return 0
    for p in projects:
        print(f"{p['slug']}\t{p.get('name', '')}\t{p.get('host_path', '')}"
              f"\t{p.get('collection', '')}")
    return 0


def cmd_migrate() -> int:
    """One-time: turn a legacy single-project install into project 'default',
    reusing its existing VAULT_PATH + COLLECTION_NAME verbatim (no re-embed)."""
    from brag import setup_core
    if registry.projects():
        return 0  # already migrated / multi-project
    env = setup_core.read_existing_env()
    host_path = env.get("VAULT_PATH", "")
    collection = env.get("COLLECTION_NAME") or config.COLLECTION_NAME
    registry.synthesize_default(host_path, collection)
    _regen_override()
    print("default")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: projects {add|remove|list|migrate} ...", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "add" and len(rest) >= 2:
        return cmd_add(rest[0], rest[1])
    if cmd == "remove" and len(rest) >= 1:
        return cmd_remove(rest[0], delete_index="--delete-index" in rest)
    if cmd == "remove-interactive":
        return cmd_remove_interactive()
    if cmd == "list":
        return cmd_list()
    if cmd == "migrate":
        return cmd_migrate()
    print("usage: projects {add <name> <host_path>|remove <slug>|"
          "remove-interactive|list|migrate}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
