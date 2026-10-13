import datetime
import json
import os
import re
import time
from urllib.parse import urlencode

SERVERI = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
TIMEOUT_S = 180
POKUSAJA_PO_SERVERU = 2


class OverpassGreska(Exception):
    pass


def _filter(uslov):
    return "".join(f'["{kljuc}"="{vrednost}"]' for kljuc, vrednost in uslov.items())


def napravi_upit(bbox, kategorije, timeout=TIMEOUT_S):
    s, w, n, e = bbox
    oblast = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    redovi = []
    vec_dodato = set()
    for kategorija in kategorije:
        for uslov in kategorija["tagovi"]:
            f = _filter(uslov)
            if f not in vec_dodato:
                vec_dodato.add(f)
                redovi.append(f"  nwr{f}{oblast};")
    return (
        f"[out:json][timeout:{timeout}];\n"
        "(\n" + "\n".join(redovi) + "\n);\n"
        "out geom;\n"
    )


def _posalji_preko_qgis(server, upit):
    from qgis.core import QgsBlockingNetworkRequest, QgsNetworkAccessManager
    from qgis.PyQt.QtCore import QByteArray, QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    stari_timeout = QgsNetworkAccessManager.timeout()
    QgsNetworkAccessManager.setTimeout((TIMEOUT_S + 30) * 1000)
    try:
        zahtev = QNetworkRequest(QUrl(server))
        zahtev.setHeader(
            QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded"
        )
        telo = QByteArray(urlencode({"data": upit}).encode("utf-8"))
        mreza = QgsBlockingNetworkRequest()
        rezultat = mreza.post(zahtev, telo)
        if rezultat != QgsBlockingNetworkRequest.NoError:
            raise OverpassGreska(mreza.errorMessage())
        return bytes(mreza.reply().content()).decode("utf-8")
    finally:
        QgsNetworkAccessManager.setTimeout(stari_timeout)


def preuzmi(upit, folder=None, serveri=SERVERI, posalji=None, javi=None, pauza_s=2):
    posalji = posalji or _posalji_preko_qgis
    greske = []
    for server in serveri:
        for pokusaj in range(1, POKUSAJA_PO_SERVERU + 1):
            if javi:
                javi(f"Saljem upit: {server} (pokusaj {pokusaj})")
            try:
                tekst = posalji(server, upit)
                podaci = json.loads(tekst)
                napomena = podaci.get("remark", "")
                if "error" in napomena.lower():
                    raise OverpassGreska(napomena)
                putanja = _sacuvaj(folder, upit, tekst, server) if folder else None
                return podaci, server, putanja
            except Exception as greska:
                greske.append(f"{server} (pokusaj {pokusaj}): {greska}")
                if pauza_s:
                    time.sleep(pauza_s * pokusaj)
    raise OverpassGreska(
        "Nijedan Overpass server nije uspeo da odgovori:\n" + "\n".join(greske)
    )


def _sacuvaj(folder, upit, tekst, server):
    os.makedirs(folder, exist_ok=True)
    oznaka = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    osnova = os.path.join(folder, f"overpass_{oznaka}")
    with open(osnova + ".overpassql", "w", encoding="utf-8") as f:
        f.write(f"// server: {server}\n// vreme: {oznaka}\n{upit}")
    with open(osnova + ".json", "w", encoding="utf-8") as f:
        f.write(tekst)
    return osnova + ".json"


def ucitaj_sacuvan_odgovor(putanja):
    with open(putanja, encoding="utf-8") as f:
        return json.load(f)


