import io
import csv
from pathlib import Path
import shutil
import uuid
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlmodel import select, func
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import pandas as pd

from .dependencies import create_db_and_tables, SessionDep
from .models import Customer, Meter, Readout, Invoice


app = FastAPI()

env = Environment(loader=FileSystemLoader("templates"))
templates = Jinja2Templates(directory="templates")


UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INVOICE_DIR = Path("./data/invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def read_root():
    return "Hello World"

@app.post("/customers/")
def create_customer(customer: Customer, session: SessionDep) -> Customer:
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


@app.get("/customers/")
def read_customers(session: SessionDep) -> list[Customer]:
    customers = session.exec(select(Customer)).all()
    return customers


@app.get("/upload-csv", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload-csv")
async def upload_csv_form(
    session: SessionDep,
    customer_id: str = Form(...),
    file: UploadFile = File(...),
    meter_id: str = Form(None),
):
    return await upload_csv(customer_id=customer_id, session=session, file=file, meter_id=meter_id)



@app.post("/customers/{customer_id}/upload-csv")
async def upload_csv(customer_id: int, session: SessionDep, file: UploadFile = File(...), meter_id: int = Form(None)):
    customer_db = session.get(Customer, customer_id)
    if not customer_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if not meter_id:
        if not customer_db.default_meter_id:
            meter = Meter(customer_id=customer_id)
            session.add(meter)
            session.commit()
            session.refresh(meter)
            meter_id = meter.id
            customer_db.default_meter_id = meter_id
        else:
            meter_id = customer_db.default_meter_id
    else:
        meter_db = session.get(Meter, meter_id)
        if not meter_db:
            meter = Meter(meter_id=meter_id, customer_id=customer_id)
            session.add(meter)
        customer_db.default_meter_id = meter_id
        session.add(customer_db)
        session.commit()
    
    meter_id = customer_db.default_meter_id
        

    filename = f"{uuid.uuid4()[:8]}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    df = pd.read_csv(file_path, delimiter=';')

    for i, timestamp, usage, price in df.itertuples():
        readout = Readout(
            timestamp=pd.to_datetime(timestamp),
            usage=Decimal(usage.replace(',', '.')),
            price=Decimal(price.replace(',', '.')),
            meter_id=meter_id,
            csv_filename=filename
        )
        session.add(readout)

    session.commit()

    return {"filename": filename, "rows_inserted": len(df)}

@app.get("/invoices/{customer_id}")
def calculate_invoice(
    customer_id: int,
    session: SessionDep,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(None, description="End date (YYYY-MM-DD)")
):
    customer_db = session.get(Customer, customer_id)
    if not customer_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if not end:
        end = start + relativedelta(day=31)

    stmt = (
        select(
            Meter.id.label("meter_id"),
            Meter.serial_number.label("meter_number"),
            func.sum(Readout.usage * Readout.price).label("cost"),
            func.sum(Readout.usage).label("usage"),
        )
        .join(Meter)
        .where(Meter.customer_id == customer_id)
        .where(Readout.timestamp >= start)
        .where(Readout.timestamp <= end)
        .group_by(Meter.id)
    )
    meter_results = session.exec(stmt).all()

    total_usage = sum([r.usage or 0 for r in meter_results])
    total_cost = sum([r.cost or 0 for r in meter_results])

    invoice = Invoice(period_start=start, period_end=end, customer_id=customer_id, total_cost=total_cost, total_usage=total_usage, pdf_path="")
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    invoice_data = {
        "customer": {"id": 1, "name": "Janez Novak", "address": "Celovška cesta 123, Ljubljana"},
        "invoice": {"id": invoice.id, "created_at": invoice.created_at.date()},
        "period": {"start": start, "end": end},
        "meters": [
            {
                "meter_number": r.meter_number,
                "meter_id": r.meter_id,
                "usage": float(r.usage or 0),
                "cost": float(r.cost or 0),
            }
            for r in meter_results
        ],
        "total_cost": float(total_cost),
        "total_usage": float(total_usage),
        "currency": "EUR",
    }
    
    # content = await file.read()
    # text = content.decode("utf-8")
    # csv_reader = csv.DictReader(io.StringIO(text))
    
    # rows = [row for row in csv_reader]

    # Load Jinja2 template
    template = env.get_template("invoice_template.html")
    html_content = template.render(invoice_data)

    # Convert HTML to PDF
    # pdf_bytes = pdfkit.from_string(html_content, False)
    # pdf_file = io.BytesIO(pdf_bytes)
    pdf_file = io.BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)

    base_path = INVOICE_DIR / str(customer_id) / str(end.year)
    base_path.mkdir(parents=True, exist_ok=True)

    pdf_path = base_path / f"{invoice.id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_file.read())

    invoice.pdf_path = str(pdf_path)
    session.add(invoice)
    session.commit()

    pdf_file.seek(0)
    return StreamingResponse(pdf_file, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=invoice.pdf"})
