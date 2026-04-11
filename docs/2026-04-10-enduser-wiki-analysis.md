# Enduser Wiki Analysis

## Purpose

`enduser-wiki` starts as a fork of `CodeWiki`, but the target problem is different.

`CodeWiki` is optimized for repository-level documentation:
- module decomposition
- code/component summaries
- architecture-aware markdown
- repository hierarchy and diagrams

`enduser-wiki` is intended to generate product-facing, transaction-oriented documentation from code-first evidence, validated by runtime UI evidence.

The documentation target is not:
- "what modules exist?"
- "what classes call which functions?"

The documentation target is:
- what entities exist in the product
- what pages expose them
- what fields appear on those pages
- what transactions users can execute
- what validations, rules, permissions, handlers, APIs, and downstream effects those fields and transactions trigger

## Why Fork CodeWiki

`CodeWiki` is a strong base for this direction because it already provides:
- repository parsing and dependency analysis
- hierarchical decomposition for large codebases
- agentic documentation generation
- markdown and HTML generation
- diagram-aware generation workflows
- incremental generation concepts

Those capabilities are useful for the code-side of the problem.

However, `CodeWiki` is still module-centric. It does not natively model:
- pages
- screens
- fields
- navigation
- runtime interactions
- transactions as first-class documentation objects

So the fork strategy is:
- keep the code decomposition strengths
- add a UI/runtime evidence layer
- introduce a new YAML-first canonical model
- render markdown catalogs from that model

## Source-of-Truth Decisions

The design decisions behind this fork are:

- **Code first**
  Code is the authoritative source for behavior, validation, rules, payloads, handlers, persistence, and functional impact.

- **Screenshots as validation**
  Screenshots do not define behavior. They confirm what is actually visible and how it is presented to the user.

- **Runtime UI evidence**
  Playwright crawl data and network traces provide observable evidence for:
  - page existence
  - visible controls and fields
  - navigation transitions
  - form actions
  - request/response side effects

- **YAML first**
  Canonical generated documentation should live in structured YAML, then render to markdown and HTML.

- **Three linked catalogs**
  All of these are first-class outputs:
  - entity catalog
  - page catalog
  - transaction catalog

## Documentation Objects

The core documentation model should include these object types:

- `Entity`
- `Page`
- `Field`
- `Transaction`
- `ValidationRule`
- `Action`
- `Transition`
- `ApiOperation`
- `Handler`
- `PermissionRule`
- `Evidence`

This is broader than CodeWiki's component/module model because product understanding requires domain and interaction objects, not just code objects.

## Canonical Relationship Model

Relationships should be stored explicitly instead of being implicit in prose.

Examples:

- `entity -> appears_on -> page`
- `entity -> affected_by -> transaction`
- `entity -> represented_by -> field`
- `page -> contains -> field`
- `page -> participates_in -> transaction`
- `page -> navigates_to -> page`
- `field -> belongs_to -> entity`
- `field -> appears_on -> page`
- `field -> used_in -> transaction`
- `field -> triggers -> validation_rule`
- `field -> maps_to -> api_operation`
- `field -> maps_to -> handler`
- `field -> maps_to -> persistence_target`
- `transaction -> starts_on -> page`
- `transaction -> includes -> action`
- `transaction -> updates -> entity`
- `transaction -> invokes -> api_operation`
- `transaction -> invokes -> handler`
- `transaction -> requires -> permission_rule`

These relationships are the backbone for all catalogs and rendered views.

## Catalog Goals

### Entity Catalog

The entity catalog should answer:
- what business object is this
- where does it appear
- which fields represent it
- which transactions create, update, search, submit, approve, or cancel it
- what APIs, handlers, and persistence targets it maps to

Entity pages should include:
- purpose
- attributes
- page usage
- field mappings
- transaction usage
- backend traceability
- evidence

### Page Catalog

The page catalog should answer:
- what page/screen is this
- what its purpose is
- what fields and actions it exposes
- how users navigate into and out of it
- what transactions it participates in
- what code and APIs support it

Page pages should include:
- route/url
- title/labels
- screenshot references
- sections/regions
- fields
- actions
- transitions
- related entities
- related transactions
- code evidence

### Transaction Catalog

The transaction catalog should answer:
- what task the user is performing
- what steps are involved
- what pages are traversed
- what fields are touched
- what validations occur
- what APIs and handlers run
- what entities change
- what failure paths exist

Transaction pages should include:
- goal
- actor
- preconditions
- ordered steps
- pages traversed
- fields used
- validations
- backend calls
- entity impact
- side effects
- evidence

## Field Documentation Depth

Field documentation should be layered.

### Operational layer
- label
- control type
- required/optional
- editable/read-only
- default value
- visible/hidden conditions
- pages where it appears
- transactions where it is used

### Behavioral layer
- validation rules
- formatting rules
- source of values
- computed/derived behavior
- payload mappings
- handler mappings
- permission impact
- state changes triggered by edits or submission

### Full traceability layer
- downstream reports
- notifications
- integration impact
- audit/history impact
- exact code evidence links supporting each claim

