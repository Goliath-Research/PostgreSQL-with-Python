from sqlalchemy import CheckConstraint, ForeignKey, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload, sessionmaker


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    lines: Mapped[list["Line"]] = relationship(back_populates="order", order_by="Line.id")


class Line(Base):
    __tablename__ = "order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    quantity: Mapped[int] = mapped_column()
    order: Mapped[Order] = relationship(back_populates="lines")


def fixture_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    Base.metadata.create_all(engine)
    return engine


def place_order(sessions, quantities, evidence):
    if not quantities:
        raise ValueError("An order needs at least one line")
    with sessions.begin() as session:
        order = Order()
        session.add(order)
        session.flush()
        order_id = order.id
        evidence["id_after_flush"] = order_id
        for quantity in quantities:
            session.add(Line(order_id=order_id, quantity=quantity))
            session.flush()
            evidence["lines_flushed"] += 1
    return order_id


def loading_report(engine, sessions, eager):
    statements = []

    def capture(_conn, _cursor, sql, _params, _context, _many):
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with sessions() as session:
            statement = select(Order).order_by(Order.id)
            if eager:
                statement = statement.options(selectinload(Order.lines))
            orders = session.scalars(statement).all()
            rows = [{"id": order.id, "quantities": [line.quantity for line in order.lines]} for order in orders]
        return {"orders": rows, "select_count": len(statements), "sql": statements}
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def run_lab(invalid=False):
    engine = fixture_engine()
    sessions = sessionmaker(engine)
    try:
        for quantity in (1, 2, 3):
            place_order(sessions, [quantity], {"lines_flushed": 0})
        evidence = {"lines_flushed": 0}
        try:
            evidence["committed_id"] = place_order(sessions, [2, 0 if invalid else 4], evidence)
            evidence["outcome"] = "committed"
        except IntegrityError:
            if not invalid:
                raise
            evidence["outcome"] = "rolled back"
        with sessions() as session:
            evidence["persisted_attempt"] = session.get(Order, evidence["id_after_flush"]) is not None
            evidence["total_orders"] = session.scalar(select(func.count()).select_from(Order))
            evidence["total_lines"] = session.scalar(select(func.count()).select_from(Line))
        return {"transaction": evidence, "lazy": loading_report(engine, sessions, False),
                "selectin": loading_report(engine, sessions, True)}
    finally:
        engine.dispose()
