"""customtkinter-Oberfläche für BookScouter.

Aufbau: Eingabefeld + Suchen-Button, darunter die Ergebnistabelle und der
Preisverlauf früherer Abfragen als Diagramm (siehe `bookscouter/chart.py`).

Wichtig für die Bedienbarkeit: Das Abfragen aller Shops dauert wegen des
Rate-Limitings mehrere Sekunden. Deshalb läuft die Suche in einem
Hintergrund-Thread und schickt ihre Ergebnisse über eine Queue an den
Tk-Mainloop, der sie einzeln einträgt – die Oberfläche friert nicht ein und
jeder Shop erscheint, sobald er geantwortet hat.

Alle Datenbankzugriffe passieren im Worker-Thread mit einer eigenen
Verbindung: sqlite3-Verbindungen dürfen nicht über Threads hinweg geteilt
werden.
"""

import queue
import sys
import threading
import tkinter
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import customtkinter as ctk

from bookscouter.chart import PreisverlaufChart
from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.isbn import to_isbn13
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


class BookScouterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("BookScouter")
        self.geometry("860x680")
        self.minsize(700, 520)
        self._setze_fenstersymbol()

        self._queue: queue.Queue | None = None
        self._laeuft = False
        self._vorherige_preise: dict[str, dict] = {}
        self._treffer = 0
        # Alle bisher eingetroffenen Zeilen dieser Suche (Ergebnisse und
        # Fehler); die Tabelle wird daraus jedes Mal sortiert neu gezeichnet.
        self._zeilen: list = []
        # Historie aus der Datenbank plus die Ergebnisse der laufenden Suche,
        # damit das Diagramm den heutigen Stand direkt mitzeigt.
        self._verlaufsdaten: list[dict] = []
        # Wie viele Shops die laufende Suche abfragt – nicht zwingend alle,
        # seit die Shops einzeln abwählbar sind.
        self._abgefragte_shops = len(ALL_SCRAPERS)

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

        self.eingabe = ctk.CTkEntry(
            rahmen, placeholder_text="ISBN eingeben, z. B. 9783546100335", height=40
        )
        self.eingabe.grid(row=0, column=0, sticky="ew")
        self.eingabe.bind("<Return>", lambda _event: self._starte_suche())

        self.such_button = ctk.CTkButton(
            rahmen, text="Suchen", width=120, height=40, command=self._starte_suche
        )
        self.such_button.grid(row=0, column=1, padx=(10, 0))

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
            rahmen, text="Eine ISBN eingeben und auf Suchen klicken.",
            anchor="w", text_color=FARBE_GEDAEMPFT,
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

    def _starte_suche(self) -> None:
        if self._laeuft:
            return

        # ISBN-13 ist der einheitliche Schlüssel: sonst bekäme dasselbe Buch je
        # nach eingetippter Schreibweise zwei getrennte Preisverläufe.
        isbn = to_isbn13(self.eingabe.get())
        if not isbn:
            self._setze_status("Bitte zuerst eine ISBN eingeben.")
            return

        scraper_klassen = gewaehlte_scraper(self._aktuelle_auswahl())
        if not scraper_klassen:
            self._setze_status("Mindestens einen Shop auswählen.")
            return

        self._laeuft = True
        self._abgefragte_shops = len(scraper_klassen)
        self._treffer = 0
        self._vorherige_preise = {}
        self._verlaufsdaten = []
        self._zeilen = []
        self.such_button.configure(state="disabled", text="Sucht …")
        self._sperre_shop_auswahl(True)
        self.fortschritt.configure(mode="indeterminate")
        self.fortschritt.start()
        self._leere_ergebnisse()
        self._verstecke_verlauf()

        self._queue = queue.Queue()
        threading.Thread(
            target=self._arbeite, args=(isbn, scraper_klassen, self._queue), daemon=True
        ).start()
        self.after(100, self._pruefe_queue)

    @staticmethod
    def _arbeite(isbn: str, scraper_klassen: list, ausgabe: queue.Queue) -> None:
        """Läuft im Hintergrund-Thread: DB lesen, scrapen, DB schreiben."""
        try:
            conn = connect()
            try:
                historie = [dict(zeile) for zeile in get_price_history(conn, isbn)]
                ausgabe.put(("historie", historie))

                gesamt = len(scraper_klassen)
                for nummer, scraper_cls in enumerate(scraper_klassen, start=1):
                    scraper = scraper_cls()
                    ausgabe.put(("fortschritt", scraper.shop_name, nummer, gesamt))
                    try:
                        ergebnis = scraper.scrape(isbn)
                    except Exception as fehler:  # ein Shop darf die Suche nicht kippen
                        ausgabe.put(("fehler", scraper.shop_name, str(fehler)))
                        continue

                    if ergebnis.gefunden:
                        save_lookup(
                            conn, isbn=isbn, titel=ergebnis.titel,
                            shop=ergebnis.shop, preis=ergebnis.preis,
                        )
                    ausgabe.put(("ergebnis", ergebnis))
            finally:
                conn.close()
        except Exception as fehler:
            ausgabe.put(("abbruch", str(fehler)))
        finally:
            ausgabe.put(("fertig",))

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
            self._merke_vorherige_preise(nachricht[1])
            self._verlaufsdaten = list(nachricht[1])
        elif art == "fortschritt":
            _, shop, nummer, gesamt = nachricht
            self._setze_status(f"Frage {shop} ab … ({nummer} von {gesamt})")
        elif art == "ergebnis":
            self._zeige_ergebnis(nachricht[1])
        elif art == "fehler":
            self._zeige_fehlerzeile(nachricht[1], nachricht[2])
        elif art == "abbruch":
            self._setze_status(f"Suche abgebrochen: {nachricht[1]}")
        elif art == "fertig":
            self._beende_suche()

    def _beende_suche(self) -> None:
        self._laeuft = False
        self.fortschritt.stop()
        self.fortschritt.configure(mode="determinate")
        self.fortschritt.set(0)
        self.such_button.configure(state="normal", text="Suchen")
        self._sperre_shop_auswahl(False)
        self._zeige_verlauf()

        gesamt = self._abgefragte_shops
        if self._treffer == 0:
            # "Kein Shop" wäre gelogen, wenn gar nicht alle gefragt wurden.
            self._setze_status("Keiner der gewählten Shops führt diese ISBN.")
        else:
            self._setze_status(
                f"Fertig – {self._treffer} von {gesamt} Shops führen den Titel."
            )

    # -------------------------------------------------------------- Ergebnisse

    def _leere_ergebnisse(self) -> None:
        for kind in self.ergebnisse.winfo_children():
            kind.destroy()
        self._zeile = 0
        self._schreibe_kopfzeile()

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

    def _zeige_ergebnis(self, ergebnis) -> None:
        """Nimmt ein eingetroffenes Shop-Ergebnis auf und zeichnet neu."""
        if ergebnis.gefunden:
            self._treffer += 1
            # Das aktuelle Ergebnis gehört in den Verlauf, sonst würde das
            # Diagramm die gerade gespeicherte Abfrage erst beim nächsten
            # Start zeigen.
            self._verlaufsdaten.append(
                {
                    "shop": ergebnis.shop,
                    "preis": ergebnis.preis,
                    "datum": datetime.now(timezone.utc).isoformat(),
                }
            )

        self._zeilen.append(ergebnis)
        self._zeichne_tabelle()

    def _zeichne_tabelle(self) -> None:
        """Zeichnet alle bisher eingetroffenen Zeilen in sortierter Reihenfolge.

        Nach jedem Shop komplett neu statt nur anzuhängen: die Sortierung
        hängt an den Preisen, und der günstigste Shop kann erst als letzter
        antworten. Bei fünf Zeilen ist das Neuzeichnen nicht spürbar, und
        die Zeilen erscheinen weiterhin einzeln, sobald ein Shop geantwortet
        hat.
        """
        self._leere_ergebnisse()
        for zeile in sorted(self._zeilen, key=self._sortierschluessel):
            if isinstance(zeile, Fehlerzeile):
                self._zeichne_fehlerzeile(zeile)
            else:
                self._zeichne_ergebniszeile(zeile)

    @staticmethod
    def _sortierschluessel(zeile) -> tuple[int, float]:
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

    def _zeichne_ergebniszeile(self, ergebnis) -> None:
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
        vorher = self._vorherige_preise.get(ergebnis.shop)
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

    def _zeige_fehlerzeile(self, shop: str, fehler: str) -> None:
        self._zeilen.append(Fehlerzeile(shop=shop, text=fehler))
        self._zeichne_tabelle()

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

    def _merke_vorherige_preise(self, historie: list[dict]) -> None:
        """Letzter bekannter Preis je Shop – die Historie ist aufsteigend sortiert."""
        self._vorherige_preise = {eintrag["shop"]: eintrag for eintrag in historie}

    def _zeige_verlauf(self) -> None:
        if not self._verlaufsdaten:
            self._verstecke_verlauf()
            return

        self.verlauf_titel.grid(row=ZEILE_VERLAUF_TITEL, column=0, padx=20, pady=(4, 4), sticky="ew")
        self.verlauf.grid(row=ZEILE_VERLAUF, column=0, padx=20, pady=(0, 16), sticky="ew")
        # Immer alle Shops übergeben, nicht nur die angehakten: die Farbe hängt
        # am Shop, nicht daran, wer bei dieser Suche gefragt wurde – sonst
        # wechselt eine Linie die Farbe, sobald man einen Shop abwählt.
        self.verlauf.zeige(self._verlaufsdaten, shop_namen())

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
