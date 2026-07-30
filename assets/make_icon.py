"""Erzeugt `BookScouter.ico` – das Icon der .exe und des Fensters.

Aufruf (aus dem Projektordner):

    python assets/make_icon.py

Absichtlich ohne Bildbibliothek: Pillow nur fürs einmalige Zeichnen eines
Icons als Abhängigkeit aufzunehmen wäre unverhältnismässig, und so ist das
Icon reproduzierbar statt eine Binärdatei unbekannter Herkunft im Repo.

Motiv: ein aufgeschlagenes Buch in Weiss auf dem Blau des CTk-Themes, damit
Fenster, Taskleiste und .exe zum Look der App passen.
"""

import struct
import zlib
from pathlib import Path

ZIEL = Path(__file__).resolve().parent / "BookScouter.ico"

# Grössen bis 48 px als BMP (klassisches ICO-Format), grössere als PNG –
# genauso machen es gängige Icon-Werkzeuge. Ein 256er als BMP wären allein
# 256 KB, als PNG sind es wenige Kilobyte.
GROESSEN_BMP = (16, 24, 32, 48)
GROESSEN_PNG = (64, 128, 256)

# Farbverlauf des Hintergrunds, oben nach unten (CTk-Blau).
BLAU_OBEN = (59, 142, 208)
BLAU_UNTEN = (31, 106, 165)
WEISS = (255, 255, 255)

ECKENRADIUS = 0.22
# Kantenglättung: pro Bildpunkt SS×SS Proben.
SS = 4

# Aufgeschlagenes Buch, Koordinaten von 0 bis 1, y nach unten: die Seiten
# stossen in der Mitte oben zusammen und fallen nach aussen ab, der untere
# Rand liegt flach auf. Zwei gleich hohe Trapeze sahen dagegen aus wie ein
# Fenster, nicht wie ein Buch.
SEITE_LINKS = ((0.13, 0.39), (0.50, 0.31), (0.50, 0.71), (0.13, 0.71))
SEITE_RECHTS = ((0.87, 0.39), (0.50, 0.31), (0.50, 0.71), (0.87, 0.71))
# Schmaler Spalt in der Mitte, damit man zwei Seiten erkennt.
BUND_HALBBREITE = 0.018


def _im_viereck(x: float, y: float, ecken) -> bool:
    """Punkt-in-konvexem-Viereck über das Vorzeichen der Kreuzprodukte."""
    vorzeichen = None
    for i in range(4):
        ax, ay = ecken[i]
        bx, by = ecken[(i + 1) % 4]
        kreuz = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if kreuz == 0:
            continue
        if vorzeichen is None:
            vorzeichen = kreuz > 0
        elif (kreuz > 0) != vorzeichen:
            return False
    return True


def _im_abgerundeten_rechteck(x: float, y: float, radius: float) -> bool:
    naechstes_x = min(max(x, radius), 1 - radius)
    naechstes_y = min(max(y, radius), 1 - radius)
    dx, dy = x - naechstes_x, y - naechstes_y
    return dx * dx + dy * dy <= radius * radius


def _probe(x: float, y: float) -> tuple[int, int, int, int]:
    """Farbe und Deckkraft an einer Stelle des Icons."""
    if not _im_abgerundeten_rechteck(x, y, ECKENRADIUS):
        return (0, 0, 0, 0)

    ist_buch = (
        _im_viereck(x, y, SEITE_LINKS) or _im_viereck(x, y, SEITE_RECHTS)
    ) and abs(x - 0.5) > BUND_HALBBREITE
    if ist_buch:
        return (*WEISS, 255)

    r = round(BLAU_OBEN[0] + (BLAU_UNTEN[0] - BLAU_OBEN[0]) * y)
    g = round(BLAU_OBEN[1] + (BLAU_UNTEN[1] - BLAU_OBEN[1]) * y)
    b = round(BLAU_OBEN[2] + (BLAU_UNTEN[2] - BLAU_OBEN[2]) * y)
    return (r, g, b, 255)


