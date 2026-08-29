from app.cartonize import cartonize_order
from app.labels import make_inner_labels_pdf


def test_make_inner_labels_pdf_produce_pdf_valido():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result)
    assert pdf.startswith(b"%PDF-")
    n_colli = sum(len(c["contenuto"]) for c in result["scatoloni"])
    assert n_colli == 2  # 1 WP50 (24pz) + 1 WP40 (6pz)


def test_make_inner_labels_pdf_con_lotto_reale():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    lotti = {"CHMS50": {"lotto": "050826", "scadenza": "2027-08-31"}}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, lotti)
    assert pdf.startswith(b"%PDF-")
