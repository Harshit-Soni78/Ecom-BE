from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
import io
import qrcode
from io import BytesIO as QRBytesIO
from fastapi import HTTPException
from app.models.order import Order
from app.models.settings import Settings
from app.models.product import Product
from app.core.config import settings as config_settings

def generate_invoice_pdf(order_id: str, db):
    """Generate professional invoice PDF for an order"""
    try:
        # Get order details
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get settings for company info
        settings = db.query(Settings).filter(Settings.type == "business").first()
        
        # Create PDF buffer
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Company details
        company_name = settings.company_name if settings and settings.company_name else "BharatBazaar"
        business_name = settings.business_name if settings and settings.business_name else "BharatBazaar"
        gst_number = settings.gst_number if settings and settings.gst_number else ""
        
        # Colors
        header_color = colors.HexColor('#2c3e50')
        
        # Header Section
        p.setFillColor(header_color)
        p.rect(0, height - 80, width, 80, fill=1)
        
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(30, height - 50, company_name)
        
        # Invoice title on right
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 20)
        p.drawRightString(width - 30, height - 35, "TAX INVOICE")
        p.setFont("Helvetica", 10)
        p.drawRightString(width - 30, height - 50, "Original For Recipient")
        
        # Company details section
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(30, height - 110, f"Sold by: {business_name}")
        
        p.setFont("Helvetica", 10)
        y_pos = height - 130
        
        if settings and settings.address:
            addr = settings.address
            address_lines = []
            if addr.get('line1'): address_lines.append(addr['line1'])
            if addr.get('line2'): address_lines.append(addr['line2'])
            if addr.get('city') and addr.get('state'):
                address_lines.append(f"{addr['city']}, {addr['state']}, {addr.get('pincode', '')}")
            
            for line in address_lines:
                p.drawString(30, y_pos, line)
                y_pos -= 15
        
        if gst_number:
            p.drawString(30, y_pos, f"GSTIN - {gst_number}")
            y_pos -= 15
        
        # Invoice details (right side)
        p.setFont("Helvetica", 10)
        purchase_order_no = f"{order.order_number.replace('ORD', '')}"
        invoice_no = f"Invq{purchase_order_no}"
        
        p.drawRightString(width - 30, height - 110, f"Purchase Order No.")
        p.drawRightString(width - 30, height - 125, f"Invoice No.")
        p.drawRightString(width - 30, height - 140, f"Order Date")
        p.drawRightString(width - 30, height - 155, f"Invoice Date")
        
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(width - 150, height - 110, purchase_order_no)
        p.drawRightString(width - 150, height - 125, invoice_no)
        p.drawRightString(width - 150, height - 140, order.created_at.strftime('%d.%m.%Y'))
        p.drawRightString(width - 150, height - 155, order.created_at.strftime('%d.%m.%Y'))
        
        # Bill To section
        p.setFillColor(colors.lightgrey)
        p.rect(30, height - 220, width - 60, 25, fill=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, height - 210, "BILL TO / SHIP TO")
        
        p.setFont("Helvetica", 10)
        y_pos = height - 240
        
        if order.shipping_address:
            addr = order.shipping_address
            if addr.get('name'):
                p.drawString(40, y_pos, addr['name'])
                y_pos -= 15
            
            address_parts = []
            if addr.get('line1'): address_parts.append(addr['line1'])
            if addr.get('line2'): address_parts.append(addr['line2'])
            
            for part in address_parts:
                p.drawString(40, y_pos, part)
                y_pos -= 15
            
            if addr.get('city') and addr.get('state'):
                p.drawString(40, y_pos, f"{addr['city']}, {addr['state']}, {addr.get('pincode', '')}. Place of Supply: {addr.get('state', '')}")
                y_pos -= 15
        
        # Items table header
        table_start_y = height - 320
        p.setFillColor(colors.lightgrey)
        p.rect(30, table_start_y - 20, width - 60, 20, fill=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(40, table_start_y - 15, "Description")
        p.drawString(250, table_start_y - 15, "HSN")
        p.drawString(290, table_start_y - 15, "Qty")
        p.drawString(330, table_start_y - 15, "Gross Amount")
        p.drawString(420, table_start_y - 15, "Discount")
        p.drawString(480, table_start_y - 15, "Taxable Value")
        p.drawString(550, table_start_y - 15, "Taxes")
        p.drawString(580, table_start_y - 15, "Total")
        
        # Items
        p.setFont("Helvetica", 8)
        y_pos = table_start_y - 35
        
        subtotal_before_tax = 0
        total_gst = 0
        
        for item in order.items:
            # Get product details
            product = db.query(Product).filter(Product.id == item["product_id"]).first()
            product_name = product.name if product else item.get("name", "Unknown Product")
            hsn_code = product.hsn_code if product and product.hsn_code else "960390"
            gst_rate = product.gst_rate if product else 18.0
            
            quantity = item["quantity"]
            unit_price = item["price"]
            gross_amount = quantity * unit_price
            discount = 0  # Can be added later
            taxable_value = gross_amount - discount
            gst_amount = taxable_value * (gst_rate / 100) if order.gst_applied else 0
            total_amount = taxable_value + gst_amount
            
            subtotal_before_tax += taxable_value
            total_gst += gst_amount
            
            # Draw item row
            p.drawString(40, y_pos, product_name[:25])
            p.drawString(250, y_pos, hsn_code)
            p.drawString(290, y_pos, str(quantity))
            p.drawString(330, y_pos, f"Rs.{gross_amount:.2f}")
            p.drawString(420, y_pos, f"Rs.{discount:.2f}")
            p.drawString(480, y_pos, f"Rs.{taxable_value:.2f}")
            
            if gst_amount > 0:
                p.drawString(550, y_pos, f"IGST @{gst_rate}%")
                p.drawString(550, y_pos - 10, f"Rs.{gst_amount:.2f}")
                y_pos -= 10
            else:
                p.drawString(550, y_pos, "Rs.0.00")
            
            p.drawString(580, y_pos, f"Rs.{total_amount:.2f}")
            y_pos -= 20
        
        # Totals section
        totals_y = y_pos - 30
        p.line(30, totals_y + 20, width - 30, totals_y + 20)
        
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(480, totals_y, "Total")
        p.drawRightString(580, totals_y, f"Rs.{order.grand_total:.2f}")
        
        # Tax summary
        if order.gst_applied and total_gst > 0:
            p.setFont("Helvetica", 9)
            p.drawString(40, totals_y - 40, "Tax is not payable on reverse charge basis. This is a computer generated invoice and does not require signature. Other charges are charges that are")
            p.drawString(40, totals_y - 55, "applicable to your order and/or city and/or online payments (as applicable). Includes discounts for your city and/or online payments (as applicable).")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

def generate_shipping_label_pdf(order_id: str, db):
    """Generate professional shipping label PDF for an order"""
    try:
        # Get order details
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get settings for company info
        settings = db.query(Settings).filter(Settings.type == "business").first()
        
        # Create PDF buffer - Standard 4x6 inch shipping label
        buffer = io.BytesIO()
        width, height = 4*inch, 6*inch
        p = canvas.Canvas(buffer, pagesize=(width, height))
        
        # Company details
        company_name = settings.company_name if settings and settings.company_name else "BharatBazaar"
        business_name = settings.business_name if settings and settings.business_name else "BharatBazaar"
        
        # --- SEPARATOR LINES ---
        # Main Border
        p.setStrokeColor(colors.black)
        p.setLineWidth(1.5)
        
        # Horizontal Separators
        y_line1 = height - 110
        y_line2 = height - 190
        y_line3 = height - 240
        y_line4 = height - 255
        
        p.setLineWidth(1)
        p.line(5, y_line1, width - 5, y_line1)
        p.line(5, y_line2, width - 5, y_line2)
        p.line(5, y_line3, width - 5, y_line3)
        p.line(5, y_line4, width - 5, y_line4)
        
        # Vertical Separator (Top Section)
        p.line(width * 0.45, height - 5, width * 0.45, y_line1)

        # --- TOP SECTION ---
        
        # Customer Address
        p.setFont("Helvetica-Bold", 7)
        p.drawString(10, height - 15, "Customer Address")
        
        if order.shipping_address:
            addr = order.shipping_address
            p.setFont("Helvetica-Bold", 10)
            p.drawString(10, height - 30, addr.get('name', '')[:25])
            
            p.setFont("Helvetica", 8)
            y_addr = height - 42
            line_height = 9
            
            address_lines = []
            if addr.get('line1'): address_lines.append(addr['line1'])
            if addr.get('line2'): address_lines.append(addr['line2'])
            location = []
            if addr.get('city'): location.append(addr['city'])
            if addr.get('state'): location.append(addr['state'])
            if addr.get('pincode'): location.append(str(addr['pincode']))
            if location: address_lines.append(", ".join(location))
             
            # Phone
            if order.customer_phone:
                address_lines.append(f"Tel: {order.customer_phone}")
            
            for line in address_lines[:6]:
                if len(line) > 30: line = line[:28] + "..."
                p.drawString(10, y_addr, line)
                y_addr -= line_height

        # COD / Courier Section (Right)
        x_right = width * 0.45 + 5
        
        # COD Amount Header
        p.setFillColor(colors.black)
        p.rect(x_right, height - 20, width - x_right - 5, 15, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 8)
        
        cod_text = "COD: Check amount on app"
        if order.payment_method == 'cod':
            cod_text = f"COD: Rs.{order.grand_total}"
        else:
             cod_text = "PREPAID"
             
        p.drawCentredString(x_right + (width - x_right - 5)/2, height - 16, cod_text)
        
        p.setFillColor(colors.black)
        
        # Courier Name
        p.setFont("Helvetica-Bold", 12)
        p.drawString(x_right, height - 35, "Shadowfax")
        
        # Pickup Badge
        p.setFillColor(colors.black)
        p.rect(x_right, height - 48, 35, 10, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 7)
        p.drawCentredString(x_right + 17.5, height - 45, "Pickup")
        p.setFillColor(colors.black)
        
        # Destination Code
        p.setFont("Helvetica", 7)
        p.drawString(x_right, height - 58, "Destination Code")
        
        # Mock Codes
        dest_code = "S46_PSA"
        p.setFillColor(colors.lightgrey)
        p.rect(x_right, height - 72, 60, 12, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(x_right + 2, height - 69, dest_code)
        
        # Return Code
        p.setFont("Helvetica", 7)
        p.drawString(x_right, height - 80, "Return Code")
        return_code = "303702,348"
        p.setFont("Helvetica-Bold", 8)
        p.drawString(x_right, height - 90, return_code)
        
        # QR Code
        qr_size = 50
        qr_x = width - qr_size - 5
        
         # Generate QR code
        qr_data = f"{order.order_number}|{order.grand_total}"
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = QRBytesIO()
        img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        p.drawImage(ImageReader(qr_buffer), qr_x, height - 80, width=qr_size, height=qr_size)
        
        # --- MIDDLE SECTION ---
        
        # Return Address (Left)
        p.setFont("Helvetica-Bold", 7)
        p.drawString(10, y_line1 - 10, "")
        
        p.setFont("Helvetica-Bold", 8)
        y_ret = y_line1 - 22
        p.drawString(10, y_ret, company_name.upper()[:35])
        y_ret -= 10
        
        p.setFont("Helvetica", 7)
        ret_lines = []
        if settings and settings.address:
            addr = settings.address
            if addr.get('line1'): ret_lines.append(addr['line1'].upper())
            if addr.get('line2'): ret_lines.append(addr['line2'].upper())
            if addr.get('city'): ret_lines.append(f"{addr['city'].upper()}, {addr.get('state', '').upper()}")
            if addr.get('pincode'): ret_lines.append(f"{addr.get('pincode')}")
        else:
            ret_lines.append("WAREHOUSE ADDRESS")
            
        for line in ret_lines[:4]:
             if len(line) > 40: line = line[:38] + "..."
             p.drawString(10, y_ret, line)
             y_ret -= 8
             
        # Tracking Barcode
        barcode_val = order.tracking_number or order.order_number
        p.setFont("Helvetica-Bold", 9)
        p.drawCentredString(width * 0.75, y_line1 - 70, barcode_val)
        
        # Simulated Barcode
        bc_x = width * 0.55
        bc_y = y_line1 - 50
        bc_w = 120
        bc_h = 30
        
        import random
        random.seed(barcode_val)
        curr_x = bc_x
        while curr_x < bc_x + bc_w:
            w = random.choice([1, 2, 3])
            if curr_x + w > bc_x + bc_w: break
            if random.choice([True, False]):
                p.rect(curr_x, bc_y, w, bc_h, fill=1, stroke=0)
            curr_x += w
            
        # --- PRODUCT DETAILS SECTION ---
        p.setFont("Helvetica-Bold", 8)
        p.drawString(10, y_line2 - 10, "Product Details")
        
        # Table Data
        data = [['SKU', 'Size', 'Qty', 'Color', 'Order No.']]
        
        # Items
        items_to_show = order.items[:3]
        for item in items_to_show:
            prod = db.query(Product).filter(Product.id == item['product_id']).first()
            sku = prod.sku if prod else "N/A"
            name = prod.name[:15] if prod else "Item"
            data.append([
                f"{sku}\n{name}", 
                "Free", 
                str(item['quantity']), 
                "Multi", 
                order.order_number[-8:]
            ])
            
        t = Table(data, colWidths=[80, 40, 30, 40, 80])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TEXTCOLOR', (0,0), (-1,0), colors.gray), 
        ]))
        
        w, h = t.wrapOn(p, width, height)
        t.drawOn(p, 5, y_line2 - h - 15)

        # --- TAX INVOICE SECTION (Bottom) ---
        
        # Header
        p.setFillColor(colors.lightgrey)
        p.rect(5, y_line3 - 12, width - 10, 12, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 8)
        p.drawCentredString(width/2, y_line3 - 9, "TAX INVOICE")
        p.setFont("Helvetica", 6)
        p.drawRightString(width - 10, y_line3 - 9, "Original For Recipient")
        
        # Bill To / Sold By
        y_inv = y_line4 - 10
        p.setFont("Helvetica-Bold", 6)
        p.drawString(10, y_inv, "BILL TO / SHIP TO")
        p.drawString(width/2 + 5, y_inv, f"Sold by : {business_name}")
        
        y_inv -= 8
        p.setFont("Helvetica", 6)
        
        # Bill To Address (Simplified)
        if order.shipping_address:
            addr_str = f"{order.shipping_address.get('name', '')}, {order.shipping_address.get('city', '')}"
            p.drawString(10, y_inv, addr_str[:45])
            p.drawString(10, y_inv - 7, f"State: {order.shipping_address.get('state', '')}")
            
        # Sold By Address
        if settings and settings.address:
            sold_addr = f"{settings.address.get('line1', '')}, {settings.address.get('city', '')}"
            p.drawString(width/2 + 5, y_inv, sold_addr[:45])
            
        if settings and settings.gst_number:
            p.drawString(width/2 + 5, y_inv - 7, f"GSTIN - {settings.gst_number}")
            
        # Invoice Table
        inv_data = [['Description', 'HSN', 'Qty', 'Gross', 'Disc', 'Taxable', 'Tax', 'Total']]
        
        total_taxable = 0
        total_tax = 0
        
        for item in items_to_show:
            prod = db.query(Product).filter(Product.id == item['product_id']).first()
            item_total = item['quantity'] * prod.selling_price
            
            # Simple tax calc (inclusive)
            tax_rate = prod.gst_rate if prod else 18.0
            taxable = item_total / (1 + (tax_rate/100))
            tax_amt = item_total - taxable
            
            total_taxable += taxable
            total_tax += tax_amt
            
            inv_data.append([
                prod.name[:10] if prod else "Item",
                prod.hsn_code if prod and prod.hsn_code else "960390",
                str(item['quantity']),
                f"{item_total:.0f}",
                "0",
                f"{taxable:.1f}",
                f"{tax_amt:.1f}",
                f"{item_total:.0f}"
            ])
            
        # Totals Row
        inv_data.append(['Total', '', '', '', '', f"{total_taxable:.1f}", f"{total_tax:.1f}", f"{order.grand_total:.1f}"])
            
        inv_table = Table(inv_data, colWidths=[70, 30, 20, 30, 25, 35, 30, 35])
        inv_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 5),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        
        w_inv, h_inv = inv_table.wrapOn(p, width, height)
        inv_table.drawOn(p, 5, y_inv - h_inv - 25)
        
        # Footer Disclaimer
        p.setFont("Helvetica", 5)
        p.drawString(10, 10, "Tax is not payable on reverse charge basis. Computer generated invoice.")

        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shipping label: {str(e)}")
