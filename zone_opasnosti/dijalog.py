import copy
import os

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsProject,
    QgsSettings, QgsWkbTypes,
)
from qgis.gui import QgsFileWidget, QgsMapToolExtent, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
)

from .jezgro import analiza, izvestaj, overpass, slojevi, zone
from .jezgro.kategorije import IZVORI_HAZARDA, RANJIVI_OBJEKTI

GRUPA_ULAZ = "Zone opasnosti - ulazni podaci"
GRUPA_REZULTATI = "Zone opasnosti - rezultati"
MAKS_STEPENI = 0.6
PODESAVANJE_FOLDER = "zone_opasnosti/folder"


class ZoneOpasnostiDijalog(QDialog):

    def __init__(self, iface, roditelj=None):
        super().__init__(roditelj)
        self.iface = iface
        self.oblast = None
        self._okvir = None
        self._alat = None
        self._prethodni_alat = None
        self.setWindowTitle("Zone opasnosti")
        self.resize(760, 760)

        raspored = QVBoxLayout(self)

        raspored.addWidget(QLabel(
            "<b>Izvori hazarda</b> - stiklirajte kategorije; radijus se menja dvoklikom"
        ))
        self.tabela_hazarda = self._napravi_tabelu(
            IZVORI_HAZARDA, "Radijus (m)", "radijus"
        )
        raspored.addWidget(self.tabela_hazarda)

        raspored.addWidget(QLabel(
            "<b>Ranjivi objekti</b> - stiklirajte kategorije; tezina se menja dvoklikom"
        ))
        self.tabela_ranjivih = self._napravi_tabelu(
            RANJIVI_OBJEKTI, "Tezina", "tezina"
        )
        raspored.addWidget(self.tabela_ranjivih)

        red_folder = QHBoxLayout()
        red_folder.addWidget(QLabel("Folder za sirove podatke:"))
        self.folder = QgsFileWidget()
        self.folder.setStorageMode(QgsFileWidget.GetDirectory)
        self.folder.setFilePath(QgsSettings().value(
            PODESAVANJE_FOLDER, os.path.expanduser("~")
        ))
        red_folder.addWidget(self.folder)
        raspored.addLayout(red_folder)

        red_oblast = QHBoxLayout()
        self.dugme_crtaj = QPushButton("Nacrtaj oblast analize na mapi")
        self.dugme_crtaj.clicked.connect(self.zapocni_crtanje)
        red_oblast.addWidget(self.dugme_crtaj)
        self.dugme_ponisti = QPushButton("Ponisti oblast")
        self.dugme_ponisti.clicked.connect(self.ponisti_oblast)
        self.dugme_ponisti.setEnabled(False)
        red_oblast.addWidget(self.dugme_ponisti)
        self.labela_oblast = QLabel()
        red_oblast.addWidget(self.labela_oblast, 1)
        raspored.addLayout(red_oblast)
        self._osvezi_labelu_oblasti()

        self.dugme_preuzmi = QPushButton(
            "Preuzmi podatke iz OSM-a za izabranu oblast"
        )
        self.dugme_preuzmi.clicked.connect(self.preuzmi_podatke)
        raspored.addWidget(self.dugme_preuzmi)

        self.dugme_ucitaj = QPushButton("Ucitaj ranije sacuvane podatke (bez interneta)")
        self.dugme_ucitaj.clicked.connect(self.ucitaj_sacuvane_podatke)
        raspored.addWidget(self.dugme_ucitaj)

        self.dugme_zone = QPushButton("Napravi zone opasnosti")
        self.dugme_zone.setEnabled(False)
        self.dugme_zone.clicked.connect(self.napravi_zone)
        raspored.addWidget(self.dugme_zone)

        self.dugme_analiza = QPushButton("Pronadji ugrozene objekte i rangiraj zarista")
        self.dugme_analiza.setEnabled(False)
        self.dugme_analiza.clicked.connect(self.analiziraj)
        raspored.addWidget(self.dugme_analiza)

        self.dugme_izvoz = QPushButton("Sacuvaj rezultate (CSV, GeoPackage, PDF izvestaj)")
        self.dugme_izvoz.setEnabled(False)
        self.dugme_izvoz.clicked.connect(self.sacuvaj_rezultate)

        self.tabela_zarista = QTableWidget(0, 6)
        self.tabela_zarista.setHorizontalHeaderLabels(
            ["Rang", "Indeks", "Indeks (udalj.)", "Ugrozenih", "Izvora", "Po kategorijama"]
        )
        self.tabela_zarista.verticalHeader().setVisible(False)
        self.tabela_zarista.setToolTip("Dvoklik na red zumira mapu na zariste")
        self.tabela_zarista.setMaximumHeight(180)
        self.tabela_zarista.cellDoubleClicked.connect(self._zumiraj_na_zariste)
        raspored.addWidget(self.tabela_zarista)
        raspored.addWidget(self.dugme_izvoz)

        self.izvestaj = QTextEdit()
        self.izvestaj.setReadOnly(True)
        self.izvestaj.setMinimumHeight(160)
        raspored.addWidget(self.izvestaj)

        napomena = QLabel(
            "<i>Zona je kriterijum blizine, a ne model posledica akcidenta. "
            "Radijusi su demonstracioni, a ne zakonske zone.</i>"
        )
        napomena.setWordWrap(True)
        raspored.addWidget(napomena)

        dugmad = QDialogButtonBox(QDialogButtonBox.Close)
        dugmad.rejected.connect(self.close)
        raspored.addWidget(dugmad)

    @staticmethod
    def _tagovi_u_tekst(tagovi):
        return ", ".join(
            " + ".join(f"{k}={v}" for k, v in uslov.items()) for uslov in tagovi
        )

    def _napravi_tabelu(self, kategorije, naslov_vrednosti, kljuc_vrednosti):
        tabela = QTableWidget(len(kategorije), 3)
        tabela.setHorizontalHeaderLabels(["Kategorija", "OSM tagovi", naslov_vrednosti])
        for r, kategorija in enumerate(kategorije):
            naziv = QTableWidgetItem(kategorija["naziv"])
            naziv.setFlags((naziv.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            naziv.setCheckState(Qt.Checked)
            tagovi = QTableWidgetItem(self._tagovi_u_tekst(kategorija["tagovi"]))
            tagovi.setFlags(tagovi.flags() & ~Qt.ItemIsEditable)
            tagovi.setToolTip(tagovi.text())
            vrednost = QTableWidgetItem(str(kategorija[kljuc_vrednosti]))
            tabela.setItem(r, 0, naziv)
            tabela.setItem(r, 1, tagovi)
            tabela.setItem(r, 2, vrednost)
        zaglavlje = tabela.horizontalHeader()
        zaglavlje.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        zaglavlje.setSectionResizeMode(1, QHeaderView.Stretch)
        zaglavlje.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tabela.verticalHeader().setVisible(False)
        return tabela

    def _izabrane(self, tabela, kategorije, kljuc_vrednosti):
        izabrane = []
        for r, kategorija in enumerate(kategorije):
            if tabela.item(r, 0).checkState() != Qt.Checked:
                continue
            tekst = tabela.item(r, 2).text().strip().replace(",", ".")
            try:
                vrednost = float(tekst)
            except ValueError:
                vrednost = -1
            if vrednost <= 0:
                raise ValueError(
                    f"Vrednost za „{kategorija['naziv']}“ mora biti pozitivan broj."
                )
            kopija = copy.deepcopy(kategorija)
            kopija[kljuc_vrednosti] = vrednost
            izabrane.append(kopija)
        return izabrane

    def _u_wgs84(self, pravougaonik):
        transformacija = QgsCoordinateTransform(
            self.iface.mapCanvas().mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance(),
        )
        p = transformacija.transformBoundingBox(pravougaonik)
        return (p.yMinimum(), p.xMinimum(), p.yMaximum(), p.xMaximum())

    def _oblast_mape_wgs84(self):
        return self._u_wgs84(self.iface.mapCanvas().extent())

    def zapocni_crtanje(self):
        platno = self.iface.mapCanvas()
        self._prethodni_alat = platno.mapTool()
        self._alat = QgsMapToolExtent(platno)
        self._alat.extentChanged.connect(self._oblast_nacrtana)
        self._alat.deactivated.connect(self._vrati_dijalog)
        platno.setMapTool(self._alat)
        self.hide()
        self.iface.messageBar().pushInfo(
            "Zone opasnosti",
            "Prevucite misem pravougaonik oblasti analize (drzite levi taster).",
        )

    def _oblast_nacrtana(self, pravougaonik):
        if pravougaonik.width() == 0 or pravougaonik.height() == 0:
            return
        self.oblast = self._u_wgs84(pravougaonik)
        self._prikazi_okvir(pravougaonik)
        self._osvezi_labelu_oblasti()
        platno = self.iface.mapCanvas()
        platno.unsetMapTool(self._alat)
        if self._prethodni_alat is not None:
            platno.setMapTool(self._prethodni_alat)

    def _vrati_dijalog(self):
        self.iface.messageBar().clearWidgets()
        self.show()
        self.raise_()
        self.activateWindow()

    def _prikazi_okvir(self, pravougaonik):
        if self._okvir is None:
            self._okvir = QgsRubberBand(self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
            self._okvir.setStrokeColor(QColor(0, 90, 200))
            self._okvir.setFillColor(QColor(0, 90, 200, 25))
            self._okvir.setWidth(2)
        self._okvir.setToGeometry(QgsGeometry.fromRect(pravougaonik), None)

    def ukloni_okvir(self):
        if self._okvir is not None:
            self.iface.mapCanvas().scene().removeItem(self._okvir)
            self._okvir = None

    def ponisti_oblast(self):
        self.oblast = None
        self.ukloni_okvir()
        self._osvezi_labelu_oblasti()

    def _osvezi_labelu_oblasti(self):
        if self.oblast is None:
            self.labela_oblast.setText(
                "<i>Oblast nije nacrtana – koristi se deo mape prikazan na ekranu.</i>"
            )
            self.dugme_ponisti.setEnabled(False)
        else:
            s, w, n, e = self.oblast
            self.labela_oblast.setText(
                f"Oblast (J, Z, S, I): {s:.4f}, {w:.4f}, {n:.4f}, {e:.4f}"
            )
            self.dugme_ponisti.setEnabled(True)

    def _javi(self, poruka):
        self.izvestaj.append(poruka)
        QApplication.processEvents()

    def preuzmi_podatke(self):
        try:
            hazardi = self._izabrane(self.tabela_hazarda, IZVORI_HAZARDA, "radijus")
            ranjivi = self._izabrane(self.tabela_ranjivih, RANJIVI_OBJEKTI, "tezina")
        except ValueError as greska:
            QMessageBox.warning(self, "Zone opasnosti", str(greska))
            return
        if not hazardi and not ranjivi:
            QMessageBox.warning(self, "Zone opasnosti", "Nije izabrana nijedna kategorija.")
            return

        bbox = self.oblast if self.oblast is not None else self._oblast_mape_wgs84()
        s, w, n, e = bbox
        if (n - s) > MAKS_STEPENI or (e - w) > MAKS_STEPENI:
            odgovor = QMessageBox.question(
                self, "Zone opasnosti",
                "Prikazana oblast je velika, pa preuzimanje moze dugo trajati "
                "ili server moze odbiti upit.\nDa li ipak zelite da nastavite?",
            )
            if odgovor != QMessageBox.Yes:
                return

        folder = self.folder.filePath().strip() or None
        if folder:
            QgsSettings().setValue(PODESAVANJE_FOLDER, folder)

        sve_kategorije = hazardi + ranjivi
        upit = overpass.napravi_upit(bbox, sve_kategorije)

        self.izvestaj.clear()
        self._javi(f"Oblast (J, Z, S, I): {s:.4f}, {w:.4f}, {n:.4f}, {e:.4f}")
        self.dugme_preuzmi.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            podaci, server, putanja = overpass.preuzmi(upit, folder=folder, javi=self._javi)
        except overpass.OverpassGreska as greska:
            QApplication.restoreOverrideCursor()
            self.dugme_preuzmi.setEnabled(True)
            self._javi(f"<span style='color:#b00'>{greska}</span>")
            QMessageBox.critical(
                self, "Zone opasnosti",
                "Preuzimanje nije uspelo. Pokusajte ponovo za nekoliko minuta.\n"
                "Detalji su u prozoru plugina.",
            )
            return
        QApplication.restoreOverrideCursor()
        self.dugme_preuzmi.setEnabled(True)

        objekti, preskoceno = overpass.parsiraj(podaci)
        razvrstano = overpass.razvrstaj(objekti, sve_kategorije)
        slojevi.dodaj_u_projekat(razvrstano, sve_kategorije, GRUPA_ULAZ)

        self.hazardi, self.ranjivi, self.razvrstano = hazardi, ranjivi, razvrstano
        self.bbox = bbox
        self.dugme_zone.setEnabled(True)

        self._javi(f"Server: {server}")
        if putanja:
            self._javi(f"Sirovi odgovor sacuvan: {putanja}")
        self._javi(
            f"Preuzeto objekata: {len(objekti)}"
            + (f" (preskoceno bez geometrije: {preskoceno})" if preskoceno else "")
        )
        self._javi(self._tabela_rezimea(slojevi.rezime(razvrstano, sve_kategorije)))

    @staticmethod
    def _tabela_rezimea(redovi):
        html = (
            "<table border='1' cellspacing='0' cellpadding='3'>"
            "<tr><th>Kategorija</th><th>Tacke</th><th>Linije</th>"
            "<th>Poligoni</th><th>Ukupno</th></tr>"
        )
        for naziv, t, l, p in redovi:
            html += (
                f"<tr><td>{naziv}</td><td>{t}</td><td>{l}</td>"
                f"<td>{p}</td><td><b>{t + l + p}</b></td></tr>"
            )
        return html + "</table>"

    def napravi_zone(self):
        try:
            hazardi = self._izabrane(self.tabela_hazarda, IZVORI_HAZARDA, "radijus")
        except ValueError as greska:
            QMessageBox.warning(self, "Zone opasnosti", str(greska))
            return

        s, w, n, e = self.bbox
        self.epsg = zone.utm_epsg((w + e) / 2, (s + n) / 2)
        self.transformacija = zone.transformacija_u_utm(self.epsg)
        self.hazardi_zone = hazardi
        self.zone = zone.zone_po_izvoru(self.razvrstano, hazardi, self.transformacija)
        self.zarista = zone.spoji_zone([z["zona"] for z in self.zone])
        slojevi.dodaj_zone_u_projekat(self.zone, self.zarista, self.epsg, GRUPA_REZULTATI)

        self._javi(f"<br><b>Zone</b> (racunato u EPSG:{self.epsg}, UTM zona {self.epsg % 100})")
        self._javi(f"Broj zona po izvoru: {len(self.zone)}")
        self._javi(f"Broj spojenih zona (kandidata za zarista): {len(self.zarista)}")
        self.dugme_analiza.setEnabled(True)

    def ucitaj_sacuvane_podatke(self):
        from qgis.PyQt.QtWidgets import QFileDialog

        putanja, _ = QFileDialog.getOpenFileName(
            self, "Izaberite sacuvan odgovor", self.folder.filePath(),
            "Overpass odgovor (overpass_*.json)",
        )
        if not putanja:
            return
        bbox = overpass.oblast_iz_sacuvanog_upita(putanja)
        if bbox is None:
            QMessageBox.warning(
                self, "Zone opasnosti",
                "Pored izabranog fajla nije pronadjen upit (.overpassql) sa oblascu analize.",
            )
            return
        try:
            hazardi = self._izabrane(self.tabela_hazarda, IZVORI_HAZARDA, "radijus")
            ranjivi = self._izabrane(self.tabela_ranjivih, RANJIVI_OBJEKTI, "tezina")
        except ValueError as greska:
            QMessageBox.warning(self, "Zone opasnosti", str(greska))
            return

        podaci = overpass.ucitaj_sacuvan_odgovor(putanja)
        sve_kategorije = hazardi + ranjivi
        objekti, preskoceno = overpass.parsiraj(podaci)
        razvrstano = overpass.razvrstaj(objekti, sve_kategorije)
        slojevi.dodaj_u_projekat(razvrstano, sve_kategorije, GRUPA_ULAZ)

        self.hazardi, self.ranjivi, self.razvrstano = hazardi, ranjivi, razvrstano
        self.bbox = bbox
        self.dugme_zone.setEnabled(True)

        s, w, n, e = bbox
        self.izvestaj.clear()
        self._javi(f"Ucitan sacuvan odgovor: {putanja}")
        self._javi(f"Oblast (J, Z, S, I): {s:.4f}, {w:.4f}, {n:.4f}, {e:.4f}")
        self._javi(
            f"Objekata: {len(objekti)}"
            + (f" (preskoceno bez geometrije: {preskoceno})" if preskoceno else "")
        )
        self._javi(self._tabela_rezimea(slojevi.rezime(razvrstano, sve_kategorije)))

    def analiziraj(self):
        try:
            ranjivi = self._izabrane(self.tabela_ranjivih, RANJIVI_OBJEKTI, "tezina")
        except ValueError as greska:
            QMessageBox.warning(self, "Zone opasnosti", str(greska))
            return

        self.ranjivi_analiza = ranjivi
        ranjivi_objekti = analiza.pripremi_ranjive(self.razvrstano, ranjivi, self.transformacija)
        self.ugrozeni = analiza.pronadji_ugrozene(ranjivi_objekti, self.zone, self.zarista)
        self.zarista_rang = analiza.rangiraj_zarista(self.zarista, self.zone, self.ugrozeni)
        slojevi.dodaj_rezultate_analize(
            self.ugrozeni, self.zarista_rang, self.epsg, GRUPA_REZULTATI
        )
        self._popuni_tabelu_zarista()
        self.dugme_izvoz.setEnabled(True)

        sa_ugrozenima = [z for z in self.zarista_rang if z["broj_ranjivih"] > 0]
        self._javi("<br><b>Analiza</b>")
        self._javi(f"Ranjivih objekata u oblasti: {len(ranjivi_objekti)}")
        self._javi(f"Ugrozenih (u bar jednoj zoni): {len(self.ugrozeni)}")
        self._javi(f"Zarista sa bar jednim ugrozenim objektom: {len(sa_ugrozenima)}")
        self._javi(
            "<i>Indeks je relativan pokazatelj za poredjenje zarista unutar iste "
            "analize, a ne mera rizika.</i>"
        )

    def _popuni_tabelu_zarista(self):
        prikaz = [z for z in self.zarista_rang if z["broj_ranjivih"] > 0]
        tabela = self.tabela_zarista
        tabela.setRowCount(len(prikaz))
        for r, z in enumerate(prikaz):
            vrednosti = [
                z["rang"], f'{z["indeks"]:g}', f'{z["indeks_udaljenost"]:g}',
                z["broj_ranjivih"], z["broj_izvora"],
                ", ".join(f"{k}: {v}" for k, v in z["po_kategoriji"].items()),
            ]
            for k, vrednost in enumerate(vrednosti):
                celija = QTableWidgetItem(str(vrednost))
                celija.setFlags(celija.flags() & ~Qt.ItemIsEditable)
                celija.setData(Qt.UserRole, z["id"])
                tabela.setItem(r, k, celija)
        tabela.resizeColumnsToContents()

    def _zumiraj_na_zariste(self, red, _kolona):
        from qgis.core import QgsGeometry

        zariste_id = self.tabela_zarista.item(red, 0).data(Qt.UserRole)
        zariste = next(z for z in self.zarista_rang if z["id"] == zariste_id)
        platno = self.iface.mapCanvas()
        transformacija = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem(f"EPSG:{self.epsg}"),
            platno.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        geometrija = QgsGeometry(zariste["geometrija"])
        geometrija.transform(transformacija)
        okvir = geometrija.boundingBox()
        okvir.scale(1.3)
        platno.setExtent(okvir)
        platno.refresh()

    def sacuvaj_rezultate(self):
        import datetime

        from qgis.PyQt.QtWidgets import QFileDialog

        roditelj = QFileDialog.getExistingDirectory(
            self, "Izaberite folder za rezultate", self.folder.filePath()
        )
        if not roditelj:
            return
        oznaka = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(roditelj, f"rezultati_{oznaka}")
        os.makedirs(folder, exist_ok=True)

        nazivi_ranjivih = [k["naziv"] for k in self.ranjivi_analiza]
        izvestaj.sacuvaj_csv_ugrozenih(
            self.ugrozeni, os.path.join(folder, "ugrozeni_objekti.csv")
        )
        izvestaj.sacuvaj_csv_zarista(
            self.zarista_rang, nazivi_ranjivih, os.path.join(folder, "zarista.csv")
        )

        grupa = QgsProject.instance().layerTreeRoot().findGroup(GRUPA_REZULTATI)
        slojevi_rezultata = [cvor.layer() for cvor in grupa.findLayers()] if grupa else []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            izvestaj.sacuvaj_geopackage(
                slojevi_rezultata, os.path.join(folder, "rezultati.gpkg")
            )
            izvestaj.napravi_pdf(
                os.path.join(folder, "izvestaj.pdf"),
                self._obuhvat_za_pdf(),
                self.iface.mapCanvas().mapSettings().destinationCrs(),
                slojevi_rezultata,
                self.zarista_rang,
                self._parametri_html(),
            )
        except RuntimeError as greska:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Zone opasnosti", str(greska))
            return
        QApplication.restoreOverrideCursor()
        self._javi(f"<br><b>Rezultati sacuvani u:</b> {folder}")
        self._javi("ugrozeni_objekti.csv, zarista.csv, rezultati.gpkg, izvestaj.pdf")

    def _obuhvat_za_pdf(self):
        platno = self.iface.mapCanvas()
        zarista = [z for z in self.zarista_rang if z["broj_ranjivih"] > 0] or self.zarista_rang
        if not zarista:
            return platno.extent()
        okvir = zarista[0]["geometrija"].boundingBox()
        for z in zarista[1:]:
            okvir.combineExtentWith(z["geometrija"].boundingBox())
        transformacija = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem(f"EPSG:{self.epsg}"),
            platno.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        okvir = transformacija.transformBoundingBox(okvir)
        okvir.scale(1.15)
        return okvir

    def _parametri_html(self):
        import datetime

        s, w, n, e = self.bbox
        radijusi = "<br>".join(
            f"&nbsp;&nbsp;{k['naziv']}: {k['radijus']:g} m" for k in self.hazardi_zone
        )
        tezine = "<br>".join(
            f"&nbsp;&nbsp;{k['naziv']}: {k['tezina']:g}" for k in self.ranjivi_analiza
        )
        return (
            "<b>Parametri analize</b><br>"
            f"Datum analize: {datetime.date.today():%d.%m.%Y.}<br>"
            f"Oblast (J, Z, S, I): {s:.4f}, {w:.4f}, {n:.4f}, {e:.4f}<br>"
            f"Proracun u EPSG:{self.epsg} (UTM zona {self.epsg % 100})<br>"
            f"<b>Radijusi zona:</b><br>{radijusi}<br>"
            f"<b>Tezine ranjivih objekata:</b><br>{tezine}<br>"
            f"Ugrozenih objekata: {len(self.ugrozeni)}"
        )