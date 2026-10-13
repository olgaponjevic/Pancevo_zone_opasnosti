import json
import os
import tempfile
import unittest

from jezgro import overpass
from jezgro.kategorije import IZVORI_HAZARDA, RANJIVI_OBJEKTI

KVADRAT = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]


def _tacke(koordinate):
    return [{"lon": x, "lat": y} for x, y in koordinate]


class TestUpit(unittest.TestCase):

    def test_upit_koristi_pravu_geometriju_i_oblast(self):
        upit = overpass.napravi_upit((44.8, 20.6, 44.9, 20.7), IZVORI_HAZARDA)
        self.assertIn("out geom;", upit)
        self.assertNotIn("out center", upit)
        self.assertIn('nwr["amenity"="fuel"](44.800000,20.600000,44.900000,20.700000);', upit)

    def test_dva_uslova_u_istom_redu(self):
        upit = overpass.napravi_upit((0, 0, 1, 1), IZVORI_HAZARDA)
        self.assertIn('nwr["man_made"="storage_tank"]["content"="fuel"]', upit)

    def test_isti_tag_se_ne_ponavlja(self):
        kategorije = [{"tagovi": [{"amenity": "school"}]}, {"tagovi": [{"amenity": "school"}]}]
        upit = overpass.napravi_upit((0, 0, 1, 1), kategorije)
        self.assertEqual(upit.count('["amenity"="school"]'), 1)


class TestParsiranje(unittest.TestCase):

    def test_tacka(self):
        podaci = {"elements": [
            {"type": "node", "id": 1, "lon": 20.6, "lat": 44.8, "tags": {"amenity": "fuel"}}
        ]}
        objekti, _ = overpass.parsiraj(podaci)
        self.assertEqual(objekti[0]["geom_tip"], "tacka")
        self.assertEqual(objekti[0]["koordinate"], (20.6, 44.8))

    def test_zatvoren_put_je_poligon(self):
        podaci = {"elements": [
            {"type": "way", "id": 2, "tags": {"landuse": "industrial"},
             "geometry": _tacke(KVADRAT)}
        ]}
        objekti, _ = overpass.parsiraj(podaci)
        self.assertEqual(objekti[0]["geom_tip"], "poligon")
        self.assertEqual(objekti[0]["koordinate"], [[KVADRAT]])

    def test_otvoren_put_je_linija(self):
        podaci = {"elements": [
            {"type": "way", "id": 3, "tags": {"power": "substation"},
             "geometry": _tacke([(0, 0), (1, 0), (1, 1)])}
        ]}
        objekti, _ = overpass.parsiraj(podaci)
        self.assertEqual(objekti[0]["geom_tip"], "linija")

    def test_objekti_bez_tagova_se_preskacu(self):
        podaci = {"elements": [{"type": "node", "id": 4, "lon": 0, "lat": 0}]}
        objekti, preskoceno = overpass.parsiraj(podaci)
        self.assertEqual(objekti, [])
        self.assertEqual(preskoceno, 0)

    def test_prazan_odgovor(self):
        objekti, preskoceno = overpass.parsiraj({"elements": []})
        self.assertEqual((objekti, preskoceno), ([], 0))

    def test_multipoligon_iz_dva_dela_sa_rupom(self):
        spolja_1 = [(0, 0), (4, 0), (4, 4)]
        spolja_2 = [(0, 0), (0, 4), (4, 4)]
        rupa = [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]
        podaci = {"elements": [{
            "type": "relation", "id": 5,
            "tags": {"type": "multipolygon", "power": "plant"},
            "members": [
                {"type": "way", "role": "outer", "geometry": _tacke(spolja_1)},
                {"type": "way", "role": "outer", "geometry": _tacke(spolja_2)},
                {"type": "way", "role": "inner", "geometry": _tacke(rupa)},
            ],
        }]}
        objekti, _ = overpass.parsiraj(podaci)
        self.assertEqual(objekti[0]["geom_tip"], "poligon")
        poligoni = objekti[0]["koordinate"]
        self.assertEqual(len(poligoni), 1)
        self.assertEqual(len(poligoni[0]), 2)
        spoljni = poligoni[0][0]
        self.assertEqual(spoljni[0], spoljni[-1])
        self.assertEqual(len(spoljni), 5)

    def test_relacija_koja_nije_multipoligon_se_preskace(self):
        podaci = {"elements": [{
            "type": "relation", "id": 6, "tags": {"type": "site", "power": "plant"},
            "members": [],
        }]}
        objekti, preskoceno = overpass.parsiraj(podaci)
        self.assertEqual(objekti, [])
        self.assertEqual(preskoceno, 1)


