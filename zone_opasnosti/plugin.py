from qgis.PyQt.QtWidgets import QAction
from .dijalog import ZoneOpasnostiDijalog


class ZoneOpasnostiPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.akcija = None
        self.dijalog = None

    def initGui(self):
        self.akcija = QAction("Zone opasnosti", self.iface.mainWindow())
        self.akcija.triggered.connect(self.pokreni)
        self.iface.addToolBarIcon(self.akcija)
        self.iface.addPluginToVectorMenu("Zone opasnosti", self.akcija)

    def unload(self):
        if self.dijalog is not None:
            self.dijalog.ukloni_okvir() 
        self.iface.removePluginVectorMenu("Zone opasnosti", self.akcija)
        self.iface.removeToolBarIcon(self.akcija)

    def pokreni(self):
        if self.dijalog is None:
            self.dijalog = ZoneOpasnostiDijalog(self.iface, self.iface.mainWindow())
        self.dijalog.show()
        self.dijalog.raise_()