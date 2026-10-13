import unittest

from qgis.core import QgsGeometry, QgsPointXY

from jezgro import analiza, zone

X0, Y0 = 500000, 5000000

PUMPA = {"id": "pumpa", "naziv": "Benzinska pumpa"}
VRTIC = {"id": "vrtic", "naziv": "Vrtic / jaslice", "tezina": 3}
KLINIKA = {"id": "klinika", "naziv": "Klinika / dom zdravlja", "tezina": 2}


def tacka(dx, dy=0):
    return QgsGeometry.fromPointXY(QgsPointXY(X0 + dx, Y0 + dy))


def pravougaonik(x1, y1, x2, y2):
    temena = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    return QgsGeometry.fromPolygonXY([[QgsPointXY(X0 + x, Y0 + y) for x, y in temena]])


def izvor(geometrija, radijus, ime="Izvor"):
    return {
        "kategorija": PUMPA, "objekat": {"osm_id": 1, "tagovi": {"name": ime}},
        "izvor": geometrija, "radijus": radijus,
        "zona": zone.napravi_zonu(geometrija, radijus),
    }


def ranjivi(geometrija, kategorija=VRTIC):
    return {"kategorija": kategorija, "objekat": {"osm_id": 2, "tagovi": {}},
            "geometrija": geometrija}


def analiziraj(izvori, ranjivi_objekti):
    zarista = zone.spoji_zone([z["zona"] for z in izvori])
    ugrozeni = analiza.pronadji_ugrozene(ranjivi_objekti, izvori, zarista)
    return ugrozeni, analiza.rangiraj_zarista(zarista, izvori, ugrozeni)


class TestUgrozeni(unittest.TestCase):

    def test_objekat_na_99_m_je_ugrozen_a_na_101_m_nije(self):
        ugrozeni, _ = analiziraj([izvor(tacka(0), 100)],
                                 [ranjivi(tacka(99)), ranjivi(tacka(101))])
        self.assertEqual(len(ugrozeni), 1)
        self.assertAlmostEqual(ugrozeni[0]["udaljenost"], 99)

    def test_poligon_cija_ivica_ulazi_u_zonu_je_ugrozen(self):
        objekat = pravougaonik(50, -50, 250, 50)
        ugrozeni, _ = analiziraj([izvor(tacka(0), 100)], [ranjivi(objekat)])
        self.assertEqual(len(ugrozeni), 1)
        self.assertAlmostEqual(ugrozeni[0]["udaljenost"], 50)

    def test_udaljenost_se_meri_od_ivice_izvora(self):
        ugrozeni, _ = analiziraj([izvor(pravougaonik(0, 0, 100, 100), 50)],
                                 [ranjivi(tacka(140, 50))])
        self.assertAlmostEqual(ugrozeni[0]["udaljenost"], 40)

    def test_objekat_u_dve_zone_pamti_najblizi_izvor(self):
        izvori = [izvor(tacka(0), 100, "Daleka"), izvor(tacka(120), 100, "Bliska")]
        ugrozeni, _ = analiziraj(izvori, [ranjivi(tacka(80))])
        self.assertEqual(ugrozeni[0]["broj_zona"], 2)
        self.assertEqual(ugrozeni[0]["najblizi_izvor"]["objekat"]["tagovi"]["name"], "Bliska")
        self.assertAlmostEqual(ugrozeni[0]["udaljenost"], 40)

    def test_bez_izvora_nema_ugrozenih(self):
        ugrozeni, zarista = analiziraj([], [ranjivi(tacka(0))])
        self.assertEqual((ugrozeni, zarista), ([], []))


class TestIndeks(unittest.TestCase):

    def test_doprinos(self):
        self.assertEqual(analiza.doprinos(3, 0, 100), 3)
        self.assertEqual(analiza.doprinos(3, 50, 100), 1.5)
        self.assertEqual(analiza.doprinos(3, 100, 100), 0)
        self.assertEqual(analiza.doprinos(3, 150, 100), 0)

    def test_indeks_je_zbir_tezina(self):
        _, zarista = analiziraj(
            [izvor(tacka(0), 100)],
            [ranjivi(tacka(0, 0), VRTIC), ranjivi(tacka(50), KLINIKA)],
        )
        self.assertEqual(zarista[0]["indeks"], 5)
        self.assertAlmostEqual(zarista[0]["indeks_udaljenost"], 4)
        self.assertEqual(zarista[0]["po_kategoriji"],
                         {"Vrtic / jaslice": 1, "Klinika / dom zdravlja": 1})

    def test_zariste_sa_vecim_indeksom_je_prvo(self):
        izvori = [izvor(tacka(0), 100, "A"), izvor(tacka(1000), 100, "B")]
        _, zarista = analiziraj(izvori, [
            ranjivi(tacka(10), KLINIKA),
            ranjivi(tacka(1010), VRTIC), ranjivi(tacka(990), VRTIC),
        ])
        self.assertEqual([z["rang"] for z in zarista], [1, 2])
        self.assertEqual([z["indeks"] for z in zarista], [6, 2])
        self.assertEqual(zarista[0]["izvori"], ["Benzinska pumpa: B"])

    def test_zariste_bez_ranjivih_ima_indeks_nula(self):
        _, zarista = analiziraj([izvor(tacka(0), 100)], [ranjivi(tacka(500))])
        self.assertEqual(zarista[0]["indeks"], 0)
        self.assertEqual(zarista[0]["broj_ranjivih"], 0)


if __name__ == "__main__":
    unittest.main()