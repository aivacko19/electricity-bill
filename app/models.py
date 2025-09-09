from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship


class Customer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    address: str
    email: str
    default_meter_id: Optional[int] = Field(default=None, foreign_key="meter.id")

    meters: List["Meter"] = Relationship(
        back_populates="customer",
        sa_relationship_kwargs={"foreign_keys": "[Meter.customer_id]"}
    )
    default_meter: Optional["Meter"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Customer.default_meter_id]"}
    )
    invoices: List["Invoice"] = Relationship(back_populates="customer")


class Meter(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    serial_number: str | None = None
    customer_id: int = Field(default=None, foreign_key="customer.id")

    customer: Optional[Customer] = Relationship(
        back_populates="meters",
        sa_relationship_kwargs={"foreign_keys": "[Meter.customer_id]"}
    )
    readouts: List["Readout"] = Relationship(back_populates="meter")


class Readout(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime
    usage: Decimal = Field(default=0, max_digits=12, decimal_places=5)
    price: Decimal = Field(default=0, max_digits=12, decimal_places=5)
    csv_filename: str
    meter_id: int = Field(default=None, foreign_key="meter.id")

    meter: Meter = Relationship(back_populates="readouts")


class Invoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    period_start: date
    period_end: date
    total_cost: Decimal = Field(default=0, max_digits=12, decimal_places=5)
    total_usage: Decimal = Field(default=0, max_digits=12, decimal_places=5)
    pdf_path: str | None = None
    customer_id: int = Field(default=None, foreign_key="customer.id")

    customer: Customer = Relationship(back_populates="invoices")
