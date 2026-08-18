"""Preisverlauf als Liniendiagramm.

Gezeichnet wird direkt auf einem `tkinter.Canvas` – bewusst ohne matplotlib:
das Diagramm besteht aus Linien, Punkten und Text, dafür lohnt keine
Abhängigkeit, die den späteren PyInstaller-Build um ein Vielfaches aufbläht.

Eine Linie je Shop, x-Achse sind Tage, y-Achse ist der Preis. Mehrere
Abfragen desselben Shops am selben Tag werden zum letzten Preis dieses Tages
zusammengefasst: Buchpreise ändern sich nicht im Minutentakt, und ohne diese
Zusammenfassung würden die Sekundenabstände einer einzelnen Suche die
x-Achse dominieren.
"""

import math
import tkinter as tk
from datetime import date, datetime

import customtkinter as ctk

# Kategoriale Palette, Slots 1–8, jeweils (hell, dunkel).
#
# Die Reihenfolge ist die Absicherung gegen Farbfehlsichtigkeit, nicht
# Kosmetik – geprüft mit dem Validator der dataviz-Vorgaben (schlechtestes
# benachbartes Paar ΔE 9.1 hell / 8.4 dunkel bei Zielwert 8, alle 8 Slots;
# hell zusätzlich mit Kontrastwarnung für aqua/gelb/magenta, siehe unten).
# Wer hier umsortiert oder Farben austauscht, muss neu prüfen. Alle acht sind
# die festen Slots der Referenzpalette, keine neu erfundenen Werte.
#
# Die Kontrastwarnung im hellen Modus ist gedeckt: die Legende nennt zu jeder
# Linie den Shop-Namen und den letzten Preis im Klartext, die Farbe ist also
# nie der einzige Träger der Information.
SERIENFARBEN = [
    ("#2a78d6", "#3987e5"),  # blau
    ("#eb6834", "#d95926"),  # orange
    ("#1baf7a", "#199e70"),  # aqua
    ("#eda100", "#c98500"),  # gelb
    ("#e87ba4", "#d55181"),  # magenta
    ("#008300", "#008300"),  # grün
    ("#4a3aa7", "#9085e9"),  # violett
    ("#e34948", "#e66767"),  # rot
]

# Mehr Shops als Farbslots: die Referenzpalette hat acht Slots und darf nicht
# um selbst erfundene Farbtöne verlängert werden. Ab Slot 9 wiederholen sich
# deshalb die Farben, und die Wiederholung wird über die Strichart
# unterschieden – dieselbe Farbe einmal durchgezogen, einmal gestrichelt.
# So bleibt jede Serie eindeutig, ohne die geprüften Farbabstände aufzugeben.
STRICH_DURCHGEZOGEN: tuple[int, ...] = ()
STRICH_GESTRICHELT = (6, 4)


def serienstil(nummer: int) -> tuple[tuple[str, str], tuple[int, ...]]:
    """Farbpaar und Strichart der n-ten Serie."""
    return (
        SERIENFARBEN[nummer % len(SERIENFARBEN)],
        STRICH_DURCHGEZOGEN if nummer < len(SERIENFARBEN) else STRICH_GESTRICHELT,
    )

FLAECHE = ("#fcfcfb", "#1a1a19")
GITTER = ("#e1e0d9", "#2c2c2a")
ACHSE = ("#c3c2b7", "#383835")
INK_PRIMAER = ("#0b0b0b", "#ffffff")
INK_SEKUNDAER = ("#52514e", "#c3c2b7")
INK_GEDAEMPFT = ("#898781", "#898781")


def farbe(paar: tuple[str, str]) -> str:
    """Wählt aus einem (hell, dunkel)-Paar den Wert des aktuellen Modus."""
    return paar[0] if ctk.get_appearance_mode() == "Light" else paar[1]


def format_preis(wert: float) -> str:
    return f"{wert:.2f} €".replace(".", ",")


def aggregiere_nach_tag(punkte: list[dict]) -> dict[str, list[tuple[date, float]]]:
    """Fasst die Abfragen je Shop auf einen Preis pro Tag zusammen.

    Maßgeblich ist die letzte Abfrage des Tages. Rückgabe ist je Shop nach
    Datum aufsteigend sortiert.
    """
    je_shop: dict[str, dict[date, tuple[datetime, float]]] = {}

    for punkt in punkte:
        try:
            zeitpunkt = datetime.fromisoformat(punkt["datum"])
        except (TypeError, ValueError):
            continue

        tag = zeitpunkt.date()
        tage = je_shop.setdefault(punkt["shop"], {})
        bisher = tage.get(tag)
        if bisher is None or zeitpunkt >= bisher[0]:
            tage[tag] = (zeitpunkt, float(punkt["preis"]))

    return {
        shop: [(tag, preis) for tag, (_, preis) in sorted(tage.items())]
        for shop, tage in je_shop.items()
    }


