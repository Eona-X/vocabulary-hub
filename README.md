# Eona Vocabulary Services

An open source **Vocabulary Hub** for publishing, governing, and consuming
shared vocabularies (ontologies, schemas, reference data) across organizations
and data spaces.

Licensed under the [Apache License 2.0](#license).

## Overview

> A Vocabulary Hub is to **meaning** what a package registry is to **code**:
> a governed, versioned, discoverable repository of the shared definitions
> that make data exchange possible. It does not move data — it makes the
> data that *does* move understandable to everyone involved.

This project provides a reference implementation of such a hub, suitable for
use inside an organization, between partners, or as the vocabulary backbone
of a federated data space.

---

## What is a Vocabulary Hub?

A Vocabulary Hub is a **trusted, centrally accessible service that hosts the
vocabularies needed to describe and exchange data** in a data space. In
practice, it is the place where participants look up:

- **Ontologies** — formal definitions of concepts and their relationships
  (typically expressed in RDFS/OWL).
- **Schemas** — structural descriptions of data (e.g. SHACL shapes, JSON
  Schema, XSD).
- **Reference data** — controlled vocabularies, code lists, and taxonomies
  (e.g. SKOS concept schemes).

Without a Vocabulary Hub, every participant must agree bilaterally on the
meaning and structure of the data they exchange. With one, vocabularies are
**published once, versioned, governed, and discoverable by everyone**, so
data producers and consumers share the same semantics by construction.

### Why it matters

- **Semantic interoperability.** Two systems can only meaningfully exchange
  data if they share definitions. The Hub is the source of truth for those
  definitions.
- **Discoverability.** Participants can search and browse vocabularies before
  modelling their own data, encouraging reuse over reinvention.
- **Governance.** Vocabularies have owners, lifecycles, and version histories.
  Changes are reviewed rather than silently propagated.
- **Machine-readability.** Vocabularies are served in standard formats
  (Turtle, JSON-LD, RDF/XML, …) so they can be consumed directly by
  applications, validators, and reasoners.



## Features

- Publish and version ontologies, SHACL shapes, and SKOS vocabularies.
- Content negotiation across standard RDF serializations
  (Turtle, JSON-LD, N-Triples, RDF/XML).
- SPARQL endpoint for querying hosted vocabularies.
- Human-readable documentation generated from the vocabularies themselves.
- Role-based governance: editors, reviewers, publishers.
- REST API for programmatic access and CI/CD integration.

## Getting started

```bash
# Clone and run
git clone <this-repo>
cd eona_vocabulary_services
```

## Documentation

See the [`docs/`](./docs) directory for architecture decisions and usage
guides, including
[ADR-001: Triplestore stack selection](./001-triplestore-stack-selection.md).

---

## References

This implementation is aligned with the Vocabulary Hub concept defined by the
**International Data Spaces Association (IDSA)** in the IDS Reference
Architecture Model (IDS-RAM) 4.0:

- [IDS-RAM 4.0 — System Layer §3.5.6 Vocabulary Hub](https://github.com/International-Data-Spaces-Association/IDS-RAM_4_0/blob/main/documentation/3_Layers_of_the_Reference_Architecture_Model/3_5_System_Layer/3_5_6_Vocabulary_Hub.md)

Relevant standards:

- [W3C RDF 1.1](https://www.w3.org/TR/rdf11-concepts/)
- [W3C OWL 2](https://www.w3.org/TR/owl2-overview/)
- [W3C SHACL](https://www.w3.org/TR/shacl/)
- [W3C SKOS](https://www.w3.org/TR/skos-reference/)
- [W3C SPARQL 1.1](https://www.w3.org/TR/sparql11-overview/)

## Contributing

Contributions are welcome. Please open an issue to discuss substantial
changes before submitting a pull request.

## License

Copyright the Eona Vocabulary Services contributors.

Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this project except in compliance with the License. You may obtain a
copy of the License at:

<http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an **"AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND**, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.
