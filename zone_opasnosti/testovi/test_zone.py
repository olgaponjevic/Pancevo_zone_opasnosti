import math
import unittest

from qgis.core import QgsGeometry, QgsPointXY

from jezgro import zone

X0, Y0 = 500000, 5000000


def tacka(dx, dy=0):
    return QgsGeometry.fromPointXY(QgsPointXY(X0 + dx, Y0 + dy))


def pravougaonik(x1, y1, x2, y2):
    temena = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    return QgsGeometry.fromPolygonXY([[QgsPointXY(X0 + x, Y0 + y) for x, y in temena]])


class TestUtmZona(unittest.TestCase):

    def test_pancevo_je_u_zoni_34N(self):
        self.assertEqual(zone.utm_epsg(20.65, 44.87), 32634)

    def test_njujork_je_u_zoni_18N(self):
        self.assertEqual(zone.utm_epsg(-74.0, 40.7), 32618)

    def test_juzna_polulopta(self):
        self.assertEqual(zone.utm_epsg(151.2, -33.9), 32756)

    def test_granicni_meridijan_180(self):
        self.assertEqual(zone.utm_epsg(180.0, 10.0), 32660)


class TestZona(unittest.TestCase):

    def test_tacka_na_99_m_je_u_zoni_a_na_101_m_nije(self):
        z = zone.napravi_zonu(tacka(0), 100)
        self.assertTrue(z.intersects(tacka(99)))
        self.assertFalse(z.intersects(tacka(101)))

    def test_isto_vazi_i_u_kosom_pravcu(self):
        z = zone.napravi_zonu(tacka(0), 100)
        self.assertTrue(z.intersects(tacka(70, 70)))
        self.assertFalse(z.intersects(tacka(71, 71)))

    def test_zona_se_meri_od_ivice_poligona(self):
        izvor = pravougaonik(0, 0, 100, 100)
        z = zone.napravi_zonu(izvor, 50)
        objekat = tacka(140, 50)
        self.assertTrue(z.intersects(objekat))
        self.assertGreater(izvor.centroid().distance(objekat), 50)

    def test_poligon_cija_ivica_ulazi_u_zonu_a_centroid_ne(self):
        z = zone.napravi_zonu(tacka(0), 100)
        objekat = pravougaonik(50, -50, 250, 50)
        self.assertTrue(z.intersects(objekat))
        self.assertFalse(z.intersects(objekat.centroid()))


class TestSpajanje(unittest.TestCase):

    def test_dve_preklopljene_zone_daju_jedno_zariste(self):
        zone_lista = [zone.napravi_zonu(tacka(0), 100), zone.napravi_zonu(tacka(150), 100)]
        zarista = zone.spoji_zone(zone_lista)
        self.assertEqual(len(zarista), 1)
        self.assertEqual(sorted(zarista[0]["zone"]), [0, 1])

    def test_dve_razdvojene_zone_daju_dva_zarista(self):
        zone_lista = [zone.napravi_zonu(tacka(0), 100), zone.napravi_zonu(tacka(500), 100)]
        zarista = zone.spoji_zone(zone_lista)
        self.assertEqual(len(zarista), 2)
        self.assertEqual(sorted(len(z["zone"]) for z in zarista), [1, 1])

    def test_bez_zona_nema_zarista(self):
        self.assertEqual(zone.spoji_zone([]), [])


class TestMetri(unittest.TestCase):

    def test_zona_od_100_m_u_pancevu_ima_povrsinu_kruga_od_100_m(self):
        razvrstano = {"pumpa": [{
            "osm_tip": "node", "osm_id": 1, "tagovi": {},
            "geom_tip": "tacka", "koordinate": (20.65, 44.87),
        }]}
        hazardi = [{"id": "pumpa", "naziv": "Benzinska pumpa", "tagovi": [], "radijus": 100}]
        transformacija = zone.transformacija_u_utm(zone.utm_epsg(20.65, 44.87))
        rezultat = zone.zone_po_izvoru(razvrstano, hazardi, transformacija)
        self.assertEqual(len(rezultat), 1)
        ocekivano = math.pi * 100 ** 2
        self.assertAlmostEqual(rezultat[0]["zona"].area(), ocekivano, delta=0.01 * ocekivano)


if __name__ == "__main__":
    unittest.main()