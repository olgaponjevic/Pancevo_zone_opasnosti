import os
import sys
import unittest

from qgis.core import QgsApplication

FOLDER = os.path.join(
    QgsApplication.qgisSettingsDirPath(), "python", "plugins", "zone_opasnosti"
)
if FOLDER not in sys.path:
    sys.path.insert(0, FOLDER)

for ime in list(sys.modules):
    if ime.split(".")[0] in ("jezgro", "testovi"):
        del sys.modules[ime]

testovi = unittest.defaultTestLoader.discover(
    os.path.join(FOLDER, "testovi"), top_level_dir=FOLDER
)
unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(testovi)