# Schrittweiten, die als Achsenbeschriftung nicht krumm aussehen.
NETTE_SCHRITTE = (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0)


def berechne_y_achse(preise: list[float]) -> tuple[float, float, float]:
    """Unterer Rand, oberer Rand und Schrittweite der Preisachse.

    Die Ränder werden auf ein Vielfaches der Schrittweite gerundet, damit an
    der Achse "25,00 €" steht und nicht "24,71 €". Vor dem Runden kommt etwas
    Luft dazu, sonst läge eine Linie beim glatten Preis genau auf dem Rahmen.

    Bei durchgehend gleichem Preis (waagerechte Linie) wird künstlich ein
    Bereich aufgespannt.
    """
    kleinster, groesster = min(preise), max(preise)
    if groesster - kleinster < 0.01:
        kleinster, groesster = kleinster - 1.0, groesster + 1.0

    luft = (groesster - kleinster) * 0.15
    roh = (groesster - kleinster) / 2.5
    schritt = next((wert for wert in NETTE_SCHRITTE if wert >= roh), NETTE_SCHRITTE[-1])

    unten = math.floor((kleinster - luft) / schritt) * schritt
    oben = math.ceil((groesster + luft) / schritt) * schritt
    return unten, oben, schritt


class PreisverlaufChart(ctk.CTkFrame):
    """Liniendiagramm der bisherigen Preise, mit Preis-Einblendung beim Hovern."""

    PLOT_HOEHE = 200
    RAND_LINKS = 62
    RAND_RECHTS = 18
    RAND_OBEN = 16
    RAND_UNTEN = 28

    MARKER = 4

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._serien: dict[str, list[tuple[date, float]]] = {}
        self._farben: dict[str, tuple[str, str]] = {}
        self._striche: dict[str, tuple[int, ...]] = {}
        # Beim Zeichnen gefüllt, Grundlage für das Hovern: x-Position je Tag
        # und die Werte, die an diesem Tag auf dem Diagramm liegen.
        self._spalten: list[tuple[float, date]] = []
        self._werte_je_tag: dict[date, list[tuple[str, float, float]]] = {}
        self._plot: tuple[float, float, float, float] | None = None

        self.canvas = tk.Canvas(self, height=self.PLOT_HOEHE, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))
        self.canvas.bind("<Configure>", lambda _event: self._zeichne())
        self.canvas.bind("<Motion>", self._bei_bewegung)
        self.canvas.bind("<Leave>", lambda _event: self._loesche_tooltip())

        self.hinweis = ctk.CTkLabel(self, text="", text_color=INK_GEDAEMPFT, anchor="w")

        self.legende = ctk.CTkFrame(self, fg_color="transparent")
        self.legende.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 10))

    # ------------------------------------------------------------------- Daten

    def zeige(self, punkte: list[dict], shop_reihenfolge: list[str]) -> None:
        """Übernimmt die Historie und zeichnet neu.

        `shop_reihenfolge` legt die Farbzuordnung fest. Sie hängt bewusst
        nicht davon ab, welche Shops gerade Daten geliefert haben – sonst
        würde ein Shop, der einmal nichts führt, die Farben aller anderen
        verschieben.
        """
        self._serien = aggregiere_nach_tag(punkte)
        self._farben = {}
        self._striche = {}
        for nummer, shop in enumerate(shop_reihenfolge):
            self._farben[shop], self._striche[shop] = serienstil(nummer)
        self._baue_legende()
        self._zeichne()

    def _tage(self) -> list[date]:
        return sorted({tag for reihe in self._serien.values() for tag, _ in reihe})

    def _baue_legende(self) -> None:
        for kind in self.legende.winfo_children():
            kind.destroy()

        # Die Legende ist zugleich die Werteanzeige: der jeweils letzte Preis
        # steht als Text da und ist damit auch ohne Hovern lesbar.
        for nummer, shop in enumerate(sorted(self._serien)):
            spalte = (nummer % 3) * 3
            zeile = nummer // 3

            # Das Legendensymbol zeigt auch die Strichart: bei mehr Shops als
            # Farbslots teilen sich zwei Linien einen Farbton, und dann muss
            # die Legende denselben Unterschied zeigen wie das Diagramm.
            ctk.CTkLabel(
                self.legende,
                text="╌╌" if self._striche.get(shop) else "──",
                text_color=farbe(self._farben.get(shop, SERIENFARBEN[0])),
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=zeile, column=spalte, padx=(0, 5), pady=1, sticky="w")
            ctk.CTkLabel(
                self.legende, text=shop, text_color=INK_SEKUNDAER, anchor="w",
            ).grid(row=zeile, column=spalte + 1, padx=(0, 6), pady=1, sticky="w")
            ctk.CTkLabel(
                self.legende, text=format_preis(self._serien[shop][-1][1]),
                text_color=INK_PRIMAER, font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            ).grid(row=zeile, column=spalte + 2, padx=(0, 18), pady=1, sticky="w")

    # ---------------------------------------------------------------- Zeichnen

    def _zeichne(self) -> None:
        self.canvas.delete("all")
        self._spalten = []
        self._werte_je_tag = {}
        self._plot = None
        self.canvas.configure(bg=farbe(FLAECHE))

        tage = self._tage()
        if not tage:
            self.canvas.grid_remove()
            self.hinweis.grid_remove()
            return

        # Ein einzelner Tag ergibt keinen Verlauf – dann lieber ein ehrlicher
        # Hinweis als ein Diagramm mit einer Punktespalte.
        if len(tage) < 2:
            self.canvas.grid_remove()
            self.hinweis.configure(
                text="Erst eine Abfrage – der Verlauf wird ab der nächsten sichtbar."
            )
            self.hinweis.grid(row=1, column=0, sticky="ew", padx=14, pady=(10, 0))
            return

        self.hinweis.grid_remove()
        self.canvas.grid()

        breite = self.canvas.winfo_width()
        hoehe = self.canvas.winfo_height()
        if breite <= 1:  # noch nicht gelayoutet, <Configure> zeichnet gleich erneut
            return

        links, rechts = self.RAND_LINKS, breite - self.RAND_RECHTS
        oben, unten = self.RAND_OBEN, hoehe - self.RAND_UNTEN
        if rechts <= links or unten <= oben:
            return

        alle_preise = [preis for reihe in self._serien.values() for _, preis in reihe]
        y_min, y_max, schritt = berechne_y_achse(alle_preise)
        erster, letzter = tage[0], tage[-1]
        spanne = (letzter - erster).days or 1

        def x_von(tag: date) -> float:
            return links + (tag - erster).days / spanne * (rechts - links)

        def y_von(preis: float) -> float:
            return unten - (preis - y_min) / (y_max - y_min) * (unten - oben)

        self._plot = (links, rechts, oben, unten)
        self._spalten = [(x_von(tag), tag) for tag in tage]

        self._zeichne_achsen(links, rechts, unten, y_min, y_max, schritt, erster, letzter,
                             x_von, y_von)
        self._zeichne_serien(x_von, y_von)

    def _zeichne_achsen(
        self, links, rechts, unten, y_min, y_max, schritt, erster, letzter, x_von, y_von
    ) -> None:
        gitter, achse, gedaempft = farbe(GITTER), farbe(ACHSE), farbe(INK_GEDAEMPFT)

        # Waagerechte Hilfslinien mit Preisbeschriftung – durchgezogene
        # Haarlinien, keine gestrichelten (die lesen sich als Schwellwert).
        anzahl = round((y_max - y_min) / schritt)
        for stufe in range(anzahl + 1):
            preis = y_min + stufe * schritt
            y = y_von(preis)
            self.canvas.create_line(links, y, rechts, y, fill=gitter, width=1)
            self.canvas.create_text(
                links - 8, y, text=format_preis(preis), anchor="e",
                fill=gedaempft, font=("Segoe UI", 8),
            )

        self.canvas.create_line(links, unten, rechts, unten, fill=achse, width=1)

        for tag, anker in ((erster, "w"), (letzter, "e")):
            self.canvas.create_text(
                x_von(tag), unten + 14, text=tag.strftime("%d.%m.%Y"), anchor=anker,
                fill=gedaempft, font=("Segoe UI", 8),
            )

    def _zeichne_serien(self, x_von, y_von) -> None:
        flaeche = farbe(FLAECHE)

        for shop in sorted(self._serien):
            reihe = self._serien[shop]
            linienfarbe = farbe(self._farben.get(shop, SERIENFARBEN[0]))
            koordinaten = [(x_von(tag), y_von(preis)) for tag, preis in reihe]

            if len(koordinaten) > 1:
                self.canvas.create_line(
                    [wert for punkt in koordinaten for wert in punkt],
                    fill=linienfarbe, width=2, smooth=False,
                    dash=self._striche.get(shop, STRICH_DURCHGEZOGEN),
                )

            for (x, y), (tag, preis) in zip(koordinaten, reihe):
                # 2px-Ring in Flächenfarbe, damit sich überlappende Punkte
                # zweier Shops nicht zu einem Klumpen verschmelzen.
                self.canvas.create_oval(
                    x - self.MARKER, y - self.MARKER, x + self.MARKER, y + self.MARKER,
                    fill=linienfarbe, outline=flaeche, width=2,
                )
                self._werte_je_tag.setdefault(tag, []).append((shop, preis, y))

    # ----------------------------------------------------------------- Hovern

    def _bei_bewegung(self, event) -> None:
        """Zeigt die Preise des Tages, auf den der Zeiger am ehesten deutet.

        Bewusst pro Tag statt pro Punkt: Shops derselben Plattform haben oft
        exakt denselben Preis, ihre Linien liegen dann übereinander und ein
        einzelner Punkt wäre gar nicht gezielt treffbar. So genügt es, in die
        Nähe eines Tages zu zeigen, und man bekommt alle Shops auf einmal.
        """
        if self._plot is None or not self._spalten:
            return

        links, rechts, oben, unten = self._plot
        if not (links - 10 <= event.x <= rechts + 10 and oben - 10 <= event.y <= unten + 10):
            self._loesche_tooltip()
            return

        x, tag = min(self._spalten, key=lambda spalte: abs(spalte[0] - event.x))
        self._zeige_tooltip(x, tag)

    def _loesche_tooltip(self) -> None:
        self.canvas.delete("tooltip")

    def _zeige_tooltip(self, x: float, tag: date) -> None:
        self._loesche_tooltip()
        eintraege = sorted(self._werte_je_tag.get(tag, []))
        if not eintraege:
            return

        links, rechts, oben, unten = self._plot

        # Senkrechte Fanglinie: der Zeiger muss den Tag treffen, nicht die Linie.
        self.canvas.create_line(x, oben, x, unten, fill=farbe(ACHSE), width=1, tags="tooltip")

        for shop, _preis, y in eintraege:
            self.canvas.create_oval(
                x - self.MARKER - 3, y - self.MARKER - 3,
                x + self.MARKER + 3, y + self.MARKER + 3,
                outline=farbe(self._farben.get(shop, SERIENFARBEN[0])), width=2, tags="tooltip",
            )

        kopf = tag.strftime("%d.%m.%Y")
        zeilen = [(shop, format_preis(preis)) for shop, preis, _ in eintraege]
        breite = max(
            [len(kopf) * 7]
            + [22 + len(shop) * 6 + len(preis) * 7 for shop, preis in zeilen]
        ) + 20
        hoehe = 22 + len(zeilen) * 16 + 8

        kasten_x = x + 14
        if kasten_x + breite > rechts + self.RAND_RECHTS:
            kasten_x = x - 14 - breite
        kasten_y = min(max(oben, 4), self.canvas.winfo_height() - hoehe - 4)

        self.canvas.create_rectangle(
            kasten_x, kasten_y, kasten_x + breite, kasten_y + hoehe,
            fill=farbe(FLAECHE), outline=farbe(ACHSE), width=1, tags="tooltip",
        )
        self.canvas.create_text(
            kasten_x + 10, kasten_y + 12, text=kopf, anchor="w",
            fill=farbe(INK_GEDAEMPFT), font=("Segoe UI", 8), tags="tooltip",
        )

        for nummer, (shop, preis_text) in enumerate(zeilen):
            y_zeile = kasten_y + 28 + nummer * 16
            # Kurzer Strich in der Serienfarbe als Schlüssel; der Text selbst
            # bleibt in Textfarbe, damit er lesbar ist.
            self.canvas.create_line(
                kasten_x + 10, y_zeile, kasten_x + 24, y_zeile,
                fill=farbe(self._farben.get(shop, SERIENFARBEN[0])), width=2, tags="tooltip",
            )
            self.canvas.create_text(
                kasten_x + 30, y_zeile, text=shop, anchor="w",
                fill=farbe(INK_SEKUNDAER), font=("Segoe UI", 8), tags="tooltip",
            )
            self.canvas.create_text(
                kasten_x + breite - 10, y_zeile, text=preis_text, anchor="e",
                fill=farbe(INK_PRIMAER), font=("Segoe UI", 9, "bold"), tags="tooltip",
            )
