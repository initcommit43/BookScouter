# BookScouter – Projektplan

## Ziel des Projekts

Ein Desktop-Tool, mit dem man einen Buchtitel oder eine ISBN eingeben kann und
auf einen Blick die Preise bei mehreren vorher ausgewählten Online-Shops
sieht.

**Wichtig für die gesamte Umsetzung:** Dieses Projekt dient primär dazu, zu
zeigen, dass ein reales Problem erkannt und gelöst werden kann – nicht dazu,
möglichst viele Technologien oder Engineering-Komplexität zur Schau zu
stellen. Bei jeder Implementierungsentscheidung gilt: die einfachste,
robusteste Lösung gewinnt, nicht die "modernste" oder komplexeste. Das Projekt
wird mit KI-Unterstützung gebaut, daher sollten Patterns verwendet werden, die
gut etabliert und gut dokumentiert sind, statt exotische oder brandneue
Libraries.

## Zielgruppe

1. Privatgebrauch (Captain selbst)
2. GitHub-Portfolio-Projekt für Bewerbungen als Junior Dev (Frontend/Fullstack)

## Nutzungskontext & rechtliche Leitplanken

- Das Tool läuft **ausschließlich lokal auf der Maschine des jeweiligen
  Nutzers**. Es gibt keinen zentralen Server, kein Hosting, keine zentrale
  Datenbank, die von Captain betrieben wird.
- Abfragen erfolgen **gezielt pro ISBN/Titel auf Anfrage** – kein
  systematisches Massen-Crawling ganzer Kataloge.
- Rate-Limiting/Delays zwischen Requests einbauen, auch wenn's "nur" lokal
  läuft, damit ein einzelner Nutzer nicht versehentlich wie ein Bot-Angriff
  wirkt.
- Ehrlicher User-Agent (kein Vortäuschen eines echten Browsers).
- Keine gesammelten Scraping-Daten im Repository committen (kein `prices.json`
  mit tausenden vorab gescrapten Titeln) – nur der Code, keine
  Fremd-Datenbestände.
- robots.txt der Zielshops nach Möglichkeit respektieren.

## Tech-Stack (final, keine Alternativen mehr offen)

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | Python | Einzige Sprache im gesamten Projekt, kein Sprach-Mix |
| Scraping | `requests` + `BeautifulSoup` | Standard, gut dokumentiert, KI-freundlich |
| Speicherung | `sqlite3` (Standardbibliothek) | Keine Installation nötig, eine einzelne Datei |
| UI | `customtkinter` | Moderneres Look & Feel als klassisches Tkinter, bleibt aber reines Python, kein Server/Browser nötig |
| Verteilung | `PyInstaller` | Eine einzelne `.exe` mit eigenem Icon, Doppelklick startet die App direkt – kein Terminal, keine URL, kein Setup |

Explizit **nicht** verwendet: FastAPI/Flask-Server, Electron, React/TypeScript,
Streamlit, pywebview – diese wurden im Planungsprozess erwogen und bewusst
verworfen, weil sie unnötige Komplexität für den Zweck des Projekts bedeutet
hätten.

## Kernfunktionen (MVP)

1. Eingabefeld für ISBN oder Buchtitel
2. Auswahl/Konfiguration, welche Shops abgefragt werden sollen (ein Shop als
   Startpunkt, weitere später ergänzbar)
3. Anzeige der gefundenen Preise pro Shop auf einen Blick (Tabelle im Fenster)
4. Jede Abfrage wird lokal in SQLite gespeichert (ISBN, Titel, Shop, Preis,
   Datum)
5. Bei erneuter Suche nach demselben Titel: Anzeige des Preisverlaufs im
   Vergleich zu früheren Abfragen (z. B. "vor 1 Monat: 12,99 € → heute:
   14,49 €")

## Phasenplan

### Phase 1 – Kernlogik (Command-Line/Script-Ebene, ohne UI)
- Projektstruktur aufsetzen
- SQLite-Schema definieren und Anbindung schreiben (Tabelle für
  Preis-Abfragen: id, isbn, titel, shop, preis, datum)
- Scraping-Funktion für den ersten Shop bauen: Eingabe ISBN → Ausgabe Titel + Preis
- Rate-Limiting/Delay-Logik einbauen
- Testen mit ein paar echten ISBNs, bis die Kernlogik zuverlässig funktioniert

### Phase 2 – Mehrere Shops
- Scraping-Logik so strukturieren, dass weitere Shops einfach als zusätzliche
  Module/Funktionen ergänzt werden können (gemeinsames Interface: ISBN rein,
  Titel+Preis raus)
- Zweiten und dritten Shop ergänzen
- Fehlerbehandlung: Was passiert, wenn ein Shop das Buch nicht führt oder die
  Seite nicht erreichbar ist?

### Phase 3 – UI mit customtkinter
- Hauptfenster mit Eingabefeld, "Suchen"-Button, Ergebnistabelle
- Anbindung der Scraping- und SQLite-Funktionen an die UI (Klick auf Suchen
  löst Abfrage aus, Ergebnis erscheint in der Tabelle)
- Anzeige des Preisverlaufs, falls der Titel schon einmal gesucht wurde
- Ladeanzeige/Feedback während der Scraping-Anfragen laufen (UI darf nicht
  einfrieren – ggf. Threading verwenden)

### Phase 4 – Packaging & Politur
- Icon für die App erstellen/auswählen
- PyInstaller-Konfiguration (Onefile-Build, Icon einbinden)
- Testen des gebauten Binaries auf einer "sauberen" Maschine (ohne installiertes Python)
- README schreiben: kurze Problem-Beschreibung, Screenshot/GIF der App,
  Hinweis auf lokale Ausführung und Eigenverantwortung bzgl. AGB der
  jeweiligen Shops

### Phase 5 (optional, falls Zeit/Lust vorhanden)
- Weitere Shops ergänzen
- Einfache Preisverlauf-Visualisierung (Chart statt nur Tabelle)
- Export der eigenen Preishistorie als CSV

## Repo-Name
BookScouter (falls auf GitHub verfügbar, sonst naheliegende Variante)