def parsiraj(podaci):
    objekti = []
    preskoceno = 0
    for element in podaci.get("elements", []):
        tagovi = element.get("tags") or {}
        if not tagovi:
            continue
        tip = element.get("type")
        if tip == "node":
            geometrija = ("tacka", (element["lon"], element["lat"]))
        elif tip == "way":
            geometrija = _geometrija_puta(element, tagovi)
        elif tip == "relation":
            geometrija = _geometrija_relacije(element, tagovi)
        else:
            geometrija = None

        if geometrija is None:
            preskoceno += 1
            continue
        objekti.append({
            "osm_tip": tip,
            "osm_id": element["id"],
            "tagovi": tagovi,
            "geom_tip": geometrija[0],
            "koordinate": geometrija[1],
        })
    return objekti, preskoceno


def _koordinate(geometrija):
    return [(t["lon"], t["lat"]) for t in (geometrija or []) if t]


def _geometrija_puta(element, tagovi):
    tacke = _koordinate(element.get("geometry"))
    if len(tacke) < 2:
        return None
    zatvoren = len(tacke) >= 4 and tacke[0] == tacke[-1]
    if zatvoren and tagovi.get("area") != "no":
        return ("poligon", [[tacke]])
    return ("linija", tacke)


def _geometrija_relacije(element, tagovi):
    if tagovi.get("type") not in ("multipolygon", "boundary"):
        return None
    spoljni, unutrasnji = [], []
    for clan in element.get("members", []):
        if clan.get("type") != "way":
            continue
        tacke = _koordinate(clan.get("geometry"))
        if clan.get("role") == "inner":
            unutrasnji.append(tacke)
        else:
            spoljni.append(tacke)

    spoljni_prstenovi = spoji_u_prstenove(spoljni)
    if not spoljni_prstenovi:
        return None
    poligoni = [[prsten] for prsten in spoljni_prstenovi]
    for rupa in spoji_u_prstenove(unutrasnji):
        x, y = rupa[0]
        for poligon in poligoni:
            if tacka_u_prstenu(x, y, poligon[0]):
                poligon.append(rupa)
                break
    return ("poligon", poligoni)


def spoji_u_prstenove(linije):
    preostale = [list(linija) for linija in linije if len(linija) >= 2]
    prstenovi = []
    while preostale:
        trenutni = preostale.pop(0)
        nadovezano = True
        while trenutni[0] != trenutni[-1] and nadovezano:
            nadovezano = False
            for i, deo in enumerate(preostale):
                if deo[0] == trenutni[-1]:
                    trenutni = trenutni + deo[1:]
                elif deo[-1] == trenutni[-1]:
                    trenutni = trenutni + deo[-2::-1]
                elif deo[-1] == trenutni[0]:
                    trenutni = deo[:-1] + trenutni
                elif deo[0] == trenutni[0]:
                    trenutni = deo[:0:-1] + trenutni
                else:
                    continue
                preostale.pop(i)
                nadovezano = True
                break
        if len(trenutni) >= 4 and trenutni[0] == trenutni[-1]:
            prstenovi.append(trenutni)
    return prstenovi


def tacka_u_prstenu(x, y, prsten):
    unutra = False
    for (x1, y1), (x2, y2) in zip(prsten, prsten[1:]):
        if (y1 > y) != (y2 > y):
            x_preseka = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_preseka:
                unutra = not unutra
    return unutra


def pripada(tagovi, kategorija):
    return any(
        all(tagovi.get(kljuc) == vrednost for kljuc, vrednost in uslov.items())
        for uslov in kategorija["tagovi"]
    )


def razvrstaj(objekti, kategorije):
    rezultat = {kategorija["id"]: [] for kategorija in kategorije}
    for objekat in objekti:
        for kategorija in kategorije:
            if pripada(objekat["tagovi"], kategorija):
                rezultat[kategorija["id"]].append(objekat)
                break
    return rezultat


def oblast_iz_sacuvanog_upita(putanja_json):
    putanja_upita = os.path.splitext(putanja_json)[0] + ".overpassql"
    if not os.path.exists(putanja_upita):
        return None
    with open(putanja_upita, encoding="utf-8") as f:
        pogodak = re.search(r"\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\);", f.read())
    if pogodak is None:
        return None
    return tuple(float(broj) for broj in pogodak.groups())