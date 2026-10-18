# Implementationsplan: Anachronox RTX

Uppdaterad 2026-10-18 efter ägarens utökade önskelista. Den här planen ersätter
den gamla fasordningen. [STATUS.md](STATUS.md) anger vad som faktiskt finns och
vad som har verifierats; [TODO.md](TODO.md) är arbetslistan. Äldre resultat och
idéfiler behålls som historik, inte som nya implementationskrav.

## Prioritering och beroenden

Ordningen väger synlig nytta mot beroenden och risken att bygga vidare på ett
felaktigt ljusläge. Bildjämförelser kommer tidigt för att kunna bedöma resten.
Culling undersöks tidigt, men en ny policy införs först efter mätningar av
saknad geometri, skuggor, reflektioner och kostnad. PBR-spåret kan genomföras
oberoende av nya spelhookar när bildbaslinjerna finns.

| Ordning | Leverans | Förväntad nytta | Svårighet | Huvudrepo / beroende |
| --- | --- | --- | --- | --- |
| 0 | Förklara/rätta första ljusläget efter sparladdning | Förutsättning för tillförlitliga ljusresultat | Medel, orsak okänd | Båda; rättad input och wrapper finns |
| 1 | Automatiska skärmbildsregressioner, första version | Hög för utveckling | Medel | anoxrtx; byggs under steg 0 |
| 2 | Runtime-overlay med Anachronox-diagnostik | Medel, underlättar felsökning | Medel | QindieGL; utöka befintlig ImGui |
| 3 | Händelsestyrt animerat ljus och gemensam tillståndsläsning | Mycket hög | Medel, hooklayout måste verifieras | Båda; steg 0–2 |
| 4 | Förbättrad BSP/PVS-culling och sceninlämning | Mycket hög potential | Hög | QindieGL + BSP-verktyg; mätningar börjar i steg 1–2 |
| 5 | Dynamiska emissiva material | Hög | Medel, runtime-stöd måste provas | Båda; steg 3 |
| 6 | Förbättrad automatisk PBR-klassificering | Hög | Medel | anoxrtx; steg 1, kan gå parallellt med steg 3–5 |
| 7 | Ankarmeshar för ersättningsinnehåll | Hög | Medel | Båda; stabil identitet och livscykel |
| 8 | Animerad dimma och miljötillstånd | Hög | Medel | Båda; tillståndsläsning från steg 3 |
| 9 | Väta och regn | Medel–hög | Hög | Båda; material, miljötillstånd och culling verifierade |

Detta täcker samtliga nio önskade funktioner; numreringen i önskelistan saknade
punkt 4. Steg 0 är ett befintligt fel, inte en ersättning för någon funktion.

## Steg 0–1: ljusinitialisering och reproducerbara jämförelser

**Första implementationen:** en liten regressionskörning kring den befintliga
riggen, samtidigt som första ljusläget undersöks. Behåll ljus- och materialvärden.

1. Upprepa kallstart och sparladdning i båda Rowdy's-vyerna, även omvänd
   laddningsordning och återladdning av samma sparfil. Verifiera nonce,
   sparfingeravtryck och kameraposition innan bilden godtas.
2. Fånga efter samma insvängningstid före varje config-/override-omladdning;
   jämför sedan omladdning av samma värde samt skala 0 → 1 vid samma pose.
   Knyt API-/initieringsloggar till bilderna. Ändra livscykeln först när
   en reproduktion motiverar det; ljusstyrkekalibrering är ett separat arbete.
3. Lägg till manifest med DLL-/runtime-/config-/lagerfingeravtryck, upplösning,
   sparfil, pose, väntetid och flera bildrutor. Avvisa olika miljöer och misslyckade
   laddningar. Börja med rapporter, före/efter-bilder och differensbilder.
4. Mät variationen mellan oförändrade körningar. Använd områden/masker för
   rörliga figurer och toleranser som fångar tydliga ljusbortfall; kräv inte
   pixelidentiska bilder från en temporal renderer. Bildmedelvärde räcker inte.
