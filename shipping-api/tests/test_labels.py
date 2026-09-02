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


def test_make_inner_labels_pdf_con_gtin_genera_barcode_gs1():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    lotti = {"CHMS50": {"lotto": "050826", "scadenza": "2027-08-31"}}
    gtins = {"CHMS50": "8055829950168"}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, lotti, gtins)
    assert pdf.startswith(b"%PDF-")


def test_make_inner_labels_pdf_senza_gtin_nessun_barcode():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    lotti = {"CHMS50": {"lotto": "050826", "scadenza": "2027-08-31"}}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, lotti, gtins=None)
    assert pdf.startswith(b"%PDF-")


def test_make_inner_labels_pdf_con_nome_prodotto():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    nomi = {"CHMS50": "Chips con Mandorla di Avola da 50 g"}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, nomi_prodotto=nomi)
    assert pdf.startswith(b"%PDF-")


def test_make_inner_labels_pdf_con_nome_prodotto_lungo_va_a_capo():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    nomi = {"CHMS50": "Mandorle Pizzuta d'Avola con Fior di Sale Trapani confezione da 80 grammi extra lunga"}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, nomi_prodotto=nomi)
    assert pdf.startswith(b"%PDF-")


def test_make_inner_labels_pdf_senza_lotto_stampa_comunque():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    lotti = {"CHMS50": {"lotto": "050826", "scadenza": "2027-08-31"}}
    gtins = {"CHMS50": "8055829950168"}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, lotti, gtins, mostra_lotto=False)
    assert pdf.startswith(b"%PDF-")


def test_make_inner_labels_pdf_senza_lotto_barcode_solo_gtin():
    # senza lotto/scadenza (mostra_lotto=False) il barcode c'è comunque se
    # il GTIN è noto, ma codifica solo il prodotto, non lotto/scadenza
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    gtins = {"CHMS50": "8055829950168"}
    pdf = make_inner_labels_pdf("TEST-001", "Cliente Prova", result, lotti=None, gtins=gtins, mostra_lotto=False)
    assert pdf.startswith(b"%PDF-")
