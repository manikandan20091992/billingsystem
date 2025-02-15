from fastapi import FastAPI, Form, Depends, Request,HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List
import smtplib
from starlette.responses import HTMLResponse, JSONResponse
# Database Configuration
DB_CONFIG = {
    "dbname": "billing_db",
    "user": "manidb",
    "password": "mani@123",
    "host": "localhost",
    "port": "5432",
}

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Function to connect to DB
def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor, conn
    finally:
        cursor.close()
        conn.close()

# Home Page
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
#view_all_product_stock
@app.get('/view_all_product_stock', response_class=HTMLResponse)
def view_all_product_stock(request: Request):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall() 
        
    finally:
        cursor.close()
        conn.close()

    return templates.TemplateResponse(
        "view_all_product_stock.html",
        {"request": request, "products": products}  
    )

@app.delete("/delete_product/{product_id}")
def delete_product(product_id: int):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return JSONResponse({"success": True})
# Add Product Form
@app.get("/add_product", response_class=HTMLResponse)
def add_product_form(request: Request):
    return templates.TemplateResponse("add_product.html", {"request": request})

@app.post("/add_product")
def add_product(
    name: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    tax: float = Form(...),
    db=Depends(get_db)
):
    cursor, conn = db
    cursor.execute(
        "INSERT INTO products (name, price, stock, tax) VALUES (%s, %s, %s, %s)",
        (name, price, stock, tax)
    )
    conn.commit()
    return RedirectResponse("/", status_code=303)

# Update Stock Form
@app.get("/add_stock", response_class=HTMLResponse)
def add_stock_form(request: Request):
    return templates.TemplateResponse("add_stock.html", {"request": request})

@app.post("/add_stock")
def add_stock(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db=Depends(get_db)
):
    cursor, conn = db
    cursor.execute("UPDATE products SET stock = stock + %s WHERE id = %s", (quantity, product_id))
    conn.commit()
    return RedirectResponse("/", status_code=303)

# Bill Generation Form
@app.get("/generate_bill", response_class=HTMLResponse)
def generate_bill_form(request: Request):
    return templates.TemplateResponse("generate_bill.html", {"request": request})

@app.post("/generate_bill", response_class=HTMLResponse)
def generate_bill(
    request: Request,
    customer_email: str = Form(...),
    product_ids: List[int] = Form(...),
    quantities: List[int] = Form(...),
    paid_amount: float = Form(...),
    denomination_500: int = Form(0),
    denomination_200: int = Form(0),
    denomination_100: int = Form(0),
    denomination_50: int = Form(0),
    denomination_20: int = Form(0),
    denomination_10: int = Form(0),
    denomination_5: int = Form(0),
    db=Depends(get_db)
):
    cursor, conn = db
    cursor.execute("INSERT INTO purchases (customer_email) VALUES (%s) RETURNING id", (customer_email,))
    purchase_id = cursor.fetchone()["id"]

    total_price = 0
    total_tax = 0
    bill_items = []
    productNameList = []

    for product_id, quantity in zip(product_ids, quantities):
        cursor.execute("SELECT stock, price, tax, name FROM products WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        if not product:
            continue

        stock, price, tax_percentage, name = product["stock"], product["price"], product["tax"], product["name"]
        cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (quantity, product_id))

        item_total = price * quantity
        tax_amount = (price * quantity) * (tax_percentage / 100)
        total_price += item_total
        total_tax += tax_amount

        cursor.execute(
            "INSERT INTO purchase_items (purchase_id, product_id, quantity) VALUES (%s, %s, %s)",
            (purchase_id, product_id, quantity)
        )

        productNameList.append(name)
        bill_items.append({
            "product_ids":product_id,
            "name": name,
            "quantity": quantity,
            "price": price,
            "tax": tax_percentage,
            "tax_amount": tax_amount,
            "total": item_total + tax_amount,
            
        })

    grand_total = total_price + total_tax
    balance = paid_amount - grand_total
    conn.commit()

    send_invoice(customer_email, productNameList, total_tax, grand_total, balance)

    return templates.TemplateResponse("generate_bill.html", {
        "request": request,
        "customer_email": customer_email,
        "bill_items": bill_items,
        "total_price": total_price,
        "total_tax": total_tax,
        "grand_total": grand_total,
        "paid_amount": paid_amount,
        "balance": balance,
        "round":round(grand_total),
        "denomination_500": denomination_500,
        "denomination_200": denomination_200,
        "denomination_100": denomination_100,
        "denomination_50": denomination_50,
        "denomination_20": denomination_20,
        "denomination_10": denomination_10,
        "denomination_5": denomination_5,
    })

# Send Invoice via Email
def send_invoice(email: str, name: str, total_tax: float, grand_total: float, balance: float):
    sender_email = "manikandanvceeee@gmail.com"
    receiver_email = email
    subject = "Your Invoice"
    body = f"Product Name: {name}\nTotal Tax: {total_tax}\nGrand Total: {grand_total}\nBalance: {balance}\nThank you for your purchase!"
    message = f"Subject: {subject}\n\n{body}"

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("manikandanvceeee@gmail.com", "rqwi yljf tyop fobn")
        server.sendmail(sender_email, receiver_email, message)