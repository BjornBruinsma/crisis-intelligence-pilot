# CRISIS Intelligence — onderzoeks-pilot 0.3

Automatische **nieuwsdetectie**, nog **geen geverifieerde gebeurtenisregistratie of oorlogskansvoorspeller**.

[Dashboard](https://bjornbruinsma.github.io/crisis-intelligence-pilot/) · [Automatische runs](https://github.com/BjornBruinsma/crisis-intelligence-pilot/actions)

## Vaste werkwijze

1. Iedere zes uur leest `scripts/collect.py` twaalf experimentele Google Nieuws RSS-zoekfeeds en twee brede GDELT DOC 2.0-zoekopdrachten uit.
2. De twaalf RSS-profielen zijn acht thema's plus vier regionale zoekvensters: Iran (Perzisch), China (Chinees), Pakistan en Golfstaten (Arabisch).
3. De verzamelde **artikelmetadata** (kop, link, bron, datum, zoekprofiel) worden aan `site/data/articles.json` toegevoegd, met alleen exacte feed-items samengevoegd. Geen volledige artikelteksten.
4. `site/data/fetch_status.json` registreert per bron/profiel fouten en aantallen. Een mislukte zoekopdracht telt niet als 'geen nieuws'.
5. Het publieke dashboard publiceert via GitHub Pages. De drie hoofdmeters blijven op **geen beoordeling**.
6. In de volgende fase worden nieuwsartikelen gegroepeerd tot gebeurtenissen, geverifieerd tegen primaire bronnen en van onderbouwde en gedateerde scores voorzien.

## Acht categorieën

- Militair & veiligheid
- Politiek & diplomatie
- Overheden & crisismaatregelen
- Financiële markten
- Energie & grondstoffen
- Wereldhandel & logistiek
- Bedrijfsleven & investeringen
- Economie & samenleving

**Vier regionale zoekvensters** zijn aanvullend op deze categorieën en mogen niet verward worden met herkomst: een Chinese zoekfeed betekent niet automatisch dat een artikel uit China komt.

## Publicatie

De Actions-workflow `.github/workflows/pilot.yml` draait gepland op 00:17, 06:17, 12:17 en 18:17 UTC (GitHub kan schema's vertragen). Ook kan handmatig worden gestart via **Actions → CRISIS Intelligence news pilot → Run workflow**.

De workflow voert eerst `python -m unittest discover -s tests -v` uit, verzamelt nieuws, commit de statusgegevens en publiceert `site/` naar GitHub Pages. Nieuwsscores worden niet automatisch bijgewerkt.

## Operationele grenzen en eerlijkheid

- Google Nieuws RSS is een niet officieel als ontwikkelaars-API aangeboden feed en kan veranderen, artikelen ontbreken of verzoeken weigeren. Alleen testen met beperkte frequentie; vóór commercieel of grootschalig gebruik de voorwaarden en licenties vaststellen.
- De publieke GDELT DOC-API geeft in onze cloudomgeving soms HTTP 429. Daarom blijven er slechts twee brede GDELT-vragen over.
- Google RSS-links verwijzen vaak eerst naar Google Nieuws in plaats van direct naar de uitgever.
- Hetzelfde voorval kan door meerdere bronnen zijn beschreven. De huidige implementatie filtert **alleen exacte items** binnen een kanaal. Dit is geen gevalideerde gebeurtenisdeduplicatie.
- 'Geen artikelen' is **geen** bewijs dat er niets gebeurt.
- Noch GDELT noch Google Nieuws biedt informatie over geheime militaire besluiten. Eenzijdige selectie, censuur en propaganda zijn bekende risico's.
- Deze repository is openbaar; plaats geen vertrouwelijke documenten of sleutels in de code of het publicatiearchief.

## Volgende test

Laat de verzamelaar een paar keer draaien en beoordeel:
1. Aantal geslaagde feeds per kanaal
2. Netto nieuwe artikelen per 24 uur
3. Niet-westerse taaldekking
4. Hoeveel verschillende gebeurtenissen versus herpublicaties
5. Uitsluiten van niet-relevante artikelen
6. Of bronlinks handmatig te controleren zijn

Pas daarna gaan we indicatoren en de drie meters voeden.
