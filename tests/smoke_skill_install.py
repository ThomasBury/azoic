"""Check selected Library Skills installation in a fresh installed user project.

Run with the project's Python; pass --copy on Windows. Library Skills stays in
uvx's environment and is not added to the user's or Azoic's runtime dependencies.
"""

import json
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

import yaml

installed = distribution("azoic")
names = {"azoic-modelling", "azoic-diagnostics", "azoic-tariff"}
command = ["uvx", "--from", "library-skills==0.0.20", "library-skills"]
scan = json.loads(subprocess.check_output([*command, "scan", "--json"], text=True))
discovered = {skill["name"]: skill for skill in scan["skills"] if skill["package"] == "azoic"}
assert set(discovered) == names, scan
assert not scan["warnings"], scan["warnings"]
for name, skill in discovered.items():
    assert skill["version"] == installed.version
    source = Path(installed.locate_file(f"azoic/.agents/skills/{name}")).resolve()
    assert Path(skill["path"]).resolve() == source
    metadata = yaml.safe_load((source / "SKILL.md").read_text(encoding="utf-8").split("---")[1])
    assert metadata["metadata"]["azoic-version"] == installed.version

copy = sys.argv[1:] == ["--copy"]
assert sys.argv[1:] in ([], ["--copy"])
target = Path(".agents/skills")
assert not target.exists(), "use a fresh project to verify selected installation"
selection = [argument for name in sorted(names) for argument in ("--skill", name)]
subprocess.run(
    [*command, "install", "--yes", *selection, *(["--copy"] if copy else [])], check=True
)
assert {path.name for path in target.iterdir()} == names
for name in names:
    destination = target / name
    source = Path(discovered[name]["path"])
    assert destination.is_symlink() is not copy
    if not copy:
        assert destination.resolve() == source.resolve()
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    installed_files = {
        path.relative_to(destination) for path in destination.rglob("*") if path.is_file()
    }
    assert installed_files == source_files
    for relative in source_files:
        assert (destination / relative).read_bytes() == (source / relative).read_bytes()
print(f"Azoic {installed.version}: discovered and installed all three skills; copy={copy}")