class TestRazvrstavanje(unittest.TestCase):

    def test_svaka_kategorija_postoji_i_kad_je_prazna(self):
        rezultat = overpass.razvrstaj([], RANJIVI_OBJEKTI)
        self.assertEqual(set(rezultat), {k["id"] for k in RANJIVI_OBJEKTI})
        self.assertTrue(all(lista == [] for lista in rezultat.values()))

    def test_jaslice_idu_u_vrtice(self):
        objekat = {"tagovi": {"amenity": "childcare"}}
        rezultat = overpass.razvrstaj([objekat], RANJIVI_OBJEKTI)
        self.assertEqual(rezultat["vrtic"], [objekat])

    def test_dom_za_stare_se_ne_broji_dvaput(self):
        objekat = {"tagovi": {"amenity": "social_facility", "social_facility": "nursing_home"}}
        rezultat = overpass.razvrstaj([objekat], RANJIVI_OBJEKTI)
        self.assertEqual(rezultat["dom_za_stare"], [objekat])
        self.assertEqual(rezultat["socijalna"], [])

    def test_rezervoar_bez_goriva_nije_skladiste_goriva(self):
        objekat = {"tagovi": {"man_made": "storage_tank", "content": "water"}}
        rezultat = overpass.razvrstaj([objekat], IZVORI_HAZARDA)
        self.assertEqual(rezultat["skladiste_goriva"], [])


class TestPreuzimanje(unittest.TestCase):

    def test_prelazi_na_sledeci_server_kada_prvi_ne_odgovori(self):
        pozvani = []

        def lazni_server(server, upit):
            pozvani.append(server)
            if server == "A":
                raise overpass.OverpassGreska("Gateway Timeout")
            return json.dumps({"elements": []})

        _, server, _ = overpass.preuzmi("upit", serveri=["A", "B"],
                                        posalji=lazni_server, pauza_s=0)
        self.assertEqual(server, "B")
        self.assertEqual(pozvani, ["A", "A", "B"])

    def test_greska_kada_nijedan_server_ne_uspe(self):
        def uvek_greska(server, upit):
            raise overpass.OverpassGreska("Gateway Timeout")

        with self.assertRaises(overpass.OverpassGreska):
            overpass.preuzmi("upit", serveri=["A"], posalji=uvek_greska, pauza_s=0)

    def test_napomena_o_gresci_na_serveru_se_tretira_kao_neuspeh(self):
        odgovori = iter([
            json.dumps({"elements": [], "remark": "runtime error: Query timed out"}),
            json.dumps({"elements": []}),
        ])
        overpass.preuzmi("upit", serveri=["A"],
                         posalji=lambda s, u: next(odgovori), pauza_s=0)

    def test_sirovi_odgovor_se_cuva_i_moze_ponovo_ucitati(self):
        odgovor = {"elements": [{"type": "node", "id": 1, "lon": 1, "lat": 2,
                                 "tags": {"amenity": "school"}}]}
        with tempfile.TemporaryDirectory() as folder:
            _, _, putanja = overpass.preuzmi(
                "upit", folder=folder, serveri=["A"],
                posalji=lambda s, u: json.dumps(odgovor), pauza_s=0,
            )
            self.assertTrue(os.path.exists(putanja))
            self.assertTrue(os.path.exists(putanja.replace(".json", ".overpassql")))
            self.assertEqual(overpass.ucitaj_sacuvan_odgovor(putanja), odgovor)

    def test_oblast_se_cita_iz_sacuvanog_upita(self):
        bbox = (44.8475, 20.5668, 44.9027, 20.7938)
        upit = overpass.napravi_upit(bbox, IZVORI_HAZARDA)
        with tempfile.TemporaryDirectory() as folder:
            _, _, putanja = overpass.preuzmi(
                upit, folder=folder, serveri=["A"],
                posalji=lambda s, u: json.dumps({"elements": []}), pauza_s=0,
            )
            self.assertEqual(overpass.oblast_iz_sacuvanog_upita(putanja), bbox)

    def test_oblast_je_none_ako_upit_ne_postoji(self):
        self.assertIsNone(overpass.oblast_iz_sacuvanog_upita("nepostojeci.json"))


if __name__ == "__main__":
    unittest.main()