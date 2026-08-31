"""BRAG must import on whichever mcp major version is installed.

mcp 2.x renamed FastMCP to MCPServer and left a tombstone module behind:
`mcp/server/fastmcp.py` raises ModuleNotFoundError with the migration hint. Two
import lines in BRAG point at it, so on mcp 2.x the MCP server and the thin
client fail to import at all — the connector simply never starts.

The unit CI job installs mcp UNPINNED while users get requirements.txt's pin, so
what CI proves and what users run are not the same thing. That is the reason
this went unnoticed: only the e2e job touches these modules.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_the_mcp_server_imports_on_the_installed_mcp():
    import brag.mcp_server as s
    assert s.mcp is not None
    assert hasattr(s.mcp, "tool") and hasattr(s.mcp, "run")


def test_the_thin_client_imports_on_the_installed_mcp():
    import brag.mcp_client as c
    assert c.mcp is not None
    assert hasattr(c.mcp, "tool") and hasattr(c.mcp, "run")


def test_the_server_still_registers_every_tool():
    """A shim that imports but registers nothing would pass the tests above and
    leave the assistant with no tools at all."""
    import re
    quelle = (REPO / "brag" / "mcp_server.py").read_text(encoding="utf-8")
    erwartet = len(re.findall(r"^@mcp\.tool\(\)", quelle, re.M))
    assert erwartet >= 20, f"only {erwartet} @mcp.tool() decorators found — parse error?"
    import asyncio

    import brag.mcp_server as s
    werkzeuge = asyncio.run(s.mcp.list_tools())
    assert len(werkzeuge) == erwartet, (
        f"{erwartet} tools are decorated but {len(werkzeuge)} are registered"
    )


def test_ci_installs_the_same_mcp_users_get():
    """The unit job pip-installed mcp unpinned, so it silently tested a
    different major version than requirements.txt ships. That is exactly how an
    import break reaches users through green CI."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    lose = [z.strip() for z in ci.splitlines()
            if "pip install" in z and re.search(r"\bmcp\b(?!==)", z)]
    assert not lose, f"mcp is installed unpinned in CI: {lose}"

