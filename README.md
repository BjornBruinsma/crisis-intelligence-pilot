# CRISIS Intelligence — onderzoeks-pilot 1.0.1

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

## Clusteringveiligheid — onafhankelijke tweede AI-check

De eerste volledige test van de paargewijze clustering stelde drie samenvoegingen voor,
maar alle drie bleken na controle problematisch: verschillende aanvalsdoelen,
verschillende evacuatiehandelingen, en stijgende versus dalende olieprijzen.
We beschouwen de eerdere samenvoegingen dus **niet als bewezen dezelfde gebeurtenis**.

Daarom is een extra modelcontrole ingebouwd: een tweede aanvraag moet ieder
voorgesteld paar expliciet goedkeuren, met een nauwkeurige vergelijking van
actor, handeling en doelwit. Ontbrekende of ongeldige beoordeling betekent
**niet samenvoegen**. Harde regels verwerpen bovendien onder meer
tegenovergestelde marktbewegingen, verschillende militaire/energie-doelen
en verschillende typen evacuaties. De drie eerder fout samengevoegde
live-koppen dienen nu als regressietests.

Maximaal **drie AI-verzoeken per event-ronde, twaalf per UTC-dag** (met eerder
verrichte aanvragen meegeteld). Voor AI-samenvattingen en OWOP gelden aparte
limieten. Ook dubbele AI-consensus kan onjuist zijn; we tonen geen
gekalibreerde betrouwbaarheidsscore zonder echte labels.

## Pilot 0.8 — onafhankelijke workflows en signaalmonitor (28 oktober 2026)

**Twee afzonderlijke automatische processen:**

