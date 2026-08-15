"""customtkinter-Oberfläche für BookScouter.

Aufbau: Eingabefeld + Suchen-Button, darunter die Ergebnisse und der
Preisverlauf früherer Abfragen als Diagramm (siehe `bookscouter/chart.py`).

Das Eingabefeld nimmt mehrere ISBNs auf (eine pro Zeile). Jedes Buch bekommt
einen eigenen, auf- und zuklappbaren Block: zugeklappt zeigt er nur das beste
Angebot, aufgeklappt die gewohnte Tabelle aller Shops. Bei genau einer ISBN
ist der Block von Anfang an offen – dann sieht die Oberfläche aus wie vor der
Sammelabfrage.

Wichtig für die Bedienbarkeit: Das Abfragen aller Shops dauert wegen des
Rate-Limitings mehrere Sekunden, bei mehreren Titeln entsprechend länger.
Deshalb läuft die Suche in einem Hintergrund-Thread und schickt ihre
Ergebnisse über eine Queue an den Tk-Mainloop, der sie einzeln einträgt – die
Oberfläche friert nicht ein und jeder Shop erscheint, sobald er geantwortet
hat. Aus demselben Grund lässt sich ein laufender Durchgang abbrechen.

Alle Datenbankzugriffe passieren im Worker-Thread mit einer eigenen
Verbindung: sqlite3-Verbindungen dürfen nicht über Threads hinweg geteilt
werden.
"""

import queue
import sys
import threading
import tkinter
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import customtkinter as ctk

from bookscouter.chart import PreisverlaufChart
from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.isbn import parse_isbn_liste
from bookscouter.scrapers import ALL_SCRAPERS

# Farben jeweils als (Hell-Modus, Dunkel-Modus).
FARBE_GUENSTIGER = ("#1a7f37", "#3fb950")
FARBE_TEURER = ("#cf222e", "#f85149")
FARBE_GEDAEMPFT = ("gray45", "gray60")
FARBE_LINK = ("#0969da", "#4493f8")

SPALTEN = ("Shop", "Titel", "Preis", "", "Verfügbarkeit", "")
# Spalte, über die sich Zeilen ohne Preis (nicht geführt, Fehler) erstrecken.
SPALTEN_RESTBREITE = len(SPALTEN) - 1

# Verfügbarkeiten, die als "kann man kaufen" bzw. "kann man nicht kaufen"
# eingefärbt werden; alles andere (inkl. "Unbekannt") bleibt gedämpft.
VERFUEGBAR = {"Auf Lager", "Nur im Laden", "Nur online", "Nur begrenzt"}
NICHT_VERFUEGBAR = {"Nicht auf Lager", "Ausverkauft", "Nicht mehr lieferbar"}

# Zeilen des Hauptfensters als Namen statt als Zahlen: sonst verschiebt jede
# neu eingefügte Zeile die Nummern in mehreren Methoden gleichzeitig.
(
    ZEILE_EINGABE,
    ZEILE_SHOPS,
    ZEILE_STATUS,
    ZEILE_ERGEBNISSE,
    ZEILE_VERLAUF_TITEL,
    ZEILE_VERLAUF,
) = range(6)

HINWEIS = "ISBNs eingeben – eine pro Zeile. Strg+Enter oder auf Suchen klicken."


def format_preis(wert: float) -> str:
    return f"{wert:.2f} €".replace(".", ",")


def shop_namen() -> list[str]:
    """Anzeigenamen aller Shops in der Reihenfolge von ALL_SCRAPERS."""
    return [scraper_cls().shop_name for scraper_cls in ALL_SCRAPERS]


def gewaehlte_scraper(auswahl: dict[str, bool]) -> list:
    """Die angehakten Scraper-Klassen, in der Reihenfolge von ALL_SCRAPERS.

    Ein Shop, der in der Auswahl gar nicht auftaucht, gilt als angehakt: eine
    lückenhafte Auswahl soll höchstens einen Shop zu viel abfragen, aber nie
    stillschweigend einen verschlucken.
    """
    return [cls for cls in ALL_SCRAPERS if auswahl.get(cls().shop_name, True)]


