# Changelog

## Unreleased

### Features

* add out-of-the-box expectation guard for pre-handoff agent verification
* add `etg serve` MCP server with schema-gated alignment and conflict tools
* publish agent discoverability through `ai-catalog.json`

### Bug Fixes

* harden SQLite ledger concurrency with WAL mode and busy timeouts
* close warning-producing registry, broker, router, and hydration resources

## [1.7.2](https://github.com/nyabutid/entigram/compare/v1.7.1...v1.7.2) (2026-06-21)


### Bug Fixes

* eliminate PyPI index race condition in homebrew release script ([a211b37](https://github.com/nyabutid/entigram/commit/a211b379683b6adf852100d1d4435a5f80394ca3))
* use local repo root to avoid PyPI index race condition ([0e95d74](https://github.com/nyabutid/entigram/commit/0e95d7420f6684b5afc4ed5c3ceb02d4cdbf44b4))

## [1.7.1](https://github.com/nyabutid/entigram/compare/v1.7.0...v1.7.1) (2026-06-21)


### Bug Fixes

* generate homebrew formula resources using poet ([01ecd5e](https://github.com/nyabutid/entigram/commit/01ecd5e1cb54547fc8ea75643c20595f0cf99819))
* generate homebrew formula resources using poet ([1173fa7](https://github.com/nyabutid/entigram/commit/1173fa77e0e3b7fe926e4a1273aeebcb9981ebad))

## [1.7.0](https://github.com/nyabutid/entigram/compare/v1.6.0...v1.7.0) (2026-06-21)


### Features

* sign audit bundles and clarify versions ([be12d03](https://github.com/nyabutid/entigram/commit/be12d0357b1098abe7426b534bbc10a9c3c208e3))


### Bug Fixes

* dynamically read version from pyproject.toml in tests ([309c43d](https://github.com/nyabutid/entigram/commit/309c43d89e0314e6a08d1eb519678ece52bf681d))
* sync requirements.txt for CI build ([cf01b76](https://github.com/nyabutid/entigram/commit/cf01b760ff4e1a0a2e60f06d49ced56e97e2906d))
* update hardcoded version 1.6.0 to 1.7.0 in tests ([4c5c7d9](https://github.com/nyabutid/entigram/commit/4c5c7d9be24a5c05e72844c43b68ca0b5c6b8c0b))

## [1.6.0](https://github.com/nyabutid/entigram/compare/v1.5.0...v1.6.0) (2026-06-21)

### Features

* add audit bundle and maintainer docs ([9c4840e](https://github.com/nyabutid/entigram/commit/9c4840ef4d037c6fcfead86101505283c0f88842))
* Entigram 1.6 introduces signed audit bundles for portable governance evidence.
* Document the MCP gate contract for `etg_get_schemas`, `etg_propose_alignment`, and `etg_log_conflict`.
* Add a deterministic Immutable Gate smoke test for schema discovery, hallucination rejection, ledger writes, delivery anchoring, and audit export.
* Keep the CLI/MCP runtime headless by default while publishing an optional Streamlit UI extra.

## [1.5.0](https://github.com/nyabutid/entigram/compare/v1.4.1...v1.5.0) (2026-06-20)


### Features

* deterministic ontology generation and change impact analysis ([dad7c8d](https://github.com/nyabutid/entigram/commit/dad7c8d9bf0f55813f7f58488361ee5580cfe85a))
* deterministic ontology generation and change impact analysis ([38ae72f](https://github.com/nyabutid/entigram/commit/38ae72f1936a2bc586df37907d311f844e465a6a))
* harden MCP gate contract ([4c52320](https://github.com/nyabutid/entigram/commit/4c5232011b9c0735310a544c67a2495d36476690))
* inject RelationalAlgebraGuard into etg_propose_alignment MCP handler ([af00ada](https://github.com/nyabutid/entigram/commit/af00ada789e1e3eaa9adbbb65228959dd11df0fb))
* model canonical cross-agent governance policy ([b4b480e](https://github.com/nyabutid/entigram/commit/b4b480ed85e6d8c95d0f9c90f3fc8ad343d75ab3))


### Bug Fixes

* correct pre-handoff governance order ([cb0aa04](https://github.com/nyabutid/entigram/commit/cb0aa04764294b33526e862ea8c269163c03a596))
* harden impact analysis and alignment precedence ([98880ca](https://github.com/nyabutid/entigram/commit/98880ca7d62d98425380bd65cb90d8c1dc8387b7))

## [1.4.1](https://github.com/nyabutid/entigram/compare/v1.4.0...v1.4.1) (2026-06-20)


### Bug Fixes

* support pyproject-only release versioning ([2ecc1cf](https://github.com/nyabutid/entigram/commit/2ecc1cfd7f304a3d8aeed8021e4321acaf4c3195))
* support pyproject-only release versioning ([d667780](https://github.com/nyabutid/entigram/commit/d667780ed2d94c1e051acf1693a4dd0e0a1e5432))

## [1.4.0](https://github.com/nyabutid/entigram/compare/v1.3.3...v1.4.0) (2026-06-20)


### Features

* add zero-trust MCP server ([0c5e3a3](https://github.com/nyabutid/entigram/commit/0c5e3a358757239dacea081936a2abae62b1379f))
* add zero-trust MCP server ([ee6f09c](https://github.com/nyabutid/entigram/commit/ee6f09c3fb4c89da41e3eecc8ca7cf952c31f98d))

## [1.3.3](https://github.com/nyabutid/entigram/compare/v1.3.2...v1.3.3) (2026-06-18)


### Bug Fixes

* update homebrew tap from pypi metadata ([2851af3](https://github.com/nyabutid/entigram/commit/2851af39c860a83748b0c96f173297f32dc938a1))
* update homebrew tap from pypi metadata ([adc332f](https://github.com/nyabutid/entigram/commit/adc332f832879ce5aa0e9d8727ecfd342f4790f3))

## [1.3.2](https://github.com/nyabutid/entigram/compare/v1.3.1...v1.3.2) (2026-06-18)


### Bug Fixes

* model release PR governance rules ([4360c02](https://github.com/nyabutid/entigram/commit/4360c02ef375c9b49186bbd9aa574ce4f47626e7))
* model release PR governance rules ([98bbbdd](https://github.com/nyabutid/entigram/commit/98bbbdd73a99ebb625592ebe64fd3ee4539dc1cb))

## [0.3.0](https://github.com/nyabutid/entigram/compare/v0.2.2...v0.3.0) (2026-06-04)


### Features

* add expectation guard for pre-handoff agent verification ([562dd72](https://github.com/nyabutid/entigram/commit/562dd72107d49b13f51d951cbaa75615222e2ded))
* out-of-the-box expectation guard for pre-handoff agent verification ([10d2471](https://github.com/nyabutid/entigram/commit/10d24712d5b79734a0f9205ea8fd6d9b30bde108))

## [0.2.2](https://github.com/nyabutid/entigram/compare/v0.2.1...v0.2.2) (2026-06-04)


### Bug Fixes

* broaden homebrew formula detection ([171671e](https://github.com/nyabutid/entigram/commit/171671e5e031d419b7c393209092edf4d8f59761))
* broaden homebrew formula detection ([f4fede4](https://github.com/nyabutid/entigram/commit/f4fede43d4a8ca9de94ca659e67fff20cd399b41))

## [0.2.1](https://github.com/nyabutid/entigram/compare/v0.2.0...v0.2.1) (2026-06-04)


### Bug Fixes

* resolve homebrew formula path dynamically ([c88adbd](https://github.com/nyabutid/entigram/commit/c88adbd3eaaf8423f28d4e63bc5fc489dd0abb87))
* resolve homebrew formula path dynamically ([5e3709c](https://github.com/nyabutid/entigram/commit/5e3709c9b6b35443f63c47fc00a055419fd41e21))

## [0.2.0](https://github.com/nyabutid/entigram/compare/v0.1.0...v0.2.0) (2026-06-04)


### Features

* add modern Entigram logo assets ([dab8f99](https://github.com/nyabutid/entigram/commit/dab8f9925a69418c849d7235aaf249e301cc6897))
* add modern Entigram logo assets ([43daa34](https://github.com/nyabutid/entigram/commit/43daa349b56fc7452aebe8311643ce987280dd13))
* add Ollama launch option selection ([3853b95](https://github.com/nyabutid/entigram/commit/3853b95cef8ecf0d2c1a0b23d21318b9eb7c7c83))
* close indispensability gap — learnings, trust score, E2T mapping, session proposals ([3203725](https://github.com/nyabutid/entigram/commit/3203725d6f4d797fa490122c0c945e74c7c04df3))
* commissioner companion features — evidence ledger, delivery snapshots, improvement proposals, Blocked state, CLI deliver/resolve/improve ([5eb7447](https://github.com/nyabutid/entigram/commit/5eb7447800e52ad944608c96b9db5cb777cb4a6a))


### Documentation

* add workspace alignment check to agent initialization step ([3e6204f](https://github.com/nyabutid/entigram/commit/3e6204f6f0783cf145482dad107b10edfe4a627d))

## 0.1.0 (2026-06-03)


### Bug Fixes

* align tests with federated routing guards ([2c8ed5e](https://github.com/nyabutid/entigram/commit/2c8ed5e6dd4ad246253535378cb8312256aefc6b))
* align tests with federated routing guards ([d48c969](https://github.com/nyabutid/entigram/commit/d48c969b887fcd55df9a76aa43a1bcaf69cfa393))

## [0.0.1](https://github.com/nyabutid/entigram/releases/tag/v0.0.1) (2026-06-02)

### Chore
* Initialize Entigram public baseline.
