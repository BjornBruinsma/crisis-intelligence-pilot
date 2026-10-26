# CRISIS Intelligence — GDELT pilot 0.2

Publieke researchpilot rond Iran, regionale escalatie en de wereldeconomie.

## Wat doet dit project?
- GitHub Actions verzamelt elke zes uur nieuwe GDELT DOC 2.0 artikelverwijzingen in acht thematische categorieën.
- Het dashboard toont per nieuwsartikel titel, eerste waarneming, brondomein, land en categorie.
- Berichten zijn *ongeverifieerd*. De risicometers blijven op "geen beoordeling" totdat we een onafhankelijke broncontrole en scoremethodiek hebben.
- Doublures worden voorlopig alleen op URL samengevoegd. Semantische clustering ontbreekt.
- De dataset is openbaar; geen vertrouwelijke info of secrets aan toevoegen.

## Live zetten
1. GitHub → Settings → Pages → Build and deployment → **GitHub Actions**.
2. GitHub → Actions → **CRISIS GDELT pilot** → **Run workflow**.
3. Controleer of de workflow succesvol draait en of `site/data/fetch_status.json` is geactualiseerd.
4. De Pages URL staat bij Settings → Pages. Vaak: https://bjornbruinsma.github.io/crisis-intelligence-pilot/

GitHub kan geplande runs vertragen. De openbare GDELT API kan tijdelijk onbereikbaar zijn.

## Onderzoeksthema's
1. Militair & veiligheid
2. Politiek & diplomatie
3. Overheden & crisismaatregelen
4. Financiële markten
5. Energie & grondstoffen
6. Wereldhandel & logistiek
7. Bedrijfsleven & investeringen
8. Economie & samenleving

## Wat nog ontbreekt
Verificatie tegen primaire bronnen, gebeurtenisclustering, historische signalenscores, financiële marktfeeds, scorekalibratie en private hosting. GDELT is een detectiekanaal, geen bewijs van een werkelijke militaire operatie.