def icon_pfad() -> Path:
    """Pfad zu `BookScouter.ico` – aus dem Quellordner oder aus der .exe.

    PyInstaller entpackt die gebündelten Dateien beim Start in ein temporäres
    Verzeichnis und hinterlegt es in `sys._MEIPASS`; im Quellbetrieb liegt
    das Icon dagegen einfach neben dem Paket.
    """
    basis = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return basis / "assets" / "BookScouter.ico"


@dataclass
class Fehlerzeile:
    """Ein Shop, der nicht antworten konnte – steht in derselben Liste wie
    die Ergebnisse, damit die Tabelle in einem Rutsch sortiert werden kann."""

    shop: str
    text: str


@dataclass
class Buch:
    """Ein abgefragter Titel mit allem, was zu seinem Block gehört.

    Vor der Sammelabfrage lagen diese Felder flach in der App; bei mehreren
    Titeln gleichzeitig braucht jeder seinen eigenen Satz – sonst würden sich
    Preisverlauf und "war vorher teurer" zwischen den Büchern vermischen.
    """

    isbn: str
    titel: str | None = None
    # Eingetroffene Zeilen dieses Buchs: ScrapeResult oder Fehlerzeile.
    zeilen: list = field(default_factory=list)
    # Letzter bekannter Preis je Shop aus der Datenbank.
    vorherige_preise: dict[str, dict] = field(default_factory=dict)
    # Historie plus die Ergebnisse der laufenden Suche fürs Diagramm.
    verlaufsdaten: list[dict] = field(default_factory=list)
    offen: bool = False

    @property
    def gefunden(self) -> bool:
        return any(getattr(zeile, "gefunden", False) for zeile in self.zeilen)


def sortierschluessel(zeile) -> tuple[int, float]:
    """Günstigstes Angebot zuerst, nicht Lieferbares ans Ende.

    Vier Gruppen, innerhalb jeder Gruppe nach Preis aufsteigend:
    sofort lieferbar, unklar (u.a. "Unbekannt" und "Vorbestellbar"),
    vergriffen, und zuletzt Shops ohne Angebot bzw. mit Fehler – die
    haben keinen Preis, den man vergleichen könnte.
    """
    if isinstance(zeile, Fehlerzeile) or not zeile.gefunden:
        return (3, 0.0)
    if zeile.verfuegbarkeit in VERFUEGBAR:
        return (0, zeile.preis)
    if zeile.verfuegbarkeit in NICHT_VERFUEGBAR:
        return (2, zeile.preis)
    return (1, zeile.preis)


def bestes_angebot(zeilen: list):
    """Das Angebot, das im zugeklappten Block steht – oder None.

    Bewusst dieselbe Reihenfolge wie in der aufgeklappten Tabelle: das oberste
    Angebot dort ist das, was hier oben steht. Ein vergriffener Titel für 9 €
    ist damit *nicht* das beste Angebot, solange ein lieferbares existiert –
    kaufen kann man nur, was da ist.
    """
    for zeile in sorted(zeilen, key=sortierschluessel):
        if not isinstance(zeile, Fehlerzeile) and zeile.gefunden:
            return zeile
    return None


def fortschritt_text(
    shop: str, buch_nummer: int, buch_gesamt: int, shop_nummer: int, shop_gesamt: int
) -> str:
    """Statuszeile während der Suche.

    Bei einer einzelnen ISBN bleibt es beim gewohnten Text ohne Buchzählung –
    "Buch 1 von 1" wäre nur Lärm.
    """
    shops = f"Frage {shop} ab … ({shop_nummer} von {shop_gesamt})"
    if buch_gesamt == 1:
        return shops
    return f"Buch {buch_nummer} von {buch_gesamt} · {shops}"


