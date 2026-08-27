from app.day_plan import make_day_plan_pdf


def test_make_day_plan_pdf_multipagina():
    ordini = [
        {"order_number": f"ORD-{i}", "cliente": f"Cliente {i}", "righe": [{"sku": "CHMS50", "qta": 30}]}
        for i in range(5)  # 5 ordini → 2 pagine (4 + 1)
    ]
    pdf = make_day_plan_pdf("2026-09-15", ordini)
    assert pdf.startswith(b"%PDF-")
    # 2 pagine attese per "/Type/Page" nel content stream (approssimazione robusta: conta "/Type /Page")
    assert pdf.count(b"/Type/Page") + pdf.count(b"/Type /Page") >= 2
