from app.cartonize import cartonize_order
from app.labels import make_carton_summary_labels_pdf, make_inner_labels_pdf


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


def test_make_carton_summary_labels_pdf_produce_pdf_valido():
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    pdf = make_carton_summary_labels_pdf("TEST-001", "Cliente Prova", "2026-09-10", result)
    assert pdf.startswith(b"%PDF-")


def test_make_carton_summary_labels_pdf_senza_data_consegna():
    # data_consegna può mancare (ordine di test via CSV, non reale) — non deve rompere la stampa
    result = cartonize_order([{"sku": "CHMS50", "qta": 30}])
    pdf = make_carton_summary_labels_pdf("TEST-001", "Cliente Prova", None, result)
    assert pdf.startswith(b"%PDF-")


def test_make_carton_summary_labels_pdf_con_non_censiti():
    result = cartonize_order([{"sku": "CHMS50", "qta": 24}, {"sku": "SCONOSCIUTO01", "qta": 3}])
    assert result["non_censiti"]
    pdf = make_carton_summary_labels_pdf("TEST-001", "Cliente Prova", "2026-09-10", result)
    assert pdf.startswith(b"%PDF-")


def test_etichetta_con_override_a_un_solo_componente_tiene_il_barcode():
    """Un collo misto con UN solo SKU e l'override su quello stesso SKU è a
    tutti gli effetti un collo a prodotto singolo: il GTIN è davvero quello
    del contenuto, quindi il barcode resta (caso UNIGROUP, 4 WP50 da 25
    CANTS100 al posto dei 24+4 automatici)."""
    import pymupdf
    result = cartonize_order([{"sku": "CANTS100", "qta": 25}], colli_misti=[{
        "formato": "WP50",
        "componenti": [{"sku": "CANTS100", "pezzi": 25}],
        "etichetta_sku": "CANTS100", "etichetta_pezzi": 25,
    }])
    pdf = make_inner_labels_pdf(
        "TEST-001", "Cliente Prova", result, {}, {"CANTS100": "8055829950212"},
        {"CANTS100": "Cantuccini salati 100 g"},
    )
    testo = "".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))
    assert "25 pz" in testo
    assert "GTIN 8055829950212" in testo


def test_etichetta_con_override_su_piu_componenti_resta_senza_barcode():
    import pymupdf
    result = cartonize_order([{"sku": "VP01", "qta": 50}, {"sku": "VP06", "qta": 50}], colli_misti=[{
        "formato": "WP40",
        "componenti": [{"sku": "VP01", "pezzi": 50}, {"sku": "VP06", "pezzi": 50}],
        "etichetta_sku": "CANTS100", "etichetta_pezzi": 9,
    }])
    pdf = make_inner_labels_pdf(
        "TEST-001", "Cliente Prova", result, {}, {"CANTS100": "8055829950212"},
        {"CANTS100": "Cantuccini salati 100 g"},
    )
    testo = "".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))
    assert "GTIN" not in testo
