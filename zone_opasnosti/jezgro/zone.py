from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsProject,
)

from .slojevi import napravi_geometriju

SEGMENATA = 16


def utm_epsg(lon, lat):
    broj_zone = min(int((lon + 180) // 6) + 1, 60)
    return (32600 if lat >= 0 else 32700) + broj_zone


def transformacija_u_utm(epsg):
    return QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem(f"EPSG:{epsg}"),
        QgsProject.instance(),
    )


def u_utm(geometrija, transformacija):
    kopija = QgsGeometry(geometrija)
    kopija.transform(transformacija)
    return kopija


def napravi_zonu(geometrija_izvora, radijus):
    return geometrija_izvora.buffer(radijus, SEGMENATA)


def zone_po_izvoru(razvrstano, hazardi, transformacija):
    rezultat = []
    for kategorija in hazardi:
        for objekat in razvrstano.get(kategorija["id"], []):
            izvor = u_utm(napravi_geometriju(objekat), transformacija)
            rezultat.append({
                "kategorija": kategorija,
                "objekat": objekat,
                "izvor": izvor,
                "radijus": kategorija["radijus"],
                "zona": napravi_zonu(izvor, kategorija["radijus"]),
            })
    return rezultat


def _delovi(geometrija):
    if geometrija.isMultipart():
        return geometrija.asGeometryCollection()
    return [geometrija]


def spoji_zone(geometrije_zona):
    if not geometrije_zona:
        return []
    unija = QgsGeometry.unaryUnion(geometrije_zona)
    zarista = [
        {"id": i + 1, "geometrija": deo, "zone": []}
        for i, deo in enumerate(_delovi(unija))
    ]
    for indeks, zona in enumerate(geometrije_zona):
        tacka = zona.pointOnSurface()
        for zariste in zarista:
            if zariste["geometrija"].intersects(tacka):
                zariste["zone"].append(indeks)
                break
    return zarista