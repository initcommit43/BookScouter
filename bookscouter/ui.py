"""customtkinter-Oberfläche für BookScouter.

Aufbau: Eingabefeld + Suchen-Button, darunter die Ergebnistabelle und ein
aufklappbarer Bereich mit früheren Abfragen.

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
import threading
from datetime import datetime

import customtkinter as ctk

from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.isbn import normalize_isbn
from bookscouter.scrapers import ALL_SCRAPERS

# Farben jeweils als (Hell-Modus, Dunkel-Modus).
FARBE_GUENSTIGER = ("#1a7f37", "#3fb950")
FARBE_TEURER = ("#cf222e", "#f85149")
FARBE_GEDAEMPFT = ("gray45", "gray60")

SPALTEN = ("Shop", "Titel", "Preis", "Vorher", "")

# So viele frühere Abfragen zeigt der aufgeklappte Bereich höchstens – mehr
# würde der Ergebnistabelle darüber zu viel Platz nehmen.
HISTORIE_MAX_ZEILEN = 6


def format_preis(wert: float) -> str:
    return f"{wert:.2f} €".replace(".", ",")


def format_datum(iso_datum: str) -> str:
    try:
        return datetime.fromisoformat(iso_datum).strftime("%d.%m.%Y")
    except ValueError:
        return iso_datum


class BookScouterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("BookScouter")
        self.geometry("860x680")
        self.minsize(700, 520)

        self._queue: queue.Queue | None = None
        self._laeuft = False
        self._vorherige_preise: dict[str, dict] = {}
        self._treffer = 0
        self._historie_offen = False
        self._historie_anzahl = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._baue_eingabe()
        self._baue_status()
        self._baue_ergebnisbereich()
        self._baue_historie()

        self.eingabe.focus()

    # ------------------------------------------------------------------ Aufbau

    def _baue_eingabe(self) -> None:
        rahmen = ctk.CTkFrame(self, fg_color="transparent")
        rahmen.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
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

    def _baue_status(self) -> None:
        rahmen = ctk.CTkFrame(self, fg_color="transparent")
        rahmen.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
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
        self.ergebnisse.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        # Titelspalte darf den übrigen Platz bekommen.
        self.ergebnisse.grid_columnconfigure(1, weight=1)
        self._zeile = 0

    def _baue_historie(self) -> None:
        self.historie_button = ctk.CTkButton(
            self, text="", anchor="w", height=32, fg_color="transparent",
            text_color=FARBE_GEDAEMPFT, hover=False, command=self._schalte_historie,
        )
        # Bewusst ein normaler CTkFrame statt CTkScrollableFrame: der wächst
        # exakt mit seinem Inhalt, statt eine feste Höhe zu belegen und bei
        # wenigen Einträgen halb leer zu wirken. Damit er nicht beliebig hoch
        # wird, zeigt _zeige_historie nur die letzten HISTORIE_MAX_ZEILEN.
        self.historie_rahmen = ctk.CTkFrame(self)
        self.historie_rahmen.grid_columnconfigure(2, weight=1)

    # ------------------------------------------------------------------- Suche

    def _starte_suche(self) -> None:
        if self._laeuft:
            return

        isbn = normalize_isbn(self.eingabe.get())
        if not isbn:
            self._setze_status("Bitte zuerst eine ISBN eingeben.")
            return

        self._laeuft = True
        self._treffer = 0
        self._vorherige_preise = {}
        self.such_button.configure(state="disabled", text="Sucht …")
        self.fortschritt.configure(mode="indeterminate")
        self.fortschritt.start()
        self._leere_ergebnisse()
        self._verstecke_historie()

        self._queue = queue.Queue()
        threading.Thread(
            target=self._arbeite, args=(isbn, self._queue), daemon=True
        ).start()
        self.after(100, self._pruefe_queue)

    @staticmethod
    def _arbeite(isbn: str, ausgabe: queue.Queue) -> None:
        """Läuft im Hintergrund-Thread: DB lesen, scrapen, DB schreiben."""
        try:
            conn = connect()
            try:
                historie = [dict(zeile) for zeile in get_price_history(conn, isbn)]
                ausgabe.put(("historie", historie))

                gesamt = len(ALL_SCRAPERS)
                for nummer, scraper_cls in enumerate(ALL_SCRAPERS, start=1):
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
            self._zeige_historie(nachricht[1])
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

        gesamt = len(ALL_SCRAPERS)
        if self._treffer == 0:
            self._setze_status("Kein Shop führt diese ISBN.")
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

    def _zeige_ergebnis(self, ergebnis) -> None:
        if not ergebnis.gefunden:
            self._zelle(0, ergebnis.shop, text_color=FARBE_GEDAEMPFT)
            ctk.CTkLabel(
                self.ergebnisse, text="— nicht geführt —", anchor="w",
                text_color=FARBE_GEDAEMPFT,
            ).grid(row=self._zeile, column=1, columnspan=4, padx=(0, 14), pady=3, sticky="w")
            self._zeile += 1
            return

        self._treffer += 1
        self._zelle(0, ergebnis.shop)
        self._zelle(1, ergebnis.titel)
        self._zelle(2, format_preis(ergebnis.preis),
                    font=ctk.CTkFont(size=13, weight="bold"))

        vorher = self._vorherige_preise.get(ergebnis.shop)
        if vorher is None:
            self._zelle(3, "(neu)", text_color=FARBE_GEDAEMPFT)
        else:
            self._zelle(3, format_preis(vorher["preis"]), text_color=FARBE_GEDAEMPFT)
            text, farbe = self._differenz(ergebnis.preis, vorher["preis"])
            self._zelle(4, text, text_color=farbe)

        self._zeile += 1

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
        self._zelle(0, shop, text_color=FARBE_GEDAEMPFT)
        ctk.CTkLabel(
            self.ergebnisse, text=f"Fehler: {fehler}", anchor="w", text_color=FARBE_TEURER,
        ).grid(row=self._zeile, column=1, columnspan=4, padx=(0, 14), pady=3, sticky="w")
        self._zeile += 1

    # --------------------------------------------------------------- Historie

    def _merke_vorherige_preise(self, historie: list[dict]) -> None:
        """Letzter bekannter Preis je Shop – die Historie ist aufsteigend sortiert."""
        self._vorherige_preise = {eintrag["shop"]: eintrag for eintrag in historie}

    def _zeige_historie(self, historie: list[dict]) -> None:
        for kind in self.historie_rahmen.winfo_children():
            kind.destroy()

        if not historie:
            self._verstecke_historie()
            return

        neueste_zuerst = list(reversed(historie))
        for zeile, eintrag in enumerate(neueste_zuerst[:HISTORIE_MAX_ZEILEN]):
            for spalte, text in enumerate(
                (
                    format_datum(eintrag["datum"]),
                    eintrag["shop"],
                    format_preis(eintrag["preis"]),
                )
            ):
                ctk.CTkLabel(
                    self.historie_rahmen, text=text, anchor="w",
                    text_color=FARBE_GEDAEMPFT,
                ).grid(row=zeile, column=spalte, padx=(14, 14), pady=2, sticky="w")

        weitere = len(historie) - HISTORIE_MAX_ZEILEN
        if weitere > 0:
            ctk.CTkLabel(
                self.historie_rahmen, text=f"… und {weitere} weitere", anchor="w",
                text_color=FARBE_GEDAEMPFT,
            ).grid(row=HISTORIE_MAX_ZEILEN, column=0, columnspan=3,
                   padx=(14, 14), pady=(2, 6), sticky="w")

        self._historie_anzahl = len(historie)
        self._historie_offen = False
        self._aktualisiere_historie_button()
        self.historie_button.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="ew")
        self.historie_rahmen.grid_remove()

    def _aktualisiere_historie_button(self) -> None:
        pfeil = "▾" if self._historie_offen else "▸"
        self.historie_button.configure(
            text=f"{pfeil} Frühere Abfragen ({self._historie_anzahl})"
        )

    def _schalte_historie(self) -> None:
        self._historie_offen = not self._historie_offen
        self._aktualisiere_historie_button()
        if self._historie_offen:
            # sticky="ew": nur horizontal dehnen, die Höhe bleibt bei 130px.
            self.historie_rahmen.grid(row=4, column=0, padx=20, pady=(0, 16), sticky="ew")
        else:
            self.historie_rahmen.grid_remove()

    def _verstecke_historie(self) -> None:
        self.historie_button.grid_remove()
        self.historie_rahmen.grid_remove()
        self._historie_offen = False

    # ----------------------------------------------------------------- Status

    def _setze_status(self, text: str) -> None:
        self.status_label.configure(text=text)


def main() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    BookScouterApp().mainloop()


if __name__ == "__main__":
    main()