class BookScouterApp(ctk.CTk):
    # Weiterhin als Methode erreichbar: die Sortierung gehört zur Darstellung.
    _sortierschluessel = staticmethod(sortierschluessel)

    def __init__(self) -> None:
        super().__init__()

        self.title("BookScouter")
        self.geometry("860x680")
        self.minsize(700, 520)
        self._setze_fenstersymbol()

        self._queue: queue.Queue | None = None
        self._laeuft = False
        self._abbruch: threading.Event | None = None
        # Abgefragte Titel in Eingabereihenfolge, ISBN -> Buch.
        self._buecher: dict[str, Buch] = {}
        # Buch, dessen Preisverlauf das Diagramm gerade zeigt.
        self._chart_isbn: str | None = None
        # Wie viele Shops die laufende Suche je Buch abfragt – nicht zwingend
        # alle, seit die Shops einzeln abwählbar sind.
        self._abgefragte_shops = len(ALL_SCRAPERS)
        self._erledigte_schritte = 0
        self._gesamt_schritte = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(ZEILE_ERGEBNISSE, weight=1)

        self._baue_eingabe()
        self._baue_shop_auswahl()
        self._baue_status()
        self._baue_ergebnisbereich()
        self._baue_verlauf()

        self.eingabe.focus()

    # ------------------------------------------------------------------ Aufbau

    def _setze_fenstersymbol(self) -> None:
        """Setzt das Icon für Titelleiste und Taskleiste.

        Fehlt oder klemmt die Datei, läuft die App ohne eigenes Symbol
        weiter – ein hübscheres Fenster ist keinen Absturz wert. Der
        verzögerte zweite Versuch ist nötig, weil customtkinter beim Aufbau
        sein eigenes Symbol setzt und das direkt gesetzte sonst überschreibt.
        """
        pfad = str(icon_pfad())

        def setzen() -> None:
            try:
                self.iconbitmap(pfad)
            except tkinter.TclError:
                pass

        setzen()
        self.after(300, setzen)

    def _baue_eingabe(self) -> None:
        rahmen = ctk.CTkFrame(self, fg_color="transparent")
        rahmen.grid(row=ZEILE_EINGABE, column=0, padx=20, pady=(20, 10), sticky="ew")
        rahmen.grid_columnconfigure(0, weight=1)

        # Mehrzeilig, damit eine ganze Wunschliste hineinpasst. Enter macht
        # hier eine neue Zeile und darf die Suche deshalb nicht mehr starten;
        # dafür gibt es den Button und Strg+Enter.
        self.eingabe = ctk.CTkTextbox(rahmen, height=92, wrap="none")
        self.eingabe.grid(row=0, column=0, sticky="ew")
        self.eingabe.bind("<Control-Return>", self._auf_tastenkuerzel)

        self.such_button = ctk.CTkButton(
            rahmen, text="Suchen", width=120, height=40, command=self._button_gedrueckt
        )
        self.such_button.grid(row=0, column=1, padx=(10, 0), sticky="n")

    def _auf_tastenkuerzel(self, _event) -> str:
        """Strg+Enter startet die Suche, ohne zusätzlich eine Zeile einzufügen."""
        self._button_gedrueckt()
        return "break"

    def _baue_shop_auswahl(self) -> None:
        """Je Shop ein Kästchen; beim Start sind alle angehakt.

        Die Auswahl gilt nur für die laufende Sitzung und wird bewusst nicht
        gespeichert: dafür bräuchte es eine Einstellungsdatei, und der
        Normalfall bleibt "alle Shops fragen".
        """
        rahmen = ctk.CTkFrame(self, fg_color="transparent")
        rahmen.grid(row=ZEILE_SHOPS, column=0, padx=20, pady=(0, 10), sticky="ew")

        self._shop_auswahl: dict[str, ctk.BooleanVar] = {}
        self._shop_kaestchen: list[ctk.CTkCheckBox] = []
        for spalte, name in enumerate(shop_namen()):
            variable = ctk.BooleanVar(value=True)
            kaestchen = ctk.CTkCheckBox(
                rahmen, text=name, variable=variable, font=ctk.CTkFont(size=12),
                checkbox_width=18, checkbox_height=18,
            )
            kaestchen.grid(row=0, column=spalte, padx=(0, 14), sticky="w")
            self._shop_auswahl[name] = variable
            self._shop_kaestchen.append(kaestchen)

    def _aktuelle_auswahl(self) -> dict[str, bool]:
        return {name: variable.get() for name, variable in self._shop_auswahl.items()}

    def _sperre_shop_auswahl(self, gesperrt: bool) -> None:
        """Während einer laufenden Suche nicht umstellbar – sonst passt die
        Fortschrittsanzeige ("3 von 5") nicht mehr zu dem, was abgefragt wird."""
        for kaestchen in self._shop_kaestchen:
            kaestchen.configure(state="disabled" if gesperrt else "normal")

    def _baue_status(self) -> None:
        rahmen = ctk.CTkFrame(self, fg_color="transparent")
        rahmen.grid(row=ZEILE_STATUS, column=0, padx=20, pady=(0, 10), sticky="ew")
        rahmen.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            rahmen, text=HINWEIS, anchor="w", text_color=FARBE_GEDAEMPFT,
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        self.fortschritt = ctk.CTkProgressBar(rahmen, height=4)
        self.fortschritt.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        self.fortschritt.set(0)

    def _baue_ergebnisbereich(self) -> None:
        self.ergebnisse = ctk.CTkScrollableFrame(self, label_text="Aktuelle Preise")
        self.ergebnisse.grid(row=ZEILE_ERGEBNISSE, column=0, padx=20, pady=(0, 10), sticky="nsew")
        # Titelspalte darf den übrigen Platz bekommen.
        self.ergebnisse.grid_columnconfigure(1, weight=1)
        self._zeile = 0

    def _baue_verlauf(self) -> None:
        self.verlauf_titel = ctk.CTkLabel(
            self, text="Preisverlauf", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=FARBE_GEDAEMPFT,
        )
        self.verlauf = PreisverlaufChart(self)

    # ------------------------------------------------------------------- Suche

    def _button_gedrueckt(self) -> None:
        """Ein Button für beides: startet die Suche bzw. bricht sie ab."""
        if self._laeuft:
            self._brich_ab()
        else:
            self._starte_suche()

    def _brich_ab(self) -> None:
        if self._abbruch is not None:
            self._abbruch.set()
        self.such_button.configure(state="disabled", text="Bricht ab …")

    def _starte_suche(self) -> None:
        # ISBN-13 ist der einheitliche Schlüssel: sonst bekäme dasselbe Buch je
        # nach eingetippter Schreibweise zwei getrennte Preisverläufe.
        isbns = parse_isbn_liste(self.eingabe.get("1.0", "end"))
        if not isbns:
            self._setze_status("Bitte zuerst mindestens eine ISBN eingeben.")
            return

        scraper_klassen = gewaehlte_scraper(self._aktuelle_auswahl())
        if not scraper_klassen:
            self._setze_status("Mindestens einen Shop auswählen.")
            return

        self._laeuft = True
        self._abbruch = threading.Event()
        self._abgefragte_shops = len(scraper_klassen)
        self._erledigte_schritte = 0
        self._gesamt_schritte = len(isbns) * len(scraper_klassen)
        # Bei einer einzelnen ISBN ist der Block sofort offen – die Suche nach
        # einem Titel soll sich nicht nach Aufklappen anfühlen.
        self._buecher = {
            isbn: Buch(isbn=isbn, offen=len(isbns) == 1) for isbn in isbns
        }
        self._chart_isbn = isbns[0] if len(isbns) == 1 else None

        self.such_button.configure(text="Abbrechen")
        self._sperre_shop_auswahl(True)
        self.fortschritt.set(0)
        self._zeichne_tabelle()
        self._verstecke_verlauf()

        self._queue = queue.Queue()
        threading.Thread(
            target=self._arbeite,
            args=(isbns, scraper_klassen, self._queue, self._abbruch),
            daemon=True,
        ).start()
        self.after(100, self._pruefe_queue)

    @staticmethod
    def _arbeite(
        isbns: list[str],
        scraper_klassen: list,
        ausgabe: queue.Queue,
        abbruch: threading.Event,
    ) -> None:
        """Läuft im Hintergrund-Thread: DB lesen, scrapen, DB schreiben."""
        try:
            conn = connect()
            try:
                # Die Scraper einmal anlegen und über alle Bücher hinweg
                # weiterverwenden: der Mindestabstand zwischen zwei Anfragen an
                # denselben Shop hängt am einzelnen Scraper-Objekt
                # (`Scraper._get`). Pro Buch neue Objekte würden ihn jedes Mal
                # vergessen und den Shop schneller anfragen als zugesagt.
                scraper = [scraper_cls() for scraper_cls in scraper_klassen]

                for buch_nummer, isbn in enumerate(isbns, start=1):
                    if abbruch.is_set():
                        break

                    historie = [dict(zeile) for zeile in get_price_history(conn, isbn)]
                    ausgabe.put(("historie", isbn, historie))

                    for shop_nummer, shop in enumerate(scraper, start=1):
                        if abbruch.is_set():
                            break

                        ausgabe.put((
                            "fortschritt", isbn, shop.shop_name,
                            buch_nummer, len(isbns), shop_nummer, len(scraper),
                        ))
                        try:
                            ergebnis = shop.scrape(isbn)
                        except Exception as fehler:  # ein Shop darf die Suche nicht kippen
                            ausgabe.put(("fehler", isbn, shop.shop_name, str(fehler)))
                            continue

                        if ergebnis.gefunden:
                            save_lookup(
                                conn, isbn=isbn, titel=ergebnis.titel,
                                shop=ergebnis.shop, preis=ergebnis.preis,
                            )
                        ausgabe.put(("ergebnis", isbn, ergebnis))
            finally:
                conn.close()
        except Exception as fehler:
            ausgabe.put(("abbruch", str(fehler)))
        finally:
            ausgabe.put(("fertig", abbruch.is_set()))

    def _pruefe_queue(self) -> None:
        """Läuft im Mainloop und trägt ein, was der Worker geschickt hat."""
        try:
            while True:
                self._verarbeite(self._queue.get_nowait())
        except queue.Empty:
            pass

        if self._laeuft:
            self.after(100, self._pruefe_queue)

    def _verarbeite(self, nachricht: tuple) -> None:
        art = nachricht[0]

        if art == "historie":
            _, isbn, historie = nachricht
            buch = self._buecher.get(isbn)
            if buch is not None:
                buch.vorherige_preise = self._letzte_preise(historie)
                buch.verlaufsdaten = list(historie)
        elif art == "fortschritt":
            _, _isbn, shop, buch_nummer, buch_gesamt, shop_nummer, shop_gesamt = nachricht
            self._setze_status(
                fortschritt_text(shop, buch_nummer, buch_gesamt, shop_nummer, shop_gesamt)
            )
        elif art == "ergebnis":
            self._zeige_ergebnis(nachricht[1], nachricht[2])
        elif art == "fehler":
            self._zeige_fehlerzeile(nachricht[1], nachricht[2], nachricht[3])
        elif art == "abbruch":
            self._setze_status(f"Suche abgebrochen: {nachricht[1]}")
        elif art == "fertig":
            self._beende_suche(abgebrochen=nachricht[1])

    def _schritt_erledigt(self) -> None:
        self._erledigte_schritte += 1
        if self._gesamt_schritte:
            self.fortschritt.set(self._erledigte_schritte / self._gesamt_schritte)

    def _beende_suche(self, abgebrochen: bool = False) -> None:
        self._laeuft = False
        self._abbruch = None
        self.such_button.configure(state="normal", text="Suchen")
        self._sperre_shop_auswahl(False)
        self._zeige_verlauf()

        if abgebrochen:
            self.fortschritt.set(0)
            self._setze_status("Abgebrochen – die bisherigen Ergebnisse bleiben stehen.")
            return

        self.fortschritt.set(1)
        self._setze_status(self._abschlusstext())

    def _abschlusstext(self) -> str:
        """Bei einem Titel zählt der Text die Shops, bei mehreren die Titel."""
        if len(self._buecher) == 1:
            buch = next(iter(self._buecher.values()))
            treffer = sum(1 for zeile in buch.zeilen if getattr(zeile, "gefunden", False))
            if treffer == 0:
                # "Kein Shop" wäre gelogen, wenn gar nicht alle gefragt wurden.
                return "Keiner der gewählten Shops führt diese ISBN."
            return f"Fertig – {treffer} von {self._abgefragte_shops} Shops führen den Titel."

        gefunden = sum(1 for buch in self._buecher.values() if buch.gefunden)
        if gefunden == 0:
            return "Keiner der gewählten Shops führt einen dieser Titel."
        return (
            f"Fertig – {gefunden} von {len(self._buecher)} Titeln bei mindestens "
            "einem Shop gefunden."
        )

    # -------------------------------------------------------------- Ergebnisse

    @staticmethod
    def _letzte_preise(historie: list[dict]) -> dict[str, dict]:
        """Letzter bekannter Preis je Shop – die Historie ist aufsteigend sortiert."""
        return {eintrag["shop"]: eintrag for eintrag in historie}

    def _zeige_ergebnis(self, isbn: str, ergebnis) -> None:
        """Nimmt ein eingetroffenes Shop-Ergebnis auf und zeichnet neu."""
        self._schritt_erledigt()
        buch = self._buecher.get(isbn)
        if buch is None:
            return

        if ergebnis.gefunden:
            if buch.titel is None:
                buch.titel = ergebnis.titel
            # Das aktuelle Ergebnis gehört in den Verlauf, sonst würde das
            # Diagramm die gerade gespeicherte Abfrage erst beim nächsten
            # Start zeigen.
            buch.verlaufsdaten.append(
                {
                    "shop": ergebnis.shop,
                    "preis": ergebnis.preis,
                    "datum": datetime.now(timezone.utc).isoformat(),
                }
            )

        buch.zeilen.append(ergebnis)
        self._zeichne_tabelle()

    def _zeige_fehlerzeile(self, isbn: str, shop: str, fehler: str) -> None:
        self._schritt_erledigt()
        buch = self._buecher.get(isbn)
        if buch is None:
            return
        buch.zeilen.append(Fehlerzeile(shop=shop, text=fehler))
        self._zeichne_tabelle()

    def _zeichne_tabelle(self) -> None:
        """Zeichnet alle Bücher neu: Kopfzeile je Buch, Shops nur wenn offen.

        Nach jedem Shop komplett neu statt nur anzuhängen: die Sortierung
        hängt an den Preisen, und der günstigste Shop kann erst als letzter
        antworten. Teuer wird das nicht, weil ein zugeklapptes Buch genau
        eine Zeile ist – gezeichnet wird also selten mehr als eine
        Shop-Tabelle plus ein paar Kopfzeilen.
        """
        for kind in self.ergebnisse.winfo_children():
            kind.destroy()
        self._zeile = 0

        # Die Spaltenüberschriften beschreiben die Shop-Zeilen; ohne offenes
        # Buch stünden sie über lauter Buchtiteln und wären irreführend.
        if any(buch.offen for buch in self._buecher.values()):
            self._schreibe_kopfzeile()

        for buch in self._buecher.values():
            self._zeichne_buchkopf(buch)
            if not buch.offen:
                continue
            for zeile in sorted(buch.zeilen, key=sortierschluessel):
                if isinstance(zeile, Fehlerzeile):
                    self._zeichne_fehlerzeile(zeile)
                else:
                    self._zeichne_ergebniszeile(zeile, buch)

    def _schreibe_kopfzeile(self) -> None:
        for spalte, titel in enumerate(SPALTEN):
            ctk.CTkLabel(
                self.ergebnisse, text=titel, anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"), text_color=FARBE_GEDAEMPFT,
            ).grid(row=0, column=spalte, padx=(0, 14), pady=(0, 6), sticky="w")
        self._zeile = 1

    def _zelle(self, spalte: int, text: str, **kwargs) -> None:
        ctk.CTkLabel(self.ergebnisse, text=text, anchor="w", **kwargs).grid(
            row=self._zeile, column=spalte, padx=(0, 14), pady=3, sticky="w"
        )

    def _link_zelle(self, spalte: int, url: str) -> None:
        """Klickbarer Verweis auf die Produktseite des Shops.

        customtkinter kennt kein Link-Widget; ein Label mit Unterstreichung,
        Hand-Cursor und Klick-Binding ist die übliche Lösung dafür.
        """
        link = ctk.CTkLabel(
            self.ergebnisse, text="Zum Angebot ↗", anchor="w",
            text_color=FARBE_LINK, cursor="hand2",
            font=ctk.CTkFont(size=12, underline=True),
        )
        link.grid(row=self._zeile, column=spalte, padx=(0, 14), pady=3, sticky="w")
        link.bind("<Button-1>", lambda _event, ziel=url: webbrowser.open(ziel))

    def _zeichne_buchkopf(self, buch: Buch) -> None:
        """Die anklickbare Zeile eines Buchs: Titel, bestes Angebot, Pfeil."""
        beschriftung = f"{'▼' if buch.offen else '▶'}  {buch.titel or buch.isbn}"
        anklickbar = [
            self._kopf_label(
                beschriftung, spalte=0, spannweite=2,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
        ]

        bestes = bestes_angebot(buch.zeilen)
        if bestes is not None:
            anklickbar.append(self._kopf_label(
                format_preis(bestes.preis), spalte=2,
                font=ctk.CTkFont(size=13, weight="bold"),
            ))
            anklickbar.append(self._kopf_label(
                f"bei {bestes.shop}", spalte=3, spannweite=2,
                text_color=FARBE_GEDAEMPFT,
            ))
        elif self._buch_fertig(buch):
            # Erst wenn alle Shops geantwortet haben – währenddessen wäre
            # "nicht gefunden" schlicht falsch.
            anklickbar.append(self._kopf_label(
                "— nicht gefunden —", spalte=2, spannweite=3,
                text_color=FARBE_GEDAEMPFT,
            ))

        for label in anklickbar:
            label.bind("<Button-1>", lambda _event, isbn=buch.isbn: self._klapp_um(isbn))

        self._zeile += 1

    def _kopf_label(self, text: str, spalte: int, spannweite: int = 1, **kwargs):
        label = ctk.CTkLabel(
            self.ergebnisse, text=text, anchor="w", cursor="hand2", **kwargs
        )
        label.grid(
            row=self._zeile, column=spalte, columnspan=spannweite,
            padx=(0, 14), pady=(8, 3), sticky="w",
        )
        return label

    def _buch_fertig(self, buch: Buch) -> bool:
        """Haben alle abgefragten Shops zu diesem Buch geantwortet?"""
        return len(buch.zeilen) >= self._abgefragte_shops

    def _klapp_um(self, isbn: str) -> None:
        buch = self._buecher.get(isbn)
        if buch is None:
            return
        buch.offen = not buch.offen
        if buch.offen:
            # Das zuletzt geöffnete Buch bestimmt, welchen Preisverlauf das
            # Diagramm zeigt.
            self._chart_isbn = isbn
        self._zeichne_tabelle()
        self._zeige_verlauf()

    def _zeichne_ergebniszeile(self, ergebnis, buch: Buch) -> None:
        if not ergebnis.gefunden:
            self._zelle(0, ergebnis.shop, text_color=FARBE_GEDAEMPFT)
            ctk.CTkLabel(
                self.ergebnisse, text="— nicht geführt —", anchor="w",
                text_color=FARBE_GEDAEMPFT,
            ).grid(
                row=self._zeile, column=1, columnspan=SPALTEN_RESTBREITE,
                padx=(0, 14), pady=3, sticky="w",
            )
            self._zeile += 1
            return

        self._zelle(0, ergebnis.shop)
        self._zelle(1, ergebnis.titel)
        self._zelle(2, format_preis(ergebnis.preis),
                    font=ctk.CTkFont(size=13, weight="bold"))

        # Der frühere Preis selbst steht im Diagramm; hier genügt die
        # Veränderung gegenüber der letzten Abfrage.
        vorher = buch.vorherige_preise.get(ergebnis.shop)
        if vorher is not None:
            text, farbe = self._differenz(ergebnis.preis, vorher["preis"])
            self._zelle(3, text, text_color=farbe)

        self._zelle(4, ergebnis.verfuegbarkeit,
                    text_color=self._verfuegbarkeits_farbe(ergebnis.verfuegbarkeit))

        # Ein Treffer ohne URL sollte nicht vorkommen, würde aber sonst ein
        # ins Leere zeigendes "Zum Angebot" ergeben.
        if ergebnis.url:
            self._link_zelle(5, ergebnis.url)

        self._zeile += 1

    @staticmethod
    def _verfuegbarkeits_farbe(verfuegbarkeit: str) -> tuple[str, str]:
        """Grün für lieferbar, rot für vergriffen – sonst gedämpft.

        Grün/Rot sind dieselben Farben wie bei der Preisdifferenz: hier wie
        dort heissen sie schlicht "gut" bzw. "schlecht" für die Kaufende.
        """
        if verfuegbarkeit in VERFUEGBAR:
            return FARBE_GUENSTIGER
        if verfuegbarkeit in NICHT_VERFUEGBAR:
            return FARBE_TEURER
        return FARBE_GEDAEMPFT

    @staticmethod
    def _differenz(jetzt: float, vorher: float) -> tuple[str, tuple[str, str]]:
        """Text und Farbe für die Preisdifferenz gegenüber der letzten Abfrage."""
        differenz = jetzt - vorher
        if abs(differenz) < 0.005:
            return "– unverändert", FARBE_GEDAEMPFT
        pfeil = "▲" if differenz > 0 else "▼"
        farbe = FARBE_TEURER if differenz > 0 else FARBE_GUENSTIGER
        betrag = f"{differenz:+.2f}".replace(".", ",")
        return f"{pfeil} {betrag} €", farbe

    def _zeichne_fehlerzeile(self, zeile: "Fehlerzeile") -> None:
        self._zelle(0, zeile.shop, text_color=FARBE_GEDAEMPFT)
        ctk.CTkLabel(
            self.ergebnisse, text=f"Fehler: {zeile.text}", anchor="w",
            text_color=FARBE_TEURER,
        ).grid(
            row=self._zeile, column=1, columnspan=SPALTEN_RESTBREITE,
            padx=(0, 14), pady=3, sticky="w",
        )
        self._zeile += 1

    # ------------------------------------------------------------ Preisverlauf

    def _chart_buch(self) -> Buch | None:
        """Das Buch, dessen Verlauf gezeigt wird: das zuletzt geöffnete.

        Ist es inzwischen zugeklappt, rückt das oberste noch offene Buch nach –
        ein Diagramm ohne sichtbares Buch dazu wäre nicht zuzuordnen.
        """
        buch = self._buecher.get(self._chart_isbn) if self._chart_isbn else None
        if buch is not None and buch.offen:
            return buch
        return next((offen for offen in self._buecher.values() if offen.offen), None)

    def _zeige_verlauf(self) -> None:
        buch = self._chart_buch()
        if buch is None or not buch.verlaufsdaten:
            self._verstecke_verlauf()
            return

        titel = buch.titel or buch.isbn
        self.verlauf_titel.configure(
            text="Preisverlauf" if len(self._buecher) == 1 else f"Preisverlauf – {titel}"
        )
        self.verlauf_titel.grid(row=ZEILE_VERLAUF_TITEL, column=0, padx=20, pady=(4, 4), sticky="ew")
        self.verlauf.grid(row=ZEILE_VERLAUF, column=0, padx=20, pady=(0, 16), sticky="ew")
        # Immer alle Shops übergeben, nicht nur die angehakten: die Farbe hängt
        # am Shop, nicht daran, wer bei dieser Suche gefragt wurde – sonst
        # wechselt eine Linie die Farbe, sobald man einen Shop abwählt.
        self.verlauf.zeige(buch.verlaufsdaten, shop_namen())

    def _verstecke_verlauf(self) -> None:
        self.verlauf_titel.grid_remove()
        self.verlauf.grid_remove()

    # ----------------------------------------------------------------- Status

    def _setze_status(self, text: str) -> None:
        self.status_label.configure(text=text)


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    BookScouterApp().mainloop()


if __name__ == "__main__":
    main()