5. Lägg till utomhus-, vatten-, lava- och stridsvyer när giltiga lokala sparfiler
   eller verifierade scenarier finns. Markera saknade vyer som ej testade.

**Klart när:** första ljusläget är förklarat och vid behov rättat, upprepade
laddningar visar rätt bidrag utan manuell reload, och jämföraren accepterar
upprepade baslinjer men upptäcker en avsiktligt avstängd ljusvariant. Riggen
återställer filer, Steam och display även vid fel. Baslinjer godkänns uttryckligen
vid avsiktliga bildändringar; misslyckade körningar skriver inte över dem.

## Steg 2: utöka befintlig debug-overlay

Visa karta/pose, runtime/API-layout, aktiv config, initierings-/reloadorsak,
antal skapade/ritade ljus, fel, observerade spelstilar och senare cullingräknare.
Använd samma diagnostik i loggarna så bildtester inte kräver UI-input. Börja
med läsning; ljusredigering kan följa senare.

**Klart när:** panelen går att öppna/stänga under Proton utan vit overlay eller
fastnade tangenter, visar samma data som loggen och inte kommer med i normala
regressionsbilder. Avstängd diagnostik ska ha försumbar mätbar kostnad.

## Steg 3: händelsestyrt ljus och tillståndsläsning

Behåll befintliga dlights och timerstilar 1–11. Verifiera Anachronox egen
frame-/lightstyle-layout och läs verkliga stilvärden, av/på-signaler och speltid
vid den befintliga renderhooken. Anta inte standard-Quake-layout. Utöka
`bsp2lights.py` och wrapperns format tillsammans: START_OFF-ljus får inte
försvinna ur underlaget, och dynamiska stil-/entitetskopplingar behöver bestå.
Behåll kompatibilitet med äldre `.lights`-filer och skilj beständiga
författar-ID:n från flyktiga Remix-identiteter. Lägg till datadrivna
övergångar/keyframes för en verifierad händelse, med timerfallback när giltig
speldata saknas. Dela ett litet observerat tillstånd med senare material/dimma;
bygg inget generellt skriptsystem innan det behövs.

**Klart när:** ett START_OFF-ljus kan tändas och släckas från spelet, en animerad
stil följer speltid inklusive paus/laddning, och omladdning/kartbyte varken ger
spökljus eller dubbla ljus. Verifiera även synliga dlights i ett stridsscenario.

## Steg 4: BSP/PVS med hänsyn till path tracing

Börja med diagnos av nuvarande cullingvariabler och renderinlämning vid dörrar,
hörn och reflekterande ytor. Skilj geometri som spelet aldrig skickar från
wrapperns ljus-/objekturval. Vanlig kamera-PVS får inte ta bort ytor som behövs
för skuggor, reflektioner eller indirekt ljus. Heretic 2-koden är en referens,
inte en färdig Anachronox/Linux-lösning.

Prova därefter en konservativ policy med kamera-/områdeskoppling, relevanta
grannområden och säkra undantag, styrd per karta och med fallback. Mät först;
undvik att göra full avstängning av all culling till standard. Hookar kräver
verifierade signaturer och opt-in. Format för eventuell BSP-metadata måste
versioneras tillsammans med verktygen.

**Klart när:** valda hörn-/dörr-/spegeltester inte tappar synlig geometri,
skuggor eller indirekt ljus; spara jämförelser för nuvarande, konservativ och
fullständigt synlig referens. Redovisa CPU-/GPU-bildtider, inlämnad geometri
och VRAM mot budgeten på 8 GB. Aktivera enbart styrkta kartprofiler.

## Steg 5: dynamiska emissiva material

