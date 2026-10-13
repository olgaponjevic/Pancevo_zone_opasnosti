from qgis.core import (
    QgsFeature, QgsField, QgsFillSymbol, QgsGeometry, QgsMarkerSymbol, QgsPointXY,
    QgsProject, QgsSingleSymbolRenderer, QgsVectorLayer, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

TIPOVI = {
    "tacka": ("Point", "tacke"),
    "linija": ("LineString", "linije"),
    "poligon": ("MultiPolygon", "poligoni"),
}


def napravi_geometriju(objekat):
    k = objekat["koordinate"]
    tip = objekat["geom_tip"]
    if tip == "tacka":
        return QgsGeometry.fromPointXY(QgsPointXY(*k))
    if tip == "linija":
        return QgsGeometry.fromPolylineXY([QgsPointXY(*t) for t in k])
    return QgsGeometry.fromMultiPolygonXY(
        [[[QgsPointXY(*t) for t in prsten] for prsten in poligon] for poligon in k]
    )


def napravi_sloj(ime, geom_tip, objekti, kategorija):
    tip_qgis, _ = TIPOVI[geom_tip]
    sloj = QgsVectorLayer(f"{tip_qgis}?crs=EPSG:4326", ime, "memory")
    dp = sloj.dataProvider()
    dp.addAttributes([
        QgsField("osm_tip", QVariant.String),
        QgsField("osm_id", QVariant.LongLong),
        QgsField("naziv", QVariant.String),
        QgsField("kat_id", QVariant.String),
        QgsField("kategorija", QVariant.String),
    ])
    sloj.updateFields()
    obelezja = []
    for objekat in objekti:
        f = QgsFeature(sloj.fields())
        f.setGeometry(napravi_geometriju(objekat))
        f.setAttributes([
            objekat["osm_tip"],
            objekat["osm_id"],
            objekat["tagovi"].get("name", ""),
            kategorija["id"],
            kategorija["naziv"],
        ])
        obelezja.append(f)
    dp.addFeatures(obelezja)
    sloj.updateExtents()
    return sloj


def dodaj_u_projekat(razvrstano, kategorije, ime_grupe):
    projekat = QgsProject.instance()
    koren = projekat.layerTreeRoot()
    grupa = koren.findGroup(ime_grupe)
    if grupa is None:
        grupa = koren.insertGroup(0, ime_grupe)
    else:
        for sloj in grupa.findLayers():
            projekat.removeMapLayer(sloj.layerId())

    for kategorija in kategorije:
        objekti = razvrstano.get(kategorija["id"], [])
        for geom_tip, (_, opis) in TIPOVI.items():
            deo = [o for o in objekti if o["geom_tip"] == geom_tip]
            if not deo:
                continue
            sloj = napravi_sloj(f"{kategorija['naziv']} – {opis}", geom_tip, deo, kategorija)
            projekat.addMapLayer(sloj, False)
            grupa.addLayer(sloj)


def _pripremi_grupu(ime_grupe):
    projekat = QgsProject.instance()
    koren = projekat.layerTreeRoot()
    grupa = koren.findGroup(ime_grupe)
    if grupa is None:
        grupa = koren.insertGroup(0, ime_grupe)
    else:
        for sloj in grupa.findLayers():
            projekat.removeMapLayer(sloj.layerId())
    return projekat, grupa


def _poligonski_sloj(ime, epsg, polja, stil):
    sloj = QgsVectorLayer(f"MultiPolygon?crs=EPSG:{epsg}", ime, "memory")
    sloj.dataProvider().addAttributes(polja)
    sloj.updateFields()
    sloj.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(stil)))
    return sloj


def _dodaj_obelezje(sloj, geometrija, atributi):
    f = QgsFeature(sloj.fields())
    g = QgsGeometry(geometrija)
    g.convertToMultiType()
    f.setGeometry(g)
    f.setAttributes(atributi)
    sloj.dataProvider().addFeatures([f])


def dodaj_zone_u_projekat(zone, zarista, epsg, ime_grupe):
    projekat, grupa = _pripremi_grupu(ime_grupe)

    spojene = _poligonski_sloj(
        "Spojene zone (zarista)", epsg,
        [QgsField("zariste_id", QVariant.Int), QgsField("broj_izvora", QVariant.Int)],
        {"style": "no", "outline_color": "200,0,0", "outline_width": "0.8"},
    )
    for zariste in zarista:
        _dodaj_obelezje(spojene, zariste["geometrija"],
                        [zariste["id"], len(zariste["zone"])])

    po_izvoru = _poligonski_sloj(
        "Zone po izvoru", epsg,
        [QgsField("tip_hazarda", QVariant.String), QgsField("naziv", QVariant.String),
         QgsField("osm_id", QVariant.LongLong), QgsField("radijus_m", QVariant.Double)],
        {"color": "255,120,0,60", "outline_color": "200,90,0", "outline_width": "0.2"},
    )
    for z in zone:
        _dodaj_obelezje(po_izvoru, z["zona"], [
            z["kategorija"]["naziv"],
            z["objekat"]["tagovi"].get("name", ""),
            z["objekat"]["osm_id"],
            z["radijus"],
        ])

    for sloj in (spojene, po_izvoru):
        sloj.updateExtents()
        projekat.addMapLayer(sloj, False)
        grupa.addLayer(sloj)


