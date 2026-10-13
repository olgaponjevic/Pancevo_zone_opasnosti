import csv

NAPOMENA = (
    "Zona je kriterijum blizine, a ne model posledica akcidenta. Radijusi su "
    "demonstracioni, a ne zakonske zone. Indeks je relativan pokazatelj za "
    "poređenje žarišta unutar iste analize, a ne mera rizika. Plugin je "
    "demonstrator za nastavu i istraživanje, a ne operativni alat."
)
IZVOR_PODATAKA = "Podaci: OpenStreetMap contributors (ODbL)"


def _opis_izvora(zona):
    ime = zona["objekat"]["tagovi"].get("name")
    naziv = zona["kategorija"]["naziv"]
    return f"{naziv}: {ime}" if ime else naziv



def sacuvaj_csv_ugrozenih(ugrozeni, putanja):
    zaglavlje = ["naziv", "kategorija", "tezina", "najblizi_izvor",
                 "udaljenost_m", "broj_zona", "zariste_id", "osm_id"]
    with open(putanja, "w", newline="", encoding="utf-8-sig") as f:
        pisac = csv.writer(f, delimiter=";")
        pisac.writerow(zaglavlje)
        for u in sorted(ugrozeni, key=lambda u: (u["zariste_id"] or 0, u["udaljenost"])):
            pisac.writerow([
                u["objekat"]["tagovi"].get("name", ""),
                u["kategorija"]["naziv"],
                f'{u["kategorija"]["tezina"]:g}',
                _opis_izvora(u["najblizi_izvor"]),
                f'{u["udaljenost"]:.1f}',
                u["broj_zona"],
                u["zariste_id"],
                u["objekat"]["osm_id"],
            ])


def sacuvaj_csv_zarista(zarista_rang, nazivi_kategorija, putanja, samo_sa_ugrozenima=True):
    zaglavlje = (["rang", "indeks", "indeks_udaljenost", "broj_ugrozenih"]
                 + list(nazivi_kategorija) + ["broj_izvora", "izvori"])
    with open(putanja, "w", newline="", encoding="utf-8-sig") as f:
        pisac = csv.writer(f, delimiter=";")
        pisac.writerow(zaglavlje)
        for z in zarista_rang:
            if samo_sa_ugrozenima and z["broj_ranjivih"] == 0:
                continue
            pisac.writerow(
                [z["rang"], f'{z["indeks"]:g}', f'{z["indeks_udaljenost"]:g}',
                 z["broj_ranjivih"]]
                + [z["po_kategoriji"].get(naziv, 0) for naziv in nazivi_kategorija]
                + [z["broj_izvora"], ", ".join(z["izvori"])]
            )



def _ime_za_gpkg(ime):
    zamene = {"č": "c", "ć": "c", "š": "s", "ž": "z", "đ": "dj",
              "Č": "C", "Ć": "C", "Š": "S", "Ž": "Z", "Đ": "Dj"}
    for staro, novo in zamene.items():
        ime = ime.replace(staro, novo)
    dozvoljeno = "".join(z if z.isalnum() else "_" for z in ime.lower())
    while "__" in dozvoljeno:
        dozvoljeno = dozvoljeno.replace("__", "_")
    return dozvoljeno.strip("_")