def zeichne(groesse: int) -> list[list[tuple[int, int, int, int]]]:
    """Icon in der gewünschten Kantenlänge, Zeilen von oben nach unten."""
    zeilen = []
    for py in range(groesse):
        zeile = []
        for px in range(groesse):
            summe = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    x = (px + (sx + 0.5) / SS) / groesse
                    y = (py + (sy + 0.5) / SS) / groesse
                    farbe = _probe(x, y)
                    # Vor dem Mitteln mit Alpha gewichten, sonst franst der
                    # Rand grau aus statt sauber transparent zu werden.
                    a = farbe[3] / 255
                    summe[0] += farbe[0] * a
                    summe[1] += farbe[1] * a
                    summe[2] += farbe[2] * a
                    summe[3] += farbe[3]
            anzahl = SS * SS
            alpha = summe[3] / anzahl
            if alpha == 0:
                zeile.append((0, 0, 0, 0))
                continue
            gewicht = summe[3] / 255
            zeile.append(
                (
                    round(summe[0] / gewicht),
                    round(summe[1] / gewicht),
                    round(summe[2] / gewicht),
                    round(alpha),
                )
            )
        zeilen.append(zeile)
    return zeilen


def als_bmp(zeilen) -> bytes:
    """Bilddaten im ICO-BMP-Format (32 Bit, von unten nach oben)."""
    groesse = len(zeilen)
    farben = bytearray()
    for zeile in reversed(zeilen):
        for r, g, b, a in zeile:
            farben += bytes((b, g, r, a))

    # Die AND-Maske ist bei 32 Bit unbenutzt, muss aber vorhanden sein.
    maskenbreite = ((groesse + 31) // 32) * 4
    maske = bytes(maskenbreite * groesse)

    kopf = struct.pack(
        "<IiiHHIIiiII",
        40,               # Grösse des Headers
        groesse,
        groesse * 2,      # Höhe zählt Bild + Maske
        1,                # Ebenen
        32,               # Bits pro Punkt
        0,                # unkomprimiert
        len(farben) + len(maske),
        0, 0, 0, 0,
    )
    return kopf + bytes(farben) + maske


def als_png(zeilen) -> bytes:
    hoehe = len(zeilen)
    breite = len(zeilen[0])
    roh = bytearray()
    for zeile in zeilen:
        roh.append(0)  # Filtertyp "keiner"
        for farbe in zeile:
            roh += bytes(farbe)

    def block(art: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + art
            + daten
            + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", breite, hoehe, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + block(b"IHDR", ihdr)
        + block(b"IDAT", zlib.compress(bytes(roh), 9))
        + block(b"IEND", b"")
    )


def baue_ico() -> bytes:
    bilder = []
    for groesse in GROESSEN_BMP:
        bilder.append((groesse, als_bmp(zeichne(groesse))))
    for groesse in GROESSEN_PNG:
        bilder.append((groesse, als_png(zeichne(groesse))))

    kopf = struct.pack("<HHH", 0, 1, len(bilder))
    versatz = len(kopf) + 16 * len(bilder)
    verzeichnis = bytearray()
    for groesse, daten in bilder:
        verzeichnis += struct.pack(
            "<BBBBHHII",
            groesse if groesse < 256 else 0,  # 256 wird als 0 geschrieben
            groesse if groesse < 256 else 0,
            0,  # Farbtabelle: keine
            0,  # reserviert
            1,  # Ebenen
            32,  # Bits pro Punkt
            len(daten),
            versatz,
        )
        versatz += len(daten)

    return kopf + bytes(verzeichnis) + b"".join(daten for _, daten in bilder)


if __name__ == "__main__":
    ZIEL.write_bytes(baue_ico())
    print(f"{ZIEL} geschrieben ({ZIEL.stat().st_size / 1024:.1f} KB)")
