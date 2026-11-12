# Install Azoic skills for your agent

In your project with Azoic installed, run:

```bash
uvx library-skills
```

Select `azoic-modelling`, `azoic-diagnostics` and `azoic-tariff`, then select
`.agents/skills` as the destination. Library Skills discovers guidance bundled
with the installed package. It runs in its own environment and is not an Azoic
runtime dependency. See its [installation behavior](https://library-skills.io/use/).

**Azoic 0.6.0 is published and includes the skill bundle.** The published 0.5.0
package has no skills. From a project that uses Azoic 0.6.0:

```bash
uv add azoic==0.6.0
uv run python -c 'from importlib.metadata import version; print(version("azoic"))'
uvx library-skills
```

The [first-model starter](first-model.md) uses Azoic 0.6.0.
Installing skills does not upgrade Azoic or authorize a model fit.

## Choose a skill by the job

| Skill | Use it for | Keep separate |
| --- | --- | --- |
| `azoic-modelling` | Prepare development data, configure mappings, fit/tune candidates and save runs | Reserved final data stays outside experimentation |
| `azoic-diagnostics` | Interpret existing predictions/runs, ranking, calibration, segments and stability | Diagnosis does not authorize refitting or recalibration |
| `azoic-tariff` | Review/revise fitted tariffs, export, evaluate frozen selections or explicitly refit production | Export, final evaluation and production refitting are distinct operations |

Automatic discovery is enabled. You can also explicitly request a skill, such as
“Use `$azoic-diagnostics` to explain these existing rates without changing them.”
The short entry points load detailed API recipes only when needed. Those references
are bundled within each skill; no checkout, sibling skill or MCP service is required.
Skills guide agent behavior; they are not enforcement or actuarial approval.

## Other agents and copies

For Claude Code, select `.claude/skills` in the interactive installer. The
`--claude` installation option adds that destination alongside `.agents/skills`.
If your environment cannot create symlinks, including Windows without the needed
symlink permissions, use:

```bash
uvx library-skills install --copy
```

Select the same three skills. Linked skills follow package updates at that path;
rerun Library Skills if an environment move breaks the links. Copies do not update
with the package. Preserve any local edits, remove only the old copied Azoic skill
folders you intend to replace, and reinstall copies after updating Azoic. The tool
does not automatically remove copied directories.

For reproducible selected installation, the checks pin Library Skills **0.0.20**:

```bash
uvx --from library-skills==0.0.20 library-skills scan --json
uvx --from library-skills==0.0.20 library-skills install --yes --skill azoic-modelling --skill azoic-diagnostics --skill azoic-tariff
```

Add `--copy` to the installation command for copies, or `--claude` to include
Claude Code. The scan reports each skill's package, version and source path.
Confirm all three belong to your installed Azoic distribution before using them.

## Version and release checks

Each skill declares string metadata `azoic-version: "0.6.0"`. Agents inspect
`importlib.metadata.version("azoic")` in the user's project before following
version-specific recipes. A mismatch identifies stale guidance and stops those
recipes; it must not silently upgrade dependencies. This also catches old copies.
Saved model artifacts separately require trust and matching Python/dependency
versions: loading pickle can execute code before its version validation.

The canonical folders live under `src/azoic/.agents/skills/`, following
[Library Skills' Python layout](https://library-skills.io/create/). The existing
build backend includes them as package data in wheel and source distributions;
there is no custom installer or installation hook. Their structure follows
[OpenAI's skill guidance](https://learn.chatgpt.com/docs/build-skills).

For each release, reconcile all three skill-version strings with package metadata,
review affected recipes, validate the skills, and run the packaged-resource and
installed recipe checks. The checkout-wheel starter matrix checks selected Linux
symlinks and Windows copies with Library Skills 0.0.20. Live agent trials remain
outside routine CI; scripted acceptance does not replace M62 practitioner observation.
