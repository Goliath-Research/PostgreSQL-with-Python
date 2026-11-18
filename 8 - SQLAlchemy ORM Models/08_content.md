# Module 8: SQLAlchemy ORM Models

This follows Module 7 Core: instead of selecting columns into result rows, select a mapped class into Python objects. The local fixture uses SQLite and requires only the course virtual environment with SQLAlchemy 2.0 and Marimo. It does not connect to PostgreSQL. These intentionally small mappings are not drop-in mappings or migrations for the `commerce` schema.

```powershell
python -m marimo check "8 - SQLAlchemy ORM Models/08_sqlalchemy_orm_models.py"
python -m unittest discover -s "8 - SQLAlchemy ORM Models/tests" -v
python -m marimo edit "8 - SQLAlchemy ORM Models/08_sqlalchemy_orm_models.py"
```

## Read the mapping

1. `DeclarativeBase` registers mapped classes and table metadata. `Mapped[int]` marks an ORM attribute; `mapped_column(primary_key=True)` designates row identity.
2. `ForeignKey("customers.customer_id")` constrains an order to reference an existing customer. The fixture enables SQLite foreign-key enforcement explicitly.
3. `relationship(back_populates=...)` pairs `Customer.orders` (a collection) with `Order.customer` (a scalar). It is not a database column or a substitute for a foreign key.

## Predict and verify

- Ada (1): orders 101 and 102, each with a back-reference to the exact customer object. Lin (2): empty order collection. ID 99: no customer, not an empty collection.
- Compare `Session.get(Customer, id)` with `Session.scalars(select(Customer)...).one()`. Both resolve to the same retained instance inside one Session; a separate Session gives another instance for the same row. Python `is` checks object identity, not equality of primary-key values.
- An identity map is not a cache of every SELECT. As a practice exercise, add `echo=True` in `fixture_engine()` and compare the SQL from the repeated primary-key lookup, filtered SELECT, and first relationship traversal. Module 9 covers loading strategies and transactional services in more detail.