IME_ZARISTA = "Zarista (rangirana)"
PREFIKS_UGROZENIH = "Ugrozeni objekti"
UGROZENI_PO_TIPU = {
    QgsWkbTypes.PointGeometry: ("MultiPoint", "tacke"),
    QgsWkbTypes.LineGeometry: ("MultiLineString", "linije"),
    QgsWkbTypes.PolygonGeometry: ("MultiPolygon", "poligoni"),
}


def dodaj_rezultate_analize(ugrozeni, zarista_rang, epsg, ime_grupe):
    projekat = QgsProject.instance()
    koren = projekat.layerTreeRoot()
    grupa = koren.findGroup(ime_grupe)
    if grupa is None:
        grupa = koren.insertGroup(0, ime_grupe)
    for cvor in grupa.findLayers():
        if cvor.name() == IME_ZARISTA or cvor.name().startswith(PREFIKS_UGROZENIH):
            projekat.removeMapLayer(cvor.layerId())

    zarista = _poligonski_sloj(
        IME_ZARISTA, epsg,
        [QgsField("rang", QVariant.Int), QgsField("zariste_id", QVariant.Int),
         QgsField("indeks", QVariant.Double), QgsField("indeks_ud", QVariant.Double),
         QgsField("br_ranjivih", QVariant.Int), QgsField("br_izvora", QVariant.Int)],
        {"style": "no", "outline_color": "150,0,150", "outline_width": "1"},
    )
    for z in zarista_rang:
        _dodaj_obelezje(zarista, z["geometrija"], [
            z["rang"], z["id"], z["indeks"], z["indeks_udaljenost"],
            z["broj_ranjivih"], z["broj_izvora"],
        ])
    zarista.updateExtents()
    projekat.addMapLayer(zarista, False)
    grupa.insertLayer(0, zarista)

    po_tipu = {}
    for u in ugrozeni:
        po_tipu.setdefault(u["geometrija"].type(), []).append(u)
    for tip, lista in po_tipu.items():
        if tip not in UGROZENI_PO_TIPU:
            continue
        wkb, opis = UGROZENI_PO_TIPU[tip]
        sloj = QgsVectorLayer(
            f"{wkb}?crs=EPSG:{epsg}", f"{PREFIKS_UGROZENIH} – {opis}", "memory"
        )
        sloj.dataProvider().addAttributes([
            QgsField("naziv", QVariant.String), QgsField("kategorija", QVariant.String),
            QgsField("tezina", QVariant.Double), QgsField("najblizi_izvor", QVariant.String),
            QgsField("udaljenost_m", QVariant.Double), QgsField("broj_zona", QVariant.Int),
            QgsField("zariste_id", QVariant.Int), QgsField("osm_id", QVariant.LongLong),
        ])
        sloj.updateFields()
        for u in lista:
            _dodaj_obelezje(sloj, u["geometrija"], [
                u["objekat"]["tagovi"].get("name", ""),
                u["kategorija"]["naziv"],
                u["kategorija"]["tezina"],
                _opis_izvora(u["najblizi_izvor"]),
                round(u["udaljenost"], 1),
                u["broj_zona"],
                u["zariste_id"],
                u["objekat"]["osm_id"],
            ])
        if tip == QgsWkbTypes.PointGeometry:
            simbol = QgsMarkerSymbol.createSimple(
                {"name": "circle", "color": "220,0,0", "size": "3", "outline_color": "0,0,0"}
            )
        elif tip == QgsWkbTypes.PolygonGeometry:
            simbol = QgsFillSymbol.createSimple(
                {"color": "220,0,0,160", "outline_color": "0,0,0", "outline_width": "0.4"}
            )
        else:
            simbol = None
        if simbol is not None:
            sloj.setRenderer(QgsSingleSymbolRenderer(simbol))
        sloj.updateExtents()
        projekat.addMapLayer(sloj, False)
        grupa.insertLayer(0, sloj)


def _opis_izvora(zona):
    ime = zona["objekat"]["tagovi"].get("name")
    naziv = zona["kategorija"]["naziv"]
    return f"{naziv}: {ime}" if ime else naziv


def rezime(razvrstano, kategorije):
    redovi = []
    for kategorija in kategorije:
        objekti = razvrstano.get(kategorija["id"], [])
        redovi.append((
            kategorija["naziv"],
            sum(o["geom_tip"] == "tacka" for o in objekti),
            sum(o["geom_tip"] == "linija" for o in objekti),
            sum(o["geom_tip"] == "poligon" for o in objekti),
        ))
    return redovi