Använd samma observerade tillstånd som ljusen. Prova först en skylt/lampa med
två emissiva lägen i den installerade runtimen; kontrollera vilken material-API
eller stabil ersättningsväg som faktiskt fungerar innan resten byggs. Det
befintliga emissiva USD-lagret är statiskt och lavafrysning är inte ett
händelsesystem. Behåll stabil texturidentitet och undvik dubbel belysning från
emission och kompletterande API-ljus.

**Klart när:** yta och belysning följer samma av/på-händelse, återställs vid
sparladdning och kartbyte och saknar kvarhängande material/ljus. Dokumentera
stock/Plus-stöd och fallback separat.

## Steg 6: vidareutveckla PBR-klassificeringen

Utgå från `tools/pbr_layer.py`: första match på delsträngar i filens basnamn
ger redan materialvärden. Flytta regler till granskningsbar data, prioritera
explicita materialundantag, kombinera sökväg/BSP-flaggor och rapportera
regel, klass och osäkra fall. Använd representativa metall-, sten-, trä-,
glas- och skyltmaterial; sky/vätska och handgjorda lager ska behålla sina
avsedda regler. Ingen extern bildmodell krävs för första versionen.

**Klart när:** klassificering och lager är reproducerbara, tvetydiga namn får
konservativ fallback, lagerstyrka och hashar bevaras och granskade närbilder
visar bättre material utan nya ljusa normalränder.

## Steg 7: ankarmeshar

Inför ett litet versionsmärkt per-karta-format med beständigt ID och transform.
Bevisa först en unik, stabil ankarmesh och en fast ersättning i en karta.
Kontrollera hashregler, kollisioner, synlighet, material-/meshresurser och Remix
ersättningsbeteende; funktionspekare i API:t är inte bevis på fungerande ankare.
Rörliga föräldrar följer efter den statiska leveransen.

**Klart när:** ersättningen sitter kvar efter omstart och reload, två ankare
inte byter innehåll, kartbyte rensar resurser och eventuell rörlig förälder
verifieras separat. Modellinnehåll hålls utanför generator-/kodcommits.

## Steg 8–9: miljöövergångar, sedan väta/regn

Utöka befintlig per-karta-config/GL-dimma med verifierade undervattens-,
film- eller andra speltillstånd, uttrycklig prioritet och återgång till
kartans grundvärden. Testa vilka variabler som kan ändras mjukt under drift.
Ingen global Numos-himmel eller återaktivering av NRC. **Klart för steg 8:**
övergång och återgång fungerar även vid paus, sparladdning och kartbyte, med
en definierad fallback där en runtime saknar stöd.

Regn/väta börjar sedan på en enda utomhuskarta: separat nederbörd och
materialväta, skyddade inomhusytor och mjuk upptorkning. Utred Plus-specifika
effekter och stock-fallback, rörelse/culling och prestanda innan fler kartor.
**Klart för steg 9:** regn syns utomhus, tak skyddar, torra/våta tillstånd
återställs korrekt och uppmätt bildtid/VRAM ligger inom vald budget.

## Gemensamma leveranskrav

Varje steg delas i små granskbara PR:ar med källkod/format, relevant test och
evidensrapport. QindieGL ansvarar för hookar, GPU-/API-livscykel, synlighet och
overlay; anoxrtx för generatorer, författardata, installerare och bildrigg.
Bygg wrapperändringar med Linux/MinGW och kontrollera 385 exporter. Redovisa
MSVC, stock/Plus och faktisk spelverifiering separat. Dokumentationsändringar
kräver diff-/länkgranskning, inte en ny DLL-byggnad.

Ändra inte standardljus för att dölja initieringsfel. Behåll Wine-fixarna,
ägarens telemetriinställningar och reproducerbara lokala assetbyggen. Kör en
spel-/GPU-session åt gången med nätström, beständiga backupper och verifierad
återställning. Saknade testplatser är en uttrycklig begränsning, inte ett godkänt
resultat. Bildformat/upplösning, UI/partiklar och MSVC kvarstår som separata
underhållsspår i TODO, utan att försvinna bakom nya funktioner.