The system should not require every field to reach full traceability if the evidence does not support it cleanly. Coverage should be explicit.

## Evidence Sources

The target ingestion model uses four evidence classes:

### 1. Static code

Used for:
- routes
- components
- handlers
- validators
- DTOs
- models
- persistence mappings
- permissions
- downstream side effects discoverable in code

This is where CodeWiki contributes most.

### 2. Playwright crawl

Used for:
- page discovery
- visible controls
- DOM/accessibility structure
- navigation transitions
- click paths
- form flows
- route-level runtime evidence

This is the primary runtime UI collector.

### 3. Screenshots

Used for:
- confirming visible page state
- confirming labels and grouping
- validating that extracted fields are actually visible
- adding human-readable evidence to rendered docs

Screenshots are validators and presentation artifacts, not the behavior source of truth.

### 4. Runtime/network traces

Used for:
- actual request paths
- payload structures
- submit/search/update/approve effects
- transaction-level API evidence
- observed state changes across steps

This is essential for transaction docs that go beyond static page descriptions.

## Proposed Pipeline

### Stage 1: Code-side extraction

Adapt the CodeWiki dependency and hierarchy pipeline to produce structured code evidence for:
- routes
- UI components
- backend handlers
- validators
- data models
- APIs
- persistence targets
- permission checks

### Stage 2: UI/runtime extraction

Add a Playwright crawler that captures:
- route inventory
- page titles
- accessibility tree
- visible fields and controls
- action elements
- page-to-page transitions
- screenshots
- network requests

### Stage 3: Evidence alignment

Merge the static and runtime worlds:
- align page routes with frontend modules
- align field labels with internal field names and model attributes
- align actions with handlers and API operations
- align navigation with transaction candidates

### Stage 4: Transaction synthesis

Build transaction records from:
- observed page transitions
- form submissions
- code handlers and payload mappings
- entity updates

This is the key move beyond graph-only or module-only documentation.

### Stage 5: YAML generation

Emit canonical YAML artifacts for:
- entities
- pages
- fields
- transactions
- relationships
- evidence

### Stage 6: Validation

Run deterministic validation:
- schema validation
- referential integrity
- missing evidence checks
- duplicate object checks
- unsupported-claim checks
- contradiction checks between code and runtime evidence

### Stage 7: LLM judge

Use an LLM judge to score:
- completeness
- clarity
- traceability
- contradiction risk
- evidence quality
- coverage quality per catalog

### Stage 8: Adversarial review

Use a second agent to challenge:
- unsupported inferences
- missing fields
- missing transitions
- incorrect entity mappings
- overstated transaction claims
- weak field-impact claims

### Stage 9: Markdown rendering

Render YAML into:
- entity catalog pages
- page catalog pages
- field pages
- transaction pages
- relationship indexes
- overview landing pages

## Why YAML Instead of Markdown-First

Markdown is good for reading and publishing, but poor as canonical machine-checked state.

YAML is better for:
- validation
- referential integrity
- judge pipelines
- diffable structured changes
- deterministic rendering
- graph/index generation

Markdown should be a view layer over YAML, not the primary store.

## Proper Relationship Between CodeWiki and Enduser Wiki

The correct architecture is not "rename CodeWiki and keep going".

The correct architecture is:

- **CodeWiki subsystem**
  Repository analysis, decomposition, component summaries, code-side evidence extraction

- **Enduser Wiki product-doc layer**
  Entities, pages, fields, transactions, and evidence alignment

- **Runtime UI subsystem**
  Playwright crawling, screenshots, DOM/accessibility extraction, network tracing

- **Documentation synthesis layer**
  YAML objects, validation, judge, adversarial review, markdown render

This fork should evolve from module-first repo docs to evidence-based product documentation.

## Initial Implementation Direction

The first implementation slices should avoid trying to build the full system at once.

Recommended order:

1. Define YAML schemas for `Entity`, `Page`, `Field`, `Transaction`, `Relation`, and `Evidence`
2. Add deterministic validators for schema and relationship integrity
3. Build Playwright-based page/field/navigation extraction
4. Add screenshot capture and page evidence binding
5. Add code-to-page and code-to-field mapping
6. Render initial markdown catalogs from YAML
7. Add transaction synthesis
8. Add judge and adversarial review pipelines

## Fork Naming Rationale

The repository name `enduser-wiki` is appropriate because the output is meant to explain a product in user-facing operational terms, even though the evidence remains code-first.

This is not limited to:
- developers reading code structure
- architecture diagrams
- internal module summaries

It is aimed at:
- product understanding
- implementation analysis
- field impact analysis
- workflow documentation
- transaction traceability

## Summary

`enduser-wiki` should become a code-first, evidence-backed documentation system that produces three linked catalogs:
- entities
- pages
- transactions

Fields are not a side note. They are a first-class bridge between UI, business meaning, and backend behavior.

The fork should use:
- CodeWiki for code analysis and hierarchical decomposition
- Playwright for runtime UI and navigation evidence
- screenshots for validation and presentation
- runtime/network traces for transaction evidence
- YAML as canonical output
- markdown as rendered output
- validation, LLM judge, and adversarial review as publication gates
