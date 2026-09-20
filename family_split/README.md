# Familienkasse

Eine geteilte Ausgaben-App für die Familie, gebaut als Claude-Artifact mit gemeinsamer
Datenbank. Alle öffnen denselben Link (Handy oder Desktop), niemand braucht ein Konto.

## Warum nicht einfach Splitwise?

| | Splitwise (frei) | Familienkasse |
|---|---|---|
| Konten nötig | ja, pro Person | nein, ein Link für alle |
| Positionen einer Rechnung einzeln zuordnen | nur Pro | ja, mit anteiliger Steuer / Trinkgeld |
| Fremdwährung (z. B. GEL) mit Kurs pro Ausgabe | eingeschränkt | ja, Kurs wird beim Anlegen eingefroren |
| Kassenbon per Foto einlesen | Pro | ja, Claude liest Positionen aus |
| Ausgleich mit minimaler Zahl an Überweisungen | Heuristik | exakt (Subset-DP), Erklärung in der App |
| Werbung / Limits pro Tag | ja | nein |

## Dateien

- `index.html` – die komplette App (eine Datei, kein Build). Wird als Artifact veröffentlicht.
  Ohne Claude-Umgebung läuft sie lokal im Browser mit `localStorage`.
- `settle.py` – der Ausgleichs-Solver in Python: exakte Variante per DP über Teilmengen
  (Abschnitt 3 des Kurses) und als ganzzahliges Programm mit PuLP (Abschnitt 4).
  `python settle.py` rechnet die Rigi-Rechnung durch und zeigt einen Fall, in dem Greedy verliert.
- `test_settle.py` – Eigenschaftstests: DP ist gültig und optimal (gegen Brute Force), nie schlechter als Greedy.

## Datenmodell (Artifact-DB)

```
group/main            { name, base: "EUR", members: [{id, name, color}], rates: {GEL: 0.34, ...} }
expenses/<id>         { title, amount, currency, rate, date, paidBy, split, note, kind?, to? }
data/users/<uid>/profile  { memberId }        # privat: "Das bin ich"
```

`split.mode` ist `equal` (mit optionalem `among`), `shares`, `exact` oder `items`
(`items: [{name, price, for: [memberId]}]`, leeres `for` = alle). Ein Eintrag mit
`kind: "settlement"` ist eine Überweisung von `paidBy` an `to`.

## Rechenregeln

- Alles in Cent. Restcent nach dem größten Rest, damit Summen exakt aufgehen.
- Positionen: Differenz zwischen Rechnungsbetrag und Positionssumme (Steuer, Trinkgeld,
  Rundung) wird proportional zu den Positionsanteilen der Personen verteilt.
- Ausgleich: minimale Überweisungen = n − (maximale Zahl disjunkter Gruppen mit Saldo 0).
  Exakt per DP über Teilmengen bis 14 Personen, innerhalb jeder Gruppe Greedy (k − 1 Überweisungen).

## Ideen für die nächste Runde

- Wiederkehrende Ausgaben (Miete, Streaming) mit Monatsrhythmus.
- Export als CSV über die `downloads`-Fähigkeit.
- Kategorien und Monatsübersicht pro Person.
- Push-Erinnerung, wenn jemand länger als 30 Tage im Minus ist.
