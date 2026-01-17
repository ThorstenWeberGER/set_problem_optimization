# Containts bugs to solve

**open**
- map plz 
    - plz5 cells show very low customers per plz
    - sum plz5 cells for a location "seems" not to come to total shown in popup of location
- no bug but: understand the impfact of different constraints

**solved
- locations stats between results on map and exported CSV are consistent, BUT: sum of total customers AND total weighted customers 
    - does not match to legend sums
    - does not sum up to 90k total and 81k goal
- customers.csv
    - redundancy? yes, party. but data is deduplicated before it hits the solver
    - no solution implemented because only test data.

# Insight

- the data which is saved in the csv file shows up in map location pop ups (THIS MATCHES)

- the data which is saved in csv file (does not sum up correctly)
    - example: 1000 customers generated
    - list cities coverage of 1039!!! -> doppelzählungen ??? -> wir haben "überschneidungen"

      HYPOTHESE: es liegt an doppelzählungen durch Überschneidungen. 
      RESULTAT: Ja, Doppelzählungen.
      SOLUTION: Function actualizes locations_stats by deduplication.
      RESULT: csv export sum customers = stats in visualized map (totals) and also stats in maps (locations totals)

# Unit Tests

- sollen die funktionen (input > funktion > output) testen
- nicht einfach einzelne bestandteile einer funktion 
- evtl. größere funktionen in kleinere helper funktionen zerlegen und diese testen

# Ideas for picking the right cities

- running couple of different constraint sets
- identify cities which are always showing up (minimum)
- rest discuss advantages, adjust constraint sets
