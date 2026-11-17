# Pinned introductory-course source for Module 2

These local files remove the coding agent's dependency on access to a private repository.
They are exact copies from Goliath-Research/Introduction-to-Databases commit
af5182b90dc610d730449e9de7fc334542b9815c, retained under the adjacent MIT license.
This directory is source material and offline verification, NOT the completed PostgreSQL migration.

## Upstream Git blob identities

- 8 - Python Database Integration & Capstone/ecommerce_snapshot.py: 28a27f8b703e2e65de01a7521b5d5979034b6a82
- 1 - The Relational Model/messy_ecommerce_orders.csv: 1a67452f45edcdcdfb9fc1aa50a1c38877411e47
- LICENSE: bd1b06e8458a26976268c9d091b250b40ecd54c7

The helper uses the current SIX-table model: customers, products, warehouses, orders,
order_items, catalog_observations. It preserves integer-cent amounts and order-time
shipping snapshots; catalog observations are not measured inventory. The source has
observed_quantity, permits DELIVERED through application logic, and has no status CHECK.
Do not substitute the older seven-table normalization notebook.

## Offline commands, from the PostgreSQL repository root

```bash
python -m unittest discover -s source_course -p "test_*.py"
python "source_course/8 - Python Database Integration & Capstone/ecommerce_snapshot.py" rebuild source_course/baseline_bundle
python "source_course/8 - Python Database Integration & Capstone/ecommerce_snapshot.py" verify source_course/baseline_bundle
```

Rebuild deliberately fails if the destination directory exists. It creates
ecommerce_source.sqlite and source_manifest.json under contract
goliath-ecommerce-snapshot/v1. Imports do not create those files. A rebuilt baseline
is not a saved end-of-course session. Live exports must use the caller's chosen
connection and are labeled live_connection.

Expected baseline counts: customers 3, products 4, warehouses 3, orders 5, order_items 6,
catalog_observations 1. Exact historical line total: 131740 cents in unspecified currency.
Expected schema signature: 0653ff1441f8303cd2b1e3214dd3bf9880c1d0883bf96be3f1c5ee1b31192797.
The signature hashes the canonical JSON inventory including stored SQL; it is not a
general whitespace-insensitive schema-equivalence proof.

## Provenance boundaries

Module 8 generates source_row_id for application-created lines. It is a database key,
not universally verified CSV provenance, and may overlap an observation's identifier.
Do not infer lineage from ID coincidence, LAB- prefixes, or row counts.

The copied helper's exporter_commit inspects the CONTAINING checkout: here that is the
PostgreSQL repository, not the upstream introductory repository. Its source_commit=null
is intentional. The upstream revision above records the copied source; do not relabel
a live database as originating at that revision. Keep upstream files unchanged when
adding migration-specific wrappers or metadata. Reports and bundles can contain personal
data even without credentials; generated bundles must not be committed.

The helper and source bundle were smoke-tested during preparation. The new verification
suite must be run and its actual result recorded before this PR is considered ready.
PostgreSQL integration and the Module 2 notebook are separate implementation work.