- **CRISIS**: [`.github/workflows/pilot.yml`](https://github.com/BjornBruinsma/crisis-intelligence-pilot/actions/workflows/pilot.yml), iedere zes uur. Verzamelt nieuws, AI-selectie, gebeurteniskandidaten, officiële bronpassages, kwaliteitscontrole en [signaalmonitor](https://bjornbruinsma.github.io/crisis-intelligence-pilot/signals.html). De CRISIS-job voert geen OWOP-verzameling of OWOP-AI meer uit.
- **OWOP**: [`.github/workflows/owop.yml`](https://github.com/BjornBruinsma/crisis-intelligence-pilot/actions/workflows/owop.yml), viermaal daags met verschoven planning. Behoudt de bestaande eigen AI-redactie, webzoekverificatie en publicatie in `site/owop`. De OWOP-job voert geen CRISIS-analyse uit.
- Elke job schrijft **uitsluitend zijn eigen gegenereerde bestanden** terug naar `main` met een beperkt aantal retries bij gelijktijdige commits.
- Beide kunnen zelfstandig de volledige GitHub Pages-site publiceren, maar de **deploymentjobs gebruiken dezelfde seriële concurrencygroep** en laden eerst de nieuwste `main`. Zo blijven de pagina's onder hetzelfde webadres beschikbaar.

**Extra officiële bronnen:** bovenop CENTCOM, de Britse reisadviezen en het Amerikaanse ministerie van Buitenlandse Zaken worden onder meer IMO (scheepvaart), het Pakistaanse en Chinese ministerie van Buitenlandse Zaken, het ministerie van Buitenlandse Zaken van de VAE, de Iraanse buitenlandse dienst, het Amerikaanse ministerie van Financiën en EIA (energie) onderzocht. Bronnen worden parallel met maximaal vijf verbindingen opgehaald; mislukte sites tellen uitdrukkelijk als onbeschikbaar, niet als negatief bewijs. Dit zijn bronnen over het **eigen officiële standpunt** van een autoriteit; noch de relevantie van de passage noch het perspectief bewijst automatisch de gebeurtenis.

**Nieuwe onderzoeksmonitor:** `scripts/signals.py` telt per AI-gegroepeerde kandidaat maar één voorlopige richting (escalatie/de-escalatie/gemengd/neutraal/onbekend) en toont het aantal gerelateerde officiële tekstmatches. De pagina `site/signals.html` en de JSON-bestanden `site/data/signals.json`, `site/data/signal_history.json` bevatten de nieuwste steekproef en maximaal 120 dagelijkse snapshots. Dit zijn **NIET** real-world incidentenaantallen, een representatieve meting, een voorspelling, een tijdreeks voor causaliteit of een gecalibreerde oorlogskans. De drie hoofdmeters blijven leeg.

**Financiën:** de app-limieten voor het aantal AI-calls in de verschillende scripts beperken aanvragen maar zijn geen harde geldlimiet. CRISIS en OWOP delen dezelfde OpenAI API-sleutel/betaalrekening; gebruikers moeten bestedingen en automatische opwaardering in hun OpenAI-account zelf bewaken.

**Vervolg na technische tests:** een gelabelde evaluatieset van echte *zelfde-gebeurtenis / andere-gebeurtenis*-paren, gerichte raadpleging van de daadwerkelijke individuele primaire documenten en historische backtesting voordat welke risicokans dan ook zichtbaar mag worden.

## Pilot 0.9 — gerichte controle van oorspronkelijke documenten

De AI-redactie kan nu per hooggeprioriteerde onbewezen nieuwsclaim proberen het
**concrete oorspronkelijke officiële document** te vinden. Een openbare zoekdienst
(Bing RSS) en de reeds opgehaalde officiële publicatielijsten worden uitsluitend
als **vindplaats** gebruikt. Zoekresultat-snippets zijn geen bewijs.

Alleen werkelijk opgehaalde HTML-documenten op vooraf toegestane overheids- en
intergouvernementele domeinen worden aan het vergelijkingsmodel aangeboden.
De software controleert dat elk geciteerd tekstfragment letterlijk binnen
een aangeleverde documentpassage valt; bij onvoldoende gegevens blijft de
status `primary_document_not_found` of `documents_found_unassessed`.
De publicatiedatum van een document wordt opgeslagen, maar wordt nooit
stilzwijgend tot gebeurtenisdatum verheven. Een officieel statement is
niet automatisch onafhankelijk bewijs van de objectieve gebeurtenis.

De nieuwe [claimgerichte broncontrole](https://bjornbruinsma.github.io/crisis-intelligence-pilot/claims.html)
toont originele documenten, specifiek ondersteunende *verklaringen*, eventuele
tegengestelde officiële verklaringen en een zoeklog. Ook het
[kwaliteitsdashboard](https://bjornbruinsma.github.io/crisis-intelligence-pilot/quality.html)
bevat nu de afzonderlijke claimcontrole.

Kosten- en intensiteitslimieten: maximaal 3 nieuwe claims per run en 9 per
UTC-dag, maximaal 2 origin-documenten per claim, maximaal 6 goedkope
modelvergelijkingsaanvragen per UTC-dag. Resultaten blijven minimaal 24 uur
in cache. Dit is een gebruikslimiet in de pilot, **geen harde limiet op
OpenAI-accountkosten**. Bing RSS en officiële websites kunnen verzoeken
weigeren of onvolledige zoekresultaten geven. Een negatieve zoekuitkomst
ontkracht nooit een nieuwsclaim. Vooralsnog geen geverifieerde
gebeurtenisregistratie, automatische risicokans of gekalibreerde inschatting.

## Pilot 1.0 — zoekdekking en chronologische verificatie (28 oktober 2026)

- De officiële broncollector gebruikt nu de *werkelijke* Engelstalige
  [China MFA-index](https://www.fmprc.gov.cn/mfa_eng/index.html)
  en [Pakistan MFA-perspagina](https://www.mofa.gov.pk/press-releases).
  Chinese persconferentie-links worden bewaard voor nadere documentcontrole,
  ook als de titel geen specifiek land noemt.
- De claimgerichte zoeklaag combineert de actuele officiële bronsite-links
  met de publieke [GOV.UK Search API](https://www.gov.uk/api/search.json)
  en maximaal drie afzonderlijke issuer-specifieke Bing RSS-zoekopdrachten.
  Zoekresultaten dienen **alleen om originele publicaties te vinden**;
  een zoekfragment wordt nooit rechtstreeks als bewijs gebruikt. Een site die
  niets teruggeeft of een fout heeft, wordt apart geregistreerd.
- De verifier geeft per claim aan hoeveel oorspronkelijke officiële documenten
  zijn geopend, welke zoekaanbieders bereikbaar waren en welke passages
  letterlijk teruggevonden zijn. Het [kwaliteitsrapport](https://bjornbruinsma.github.io/crisis-intelligence-pilot/quality.html)
  toont de opbrengst van de bronzoektocht naast de status van de claims.
- Bij de datumcontrole wordt de publicatiedatum van de nieuwsclaim onderscheiden
  van de gebeurtenisdatum. Een gevonden officieel document dat meer dan 21 dagen
  ouder is dan de kop wordt automatisch tot **historische context** teruggezet,
  zelfs wanneer de AI het als directe ondersteuning wilde markeren.
  Dit is een voorzichtige vuistregel, geen onweerlegbare beoordeling.
- Wanneer de clustering haar AI-daglimiet bereikt, blijft de laatst geldige
  AI-groepering als cache behouden. Nieuwe of verdwenen artikelen worden
  conservatief afzonderlijk getoond. Het dashboard meldt expliciet dat de
  clustering op dat moment **niet opnieuw** is uitgevoerd.

We **kunnen geen specifieke gebeurtenis als bewezen publiceren** zonder
een primaire publicatie met een passende actor, handeling, doelwit en
chronologie. Ook directe overheidspublicaties kunnen onjuist zijn:
ze bewijzen in de eerste plaats wat de autoriteit verklaart. De drie
risicowijzers blijven buiten gebruik tot er voldoende gelabelde,
onafhankelijk gecontroleerde cases en historische backtests bestaan.

De bestaande limieten voor de claimgerichte pilot blijven ongewijzigd:
maximaal 3 nieuwe claims per uitvoering, 9 per UTC-dag, maximaal
2 bezochte originele documenten per claim en 6 AI-vergelijkingsaanvragen
per UTC-dag; zoekopdrachten naar publieke website-informatie zijn beperkt.
De kosten zijn afzonderlijke OpenAI-API-kosten en dit is geen geldplafond.

## Verificatiecorrectie na eerste live-test

De eerste versie van de uitgebreide zoeklaag vond twee GOV.UK-passages die
door het model **ten onrechte** werden aangemerkt als directe ondersteuning:
1) een waarschuwing over *voorgenomen* Iraanse doelen bij een kop over
*daadwerkelijke* luchtaanvallen; 2) Houthi-raketlanceringen bij een kop over
Saoedische raketonderscheppingen. Dit zijn verschillende handelingen.

Daarom moet elke AI-aanwijzing `direct_statement` nu een extra
deterministische consistentiecontrole doorstaan: de concrete handeling in
de nieuwskop moet overeenkomen met die in het letterlijke citaat.
Algemene GOV.UK-reisadviezen zijn geen directe bevestiging van afzonderlijke
militaire incidenten. Bij claims over aanvallen, onderscheppingen,
evacuaties, blokkades of inbeslagnames is een officiële publicatiedatum
vereist voordat een specifieke match de label `direct_statement` mag
behouden. In alle gevallen blijft `verified_event=false`.

Ook **gecachete resultaten** worden automatisch herbeoordeeld. Afgewezen
matches worden gedowngraded naar `related_only`, met een expliciete reden
en een aangepaste samenvatting. Nieuwe regressietests gebruiken deze echte
foutvoorbeelden. Dit is een conservatieve, beperkte regelset en nog geen
onfeilbare onafhankelijke waarheidscontrole.
