import csv
import os
import tempfile
import unittest

from jezgro import izvestaj

PUMPA = {"id": "pumpa", "naziv": "Benzinska pumpa"}
VRTIC = {"id": "vrtic", "naziv": "Vrtic / jaslice", "tezina": 3.0}
SKOLA = {"id": "skola", "naziv": "Skola", "tezina": 3.0}

IZVOR = {"kategorija": PUMPA, "objekat": {"osm_id": 10, "tagovi": {"name": "NIS"}}}
UGROZENI = [{
    "kategorija": VRTIC, "objekat": {"osm_id": 1, "tagovi": {"name": "Vrtic Carolija"}},
    "najblizi_izvor": IZVOR, "udaljenost": 42.345, "broj_zona": 2, "zariste_id": 1,
}]
ZARISTA = [
    {"rang": 1, "indeks": 6.0, "indeks_udaljenost": 3.5, "broj_ranjivih": 2,
     "po_kategoriji": {"Vrtic / jaslice": 1, "Skola": 1}, "broj_izvora": 3,
     "izvori": ["Benzinska pumpa: NIS", "Trafostanica"]},
    {"rang": 2, "indeks": 0, "indeks_udaljenost": 0, "broj_ranjivih": 0,
     "po_kategoriji": {}, "broj_izvora": 1, "izvori": ["Trafostanica"]},
]


def _procitaj(putanja):
    with open(putanja, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=";"))


class TestCsv(unittest.TestCase):

    def test_csv_ugrozenih(self):
        with tempfile.TemporaryDirectory() as folder:
            putanja = os.path.join(folder, "ugrozeni.csv")
            izvestaj.sacuvaj_csv_ugrozenih(UGROZENI, putanja)
            redovi = _procitaj(putanja)
        self.assertEqual(redovi[0][0], "naziv")
        self.assertEqual(redovi[1], ["Vrtic Carolija", "Vrtic / jaslice", "3",
                                     "Benzinska pumpa: NIS", "42.3", "2", "1", "1"])

    def test_csv_zarista_ima_kolonu_za_svaku_kategoriju(self):
        with tempfile.TemporaryDirectory() as folder:
            putanja = os.path.join(folder, "zarista.csv")
            izvestaj.sacuvaj_csv_zarista(
                ZARISTA, ["Vrtic / jaslice", "Skola", "Bolnica"], putanja)
            redovi = _procitaj(putanja)
        self.assertEqual(redovi[0], ["rang", "indeks", "indeks_udaljenost", "broj_ugrozenih",
                                     "Vrtic / jaslice", "Skola", "Bolnica",
                                     "broj_izvora", "izvori"])
        self.assertEqual(redovi[1], ["1", "6", "3.5", "2", "1", "1", "0", "3",
                                     "Benzinska pumpa: NIS, Trafostanica"])
        self.assertEqual(len(redovi), 2)

    def test_ime_sloja_za_geopackage(self):
        self.assertEqual(izvestaj._ime_za_gpkg("Zarista (rangirana)"), "zarista_rangirana")
        self.assertEqual(izvestaj._ime_za_gpkg("Ugrozeni objekti – tacke"),
                         "ugrozeni_objekti_tacke")


if __name__ == "__main__":
    unittest.main()