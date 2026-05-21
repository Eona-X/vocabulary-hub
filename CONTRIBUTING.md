# Contributing to Eona Vocabulary Services

Thanks for your interest in contributing! This document describes how to
propose changes — to the **code** of the Hub itself, or to the
**vocabularies** it hosts.

By participating, you agree to abide by our community standards: be
respectful, assume good intent, and prefer concrete suggestions over vague
criticism.

---

## Ways to contribute

- **Report a bug** — open a GitHub issue with steps to reproduce, expected
  vs. actual behaviour, and your environment.
- **Propose a feature** — open an issue first to discuss the use case before
  writing code.
- **Submit a vocabulary change** — propose a new ontology, SHACL shape, or
  SKOS concept scheme, or evolve an existing one (see
  [Vocabulary changes](#vocabulary-changes) below).
- **Improve documentation** — fixes to typos, examples, and clarifications
  are always welcome and don't require prior discussion.

## Development workflow

1. **Fork** the repository and create a topic branch from `main`:
   ```bash
   git checkout -b feat/short-description
   ```
2. **Make focused commits.** One logical change per commit, with a clear
   message (imperative mood, ≤72-char subject line).
3. **Add or update tests** covering the change.
4. **Run the checks locally** before opening a PR:
   ```bash
   # (project-specific commands to follow — e.g.)
   make lint
   make test
   ```
5. **Open a pull request** against `main`. Describe *what* changed and *why*,
   and link any related issues.

### Pull request expectations

- Keep PRs small and focused. Unrelated changes belong in separate PRs.
- CI must be green.
- At least one maintainer approval is required to merge.
- Maintainers may squash on merge; structure commits accordingly.

## Vocabulary changes

Because vocabularies are consumed by other systems, changes to them are
governed more strictly than code changes.

- **Additive changes** (new classes, properties, concepts) are generally safe
  and follow the standard PR flow.
- **Breaking changes** (renames, deletions, semantic shifts) require a
  version bump and a deprecation period. Open an issue to discuss first.
- Every vocabulary change must include:
  - Updated `owl:versionInfo` / `dcterms:modified`.
  - Human-readable rationale in the PR description.
  - Examples or test data demonstrating the new shape.

When in doubt, prefer **deprecation over deletion** and **new terms over
redefinition**.

## Coding standards

- Match the style of surrounding code.
- Prefer clear names and small functions over comments.
- Add comments only when the *why* is non-obvious.
- For RDF artifacts, use Turtle as the canonical serialization in the
  repository; other formats are generated.

## Reporting security issues

Please **do not** open public issues for security vulnerabilities. Instead,
contact the maintainers privately (see `SECURITY.md` when available) so the
issue can be addressed before disclosure.

## License and Developer Certificate of Origin

This project is licensed under the [Apache License 2.0](./README.md#license).
By submitting a contribution, you agree that:

1. Your contribution is licensed under the Apache License 2.0, and
2. You have the right to submit it under that license (i.e. it is your
   original work, or you have permission from the rights holder).

This is equivalent to the
[Developer Certificate of Origin](https://developercertificate.org/). Sign
your commits with `git commit -s` to make this explicit.

## Getting help

- Open a **Discussion** for questions and design conversations.
- Open an **Issue** for concrete bugs or proposals.

Thanks for helping make shared semantics a little easier for everyone.
