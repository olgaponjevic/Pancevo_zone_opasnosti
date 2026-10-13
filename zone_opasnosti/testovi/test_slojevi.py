import unittest

from qgis.core import QgsWkbTypes

from jezgro import slojevi

KVADRAT = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
SKOLA = {"id": "skola", "naziv": "Skola"}


def _objekat(osm_id, geom_tip, koordinate, ime=None):
    tagovi = {"amenity": "school"}
    if ime:
        tagovi["name"] = ime
    return {"osm_tip": "node", "osm_id": osm_id, "tagovi": tagovi,
            "geom_tip": geom_tip, "koordinate": koordinate}


class TestGeometrije(unittest.TestCase):

    def test_tacka(self):
        g = slojevi.napravi_geometriju(_objekat(1, "tacka", (20.6, 44.8)))
        self.assertEqual(g.type(), QgsWkbTypes.PointGeometry)

    def test_linija(self):
        g = slojevi.napravi_geometriju(_objekat(2, "linija", [(0, 0), (1, 1)]))
        self.assertEqual(g.type(), QgsWkbTypes.LineGeometry)

    def test_poligon(self):
        g = slojevi.napravi_geometriju(_objekat(3, "poligon", [[KVADRAT]]))
        self.assertEqual(g.type(), QgsWkbTypes.PolygonGeometry)
        self.assertAlmostEqual(g.area(), 1.0)


class TestSloj(unittest.TestCase):

    def test_sloj_sadrzi_sve_objekte_i_atribute(self):
        objekti = [_objekat(1, "tacka", (0, 0), "OS Test"), _objekat(2, "tacka", (1, 1))]
        sloj = slojevi.napravi_sloj("test", "tacka", objekti, SKOLA)
        self.assertTrue(sloj.isValid())
        self.assertEqual(sloj.featureCount(), 2)
        prvi = next(sloj.getFeatures())
        self.assertEqual(prvi["naziv"], "OS Test")
        self.assertEqual(prvi["kategorija"], "Skola")

    def test_rezime_broji_po_vrsti_geometrije(self):
        razvrstano = {"skola": [
            _objekat(1, "tacka", (0, 0)),
            _objekat(2, "poligon", [[KVADRAT]]),
            _objekat(3, "poligon", [[KVADRAT]]),
        ]}
        self.assertEqual(slojevi.rezime(razvrstano, [SKOLA]), [("Skola", 1, 0, 2)])


if __name__ == "__main__":
    unittest.main()