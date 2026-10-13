from qgis.core import QgsFeature, QgsSpatialIndex

from .slojevi import napravi_geometriju
from .zone import u_utm


def pripremi_ranjive(razvrstano, ranjivi, transformacija):
    rezultat = []
    for kategorija in ranjivi:
        for objekat in razvrstano.get(kategorija["id"], []):
            rezultat.append({
                "kategorija": kategorija,
                "objekat": objekat,
                "geometrija": u_utm(napravi_geometriju(objekat), transformacija),
            })
    return rezultat


def _prostorni_indeks(zone):
    indeks = QgsSpatialIndex()
    for i, z in enumerate(zone):
        f = QgsFeature(i)
        f.setGeometry(z["zona"])
        indeks.addFeature(f)
    return indeks


def doprinos(tezina, udaljenost, radijus):
    if radijus <= 0:
        return 0.0
    return tezina * max(0.0, 1.0 - udaljenost / radijus)


def pronadji_ugrozene(ranjivi_objekti, zone, zarista):
    zona_u_zariste = {i: z["id"] for z in zarista for i in z["zone"]}
    indeks = _prostorni_indeks(zone)
    ugrozeni = []
    for r in ranjivi_objekti:
        g = r["geometrija"]
        parovi = []
        for i in indeks.intersects(g.boundingBox()):
            z = zone[i]
            if z["zona"].intersects(g):
                parovi.append({"zona": i, "udaljenost": z["izvor"].distance(g)})
        if not parovi:
            continue
        parovi.sort(key=lambda p: p["udaljenost"])
        najblizi = parovi[0]
        ugrozeni.append({
            **r,
            "parovi": parovi,
            "najblizi_izvor": zone[najblizi["zona"]],
            "udaljenost": najblizi["udaljenost"],
            "broj_zona": len(parovi),
            "zariste_id": zona_u_zariste.get(najblizi["zona"]),
        })
    return ugrozeni


def opis_izvora(zona):
    ime = zona["objekat"]["tagovi"].get("name")
    naziv = zona["kategorija"]["naziv"]
    return f"{naziv}: {ime}" if ime else naziv


def rangiraj_zarista(zarista, zone, ugrozeni):
    rezultat = []
    for z in zarista:
        objekti = [u for u in ugrozeni if u["zariste_id"] == z["id"]]
        po_kategoriji = {}
        for u in objekti:
            naziv = u["kategorija"]["naziv"]
            po_kategoriji[naziv] = po_kategoriji.get(naziv, 0) + 1
        rezultat.append({
            "id": z["id"],
            "geometrija": z["geometrija"],
            "broj_izvora": len(z["zone"]),
            "izvori": sorted({opis_izvora(zone[i]) for i in z["zone"]}),
            "broj_ranjivih": len(objekti),
            "po_kategoriji": po_kategoriji,
            "indeks": sum(u["kategorija"]["tezina"] for u in objekti),
            "indeks_udaljenost": round(sum(
                doprinos(u["kategorija"]["tezina"], u["udaljenost"],
                         u["najblizi_izvor"]["radijus"])
                for u in objekti
            ), 2),
        })
    rezultat.sort(key=lambda z: (-z["indeks"], -z["indeks_udaljenost"], z["id"]))
    for rang, z in enumerate(rezultat, start=1):
        z["rang"] = rang
    return rezultat