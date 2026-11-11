"""Contracts for the skills shipped as ordinary Azoic package data."""

import re
import tomllib
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import pytest
import yaml

SKILLS = ("azoic-modelling", "azoic-diagnostics", "azoic-tariff")
ROOT = files("azoic").joinpath(".agents", "skills")


def test_skill_bundle_names_and_release_versions():
    assert sorted(path.name for path in ROOT.iterdir()) == sorted(SKILLS)
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert project["project"]["version"] == version("azoic")
    for name in SKILLS:
        frontmatter = yaml.safe_load(ROOT.joinpath(name, "SKILL.md").read_text().split("---")[1])
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) and len(name) < 64
        assert frontmatter["name"] == name
        assert isinstance(frontmatter["description"], str) and frontmatter["description"].strip()
        assert frontmatter["metadata"]["azoic-version"] == project["project"]["version"]


@pytest.mark.parametrize("name", SKILLS)
def test_skill_references_are_bundled_and_discoverable(name):
    skill = ROOT.joinpath(name)
    entry = skill.joinpath("SKILL.md")
    references = list(skill.joinpath("references").iterdir())
    assert references
    linked = set()
    for document in [entry, *references]:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            assert not target.startswith(("/", "http:", "https:", "../"))
            resolved = document.parent.joinpath(target.split("#")[0])
            assert resolved.is_file(), (document, target)
            linked.add(resolved.name)
    assert {path.name for path in references} <= linked
    metadata = yaml.safe_load(skill.joinpath("agents", "openai.yaml").read_text())
    assert metadata.get("policy", {}).get("allow_implicit_invocation", True)
    assert not metadata.get("dependencies")
    assert 25 <= len(metadata["interface"]["short_description"]) <= 64
