from sqlalchemy import ForeignKey, String, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    orders: Mapped[list["Order"]] = relationship(back_populates="customer", order_by="Order.order_id")


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"))
    status: Mapped[str] = mapped_column(String(20))
    customer: Mapped[Customer] = relationship(back_populates="orders")


def fixture_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    return engine


def run_lab(customer_id):
    engine = fixture_engine()
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as seed, seed.begin():
            seed.add_all([
                Customer(customer_id=1, name="Ada", orders=[
                    Order(order_id=101, status="placed"), Order(order_id=102, status="shipped")]),
                Customer(customer_id=2, name="Lin"),
            ])
        with Session(engine) as first, Session(engine) as second:
            customer = first.get(Customer, customer_id)
            if customer is None:
                return {"found": False, "customer_id": customer_id}
            via_select = first.scalars(select(Customer).where(Customer.customer_id == customer_id)).one()
            items = [{"order_id": order.order_id, "status": order.status,
                      "customer_id": order.customer_id, "back_reference_is_customer": order.customer is customer}
                     for order in customer.orders]
            other = second.get(Customer, customer_id)
            return {"found": True, "customer_id": customer.customer_id, "name": customer.name,
                    "orders": items, "same_session_get_is_same_object": first.get(Customer, customer_id) is customer,
                    "same_session_select_is_same_object": via_select is customer,
                    "other_session_is_same_object": other is customer,
                    "other_session_has_same_key": other is not None and other.customer_id == customer.customer_id}
    finally:
        engine.dispose()
