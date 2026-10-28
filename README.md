# CRISIS Intelligence — onderzoeks-pilot 0.6

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

## Automatische AI-redactie (optioneel, zonder handmatig nieuws lezen)

- Na nieuwsverzameling en de 25-kandidatenlijst draait `scripts/ai_assess.py`.
- De AI classificeert alleen de **kopclaims**: relevantie, onderwerpsoort, mogelijke escalatie/de-escalatie, redactionele urgentie en een korte uitleg in het Nederlands.
- Resultaat: [AI Nieuwsredactie](https://bjornbruinsma.github.io/crisis-intelligence-pilot/ai.html), met bronlinks en expliciet het label **niet geverifieerd**.
- Er wordt **geen** bericht automatisch tot een bewezen gebeurtenis verheven, en er worden **geen** oorlogskanspercentages gepubliceerd.
- Zonder API-sleutel draait de AI-redactie in `not_configured`-modus en worden geen betaalde aanroepen gedaan.

### Eenmalige activatie — privé API-sleutel

1. Open [OpenAI API keys](https://platform.openai.com/api-keys). Maak een API-account/project en sleutel voor de pilot. ChatGPT Plus is **niet** hetzelfde abonnement als de API: API-gebruik heeft eigen facturatie.
2. Stel een klein budget/limiet en meldingen in bij de API-provider.
3. Open [GitHub Actions secrets](https://github.com/BjornBruinsma/crisis-intelligence-pilot/settings/secrets/actions), klik **New repository secret**, en zet:
   - Name: `OPENAI_API_KEY`
   - Secret: de sleutel uit je API-project
4. **Stuur de sleutel nooit in deze chat**, zet hem nooit in code of een publieke JSON, en gebruik nooit een persoonlijke token met bredere rechten.
5. Ga naar [Actions](https://github.com/BjornBruinsma/crisis-intelligence-pilot/actions/workflows/pilot.yml), kies **Run workflow**. De reguliere runs zullen dezelfde sleutel daarna automatisch gebruiken.

Techniek: momenteel `gpt-4o-mini` via Chat Completions (JSON), met maximaal 25 actuele kandidaten per zes uur, 5 per aanvraag, maximaal **6 API-aanvragen per workflow-run** en **24 aanvragen per UTC-dag**, met caching van eerder beoordeelde kandidaat-ID's. Mislukte API-aanroepen worden als fout getoond, niet stilzwijgend als een correcte beoordeling. Kosten hangen af van het daadwerkelijke tokenverbruik en providerprijzen.

**Belangrijke beperking:** het model leest in deze fase krantenkoppen en metadata, geen volledige artikelen of officiële primaire documenten. De AI beoordeelt prioriteit en aannemelijkheid van een *nieuwsclaim*, niet de waarheid van die claim. Meertalige gebeurtenisclustering, volwaardige factchecking en historische voorspellingskalibratie zijn latere uitbreidingen.

## Pilot 0.5: gebeurtenisclustering en officiële bronvergelijking

De automatische GitHub-workflow doet na de AI-nieuwsselectie nu het volgende:

1. `scripts/primary_sources.py` probeert rechtstreeks officiële publicaties op te halen van US CENTCOM, de Britse FCDO (Iran en Saudi-Arabië) en de Amerikaanse Department of State Travel Advisory RSS-feed. Mislukte of lege bronnen worden als fout/geen data vermeld.
2. `scripts/event_cluster.py` vergelijkt maximaal 25 nieuwsclaims en groepeert ook meertalige publicaties die aantoonbaar hetzelfde voorval lijken te beschrijven. Bij twijfel blijven claims afzonderlijk. Eén kop kan meerdere gebeurtenissen noemen; volledige opsplitsing van samengestelde artikelen ontbreekt nog.
3. De tweede AI-pass vergelijkt de voorlopige groepen met opgehaalde officiële tekstfragmenten. Een match wordt pas bewaard als de geciteerde woorden *letterlijk aanwezig* zijn in het officiële brondocument.
4. Publicatie: [AI Event Intelligence](https://bjornbruinsma.github.io/crisis-intelligence-pilot/events.html) met herleidbare nieuwslinks en — waar aangetroffen — officiële publicaties; plus JSON-bestanden `site/data/event_candidates.json` en `site/data/primary_sources.json`.

**Niet claimen:** een overeenkomende officiële passage maakt het voorval niet objectief bewezen; het toont wat die instelling schrijft. Automatische semantische vergelijking blijft feilbaar. Onbevestigde groepen krijgen de status `no_matching_primary_evidence`. Ook een directe match krijgt `potential_primary_text_match_needs_review`, niet `verified`. Er zijn géén automatische kansvoorspellingen of scorewijzigingen.

Beveiliging/kosten: het openbare repository bevat nooit de API-sleutel. Het clustermodel draait op `gpt-4o-mini`. Er zijn maximaal **2 AI-aanroepen per workflowrun en 8 per UTC-dag**, met cache voor dezelfde input. Samen met de bestaande AI-redactie en het aparte OWOP-project kan extra API-gebruik plaatsvinden; bewaak het totale API-creditsaldo afzonderlijk.

De officiële brondekking is beperkt en niet representatief voor alle landen en actoren. In het bijzonder betekent geen match niet dat een voorval niet is gebeurd. Meerdere koppen zijn geen onafhankelijke bevestigingen. Volwaardige verificatie vereist het lezen van specifieke officiële primaire stukken, chronologie en tegenbewijs.

## Pilot 0.6: betrouwbaarheid van de AI-redactie

De [kwaliteitscontrole](https://bjornbruinsma.github.io/crisis-intelligence-pilot/quality.html)
rapporteert voortaan de technische metrics van iedere automatische ronde:

- Aantal oorspronkelijke artikelen, geselecteerde claims en voorlopige gebeurtenisgroepen;
- Hoeveel **zeer specifiek** als hetzelfde voorval aangemerkte koppen de AI samenvoegt;
- Of alle input-IDs ongewijzigd behouden blijven en hoe vaak modelvoorstellen worden afgewezen;
- De dekking van officiële bronnen, letterlijke tekstmatches en nog ontbrekende bevestigingen;
- Het onderscheid tussen technische uitvoeringsstatus en **onbekende** feitelijke juistheid.

De nieuwe clustermethode vraagt de AI uitsluitend om concrete *paren* van claims die dezelfde
handeling beschrijven. Alle andere claims blijven automatisch afzonderlijk staan. Hiermee
kan een onvolledig modelantwoord niet meer ongemerkt claim-ID's laten verdwijnen.
Bij fouten valt de verwerking terug op afzonderlijke kandidaten en verschijnt een
kwaliteitswaarschuwing.

We publiceren **geen precisie- of recallpercentage** zonder onafhankelijk gelabelde
testvoorbeelden. Twee krantenkoppen met dezelfde tekst zijn niet per definitie twee
onafhankelijke bronketens, en officiële algemene reisadviezen verifiëren geen specifieke
gebeurtenis zonder corresponderende publicatie.

Het aantal AI-aanroepen voor de afzonderlijke eventlaag blijft begrensd tot maximaal
2 per uitvoering en 8 per UTC-dag. Dit is alleen een applicatielimiet, geen financiële
bovengrens voor het gehele OpenAI-account of de afzonderlijke OWOP-workflow.