def sacuvaj_geopackage(slojevi, putanja):
    from qgis.core import QgsProject, QgsVectorFileWriter

    imena = []
    for i, sloj in enumerate(slojevi):
        opcije = QgsVectorFileWriter.SaveVectorOptions()
        opcije.driverName = "GPKG"
        opcije.layerName = _ime_za_gpkg(sloj.name())
        opcije.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if i == 0
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        rezultat = QgsVectorFileWriter.writeAsVectorFormatV3(
            sloj, putanja, QgsProject.instance().transformContext(), opcije
        )
        if rezultat[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Sloj „{sloj.name()}“ nije sačuvan: {rezultat[1]}")
        imena.append(opcije.layerName)
    return imena



def _html_labela(layout, tekst, x, y, sirina, visina, velicina_pt):
    from qgis.core import QgsLayoutItemLabel
    from qgis.PyQt.QtCore import QRectF

    labela = QgsLayoutItemLabel(layout)
    labela.setMode(QgsLayoutItemLabel.ModeHtml)
    labela.setText(
        f"<div style='font-family:Arial; font-size:{velicina_pt}pt'>{tekst}</div>"
    )
    layout.addLayoutItem(labela)
    labela.attemptSetSceneRect(QRectF(x, y, sirina, visina))
    return labela


def napravi_pdf(putanja, obuhvat, crs_mape, slojevi_legende, zarista_rang,
                parametri_html, naslov="Zone opasnosti - izveštaj analize", broj_redova=5):
    from qgis.core import (
        QgsLayerTree, QgsLayoutExporter, QgsLayoutFrame, QgsLayoutItemLegend,
        QgsLayoutItemMap, QgsLayoutItemPage, QgsLayoutItemScaleBar,
        QgsLayoutItemTextTable, QgsLayoutPoint, QgsLayoutTableColumn,
        QgsPrintLayout, QgsProject,
    )
    from qgis.PyQt.QtCore import QRectF

    layout = QgsPrintLayout(QgsProject.instance())
    layout.initializeDefaults()
    layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Landscape)

    _html_labela(layout, f"<b>{naslov}</b>", 10, 6, 277, 10, 16)

    mapa = QgsLayoutItemMap(layout)
    mapa.attemptSetSceneRect(QRectF(10, 18, 175, 140))
    mapa.setCrs(crs_mape)
    mapa.setFrameEnabled(True)
    layout.addLayoutItem(mapa)
    mapa.zoomToExtent(obuhvat)

    razmera = QgsLayoutItemScaleBar(layout)
    razmera.setLinkedMap(mapa)
    razmera.setStyle("Single Box")
    razmera.applyDefaultSize()
    layout.addLayoutItem(razmera)
    razmera.attemptMove(QgsLayoutPoint(13, 145))

    legenda = QgsLayoutItemLegend(layout)
    legenda.setTitle("Legenda")
    legenda.setLinkedMap(mapa)
    legenda.setAutoUpdateModel(False)
    koren = QgsLayerTree()
    for sloj in slojevi_legende:
        koren.addLayer(sloj)
    legenda.model().setRootGroup(koren)
    legenda._koren = koren
    layout.addLayoutItem(legenda)
    legenda.attemptMove(QgsLayoutPoint(190, 18))

    _html_labela(layout, parametri_html, 190, 88, 97, 72, 8)

    tabela = QgsLayoutItemTextTable(layout)
    layout.addMultiFrame(tabela)
    tabela.setColumns([QgsLayoutTableColumn(naslov_kolone) for naslov_kolone in (
        "Rang", "Indeks", "Indeks (udalj.)", "Ugroženih", "Izvora", "Po kategorijama"
    )])
    for z in [z for z in zarista_rang if z["broj_ranjivih"] > 0][:broj_redova]:
        tabela.addRow([
            str(z["rang"]), f'{z["indeks"]:g}', f'{z["indeks_udaljenost"]:g}',
            str(z["broj_ranjivih"]), str(z["broj_izvora"]),
            ", ".join(f"{k}: {v}" for k, v in z["po_kategoriji"].items()),
        ])
    okvir = QgsLayoutFrame(layout, tabela)
    okvir.attemptSetSceneRect(QRectF(10, 162, 277, 36))
    tabela.addFrame(okvir)

    _html_labela(layout, f"<i>{NAPOMENA}</i> {IZVOR_PODATAKA}", 10, 199, 277, 9, 7)

    rezultat = QgsLayoutExporter(layout).exportToPdf(
        putanja, QgsLayoutExporter.PdfExportSettings()
    )
    if rezultat != QgsLayoutExporter.Success:
        raise RuntimeError(f"PDF nije napravljen (kod greške {rezultat}).")