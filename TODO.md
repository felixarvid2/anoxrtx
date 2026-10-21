# Att göra: Anachronox RTX

Uppdaterad 2026-10-18. Prioritering och acceptanskriterier finns i
[PLAN.md](PLAN.md), nuläge och källor i [STATUS.md](STATUS.md).
`[x]` betyder bara att den avgränsade leveransen nedan är klar;
implementerat men inte sett i relevant spelmiljö anges uttryckligen.

## Nästa implementationer, i ordning

- [x] **0. Första ljusläget efter sparladdning:** startup bytte grafikdevice utan
  att återskapa ljusen. Livscykelrättning och Rowdy's-jämförelser verifierade;
  se [evidens](docs/startup-lighting-check.md). Andra kartor/runtimes återstår.
- [x] **1. Automatisk bildregression, första version:** `anoxcapture.py` och
  `anoxcompare.py` ger verifierade manifest, flerbildsjämförelser och rapporter.
  61 Python-tester passerar; positiva/negativa Rowdy's-kontroller verifierade.
  Baslinjepromovering är uttrycklig och manuell. Fler testmiljöer återstår;
  se [arbetsflödet](docs/screenshot-regression.md).
- [x] **2. Debug-overlay:** Anachronox-panel (F8 / Alt+C) med karta, kamera, tillstånd, reloadorsak,
  ljus och ljusstilar; verifierad under Proton (QindieGL #27). Kvar: cullingdiagnostik.
- [x] **3. Händelsestyrt animerat ljus:** spelets ljusstilar 1–63 styr ljusen, START_OFF exporteras och
  hålls släckt av spelets stil; verifierat i crevice och levant1 (QindieGL #27). Kvar att se i spelet:
  ett ljus som tänds under spel, paus och save-återställning.
- [x] **4. BSP/PVS:** mätt med riggkamera och `--ab-cfg "set r_novis 1"` (docs/culling-check.md): ingen synlig
  skillnad i sex vyer, upp till 60 % längre bildtid i votowne. Spelets PVS behålls; prova `r_novis 1` per bana
  om ljusläckor eller saknade skuggor syns.
- [ ] **5. Dynamisk emission:** synkronisera ett verifierat material med
  ljushändelser, utan kvarhängande tillstånd eller dubbel illumination.
- [ ] **6. PBR-klassificering:** vidareutveckla befintliga namnregler med
  dataregler, undantag, BSP-flaggor och osäkerhetsrapport; kan gå parallellt.
- [ ] **7. Ankarmeshar:** stabila författar-ID:n, per-karta-data, ersättnings-
  och resurslivscykel; statiska ankare först.
- [ ] **8. Dimma/miljötillstånd:** mjuka, verifierade övergångar och återgång
  till kartbaslinjen; ingen global Numos-himmel.
- [ ] **9. Väta/regn:** en utomhuskarta först, skydd inomhus, upptorkning,
  runtime-fallback och uppmätt prestanda.

## Befintligt som fortfarande behöver spelverifiering

- [ ] Utomhusbaslinje: HD-himmel och Numos sol-/skuggriktning på avsedda kartor.
- [ ] Vatten: genomskinlighet, stabil geometrihash och material i relevant vy.
- [x] Lava: `proc_lava` fryses (256x256, hash 0x561447B2DFA181FD) och ersättningsmaterialet syns i levant2 (2026-10-18). Orsak: HD-paketets uppskalade palett (anoxgfx kräver 256 px bred) + QindieGL fyllde gammal D3D-textur. `proc_lavafloe` ej sedd i bild än. levant1 och hephlava går inte att se med riggkameran (banstarten ritar ingen värld, även originalet svart, 2026-10-19); kräver en sparfil nära lavan.
- [x] Figurer för mörka: fyllnadsljus per figur relativt kartljusen (QindieGL #30/#32, `model_fill = 1.5` + egna värden
  för 5 banor), 10 banor inom ±0,3 EV mot originalet (2026-10-19). Övriga ~69 banor omätta.
- [ ] greattree: lila ton under Remix som originalet saknar.
- [ ] Himmel: commbase och commiteon får mörk natthimmel under Remix där originalet har ljus himmel med sol
  (+0,8–1,4 EV mörkare bild, 2026-10-19). slevant saknar originalets orange dis över lavan. Exponering inte satt för dessa.
- [ ] **Bridge-stopp vid banladdning:** Remix-bryggan låser sig ibland när en bana laddas: `Data Queue overwrite`
  utan "resolved" i bridge32.log, servern svarar inte, bilden fryser på laddskärmen. **servicetunnel från menyn:
  3 av 10 laddningar** (2026-10-21, `anoxrig.py console map servicetunnel`, oförändrad build). I alla tre kom
  QindieGL aldrig till kartljusen (som läggs på 120 bildrutor efter banbytet): stoppet sker medan banans
  geometri/texturer laddas, så kartljusen är inte orsaken (ett tidigare lyckat försök utan kartljus var slump;
  en gren som sprider ut ljusskapandet, QindieGL `feat/maplights-spread-create`, är inte skickad). Även
  labbuilding har stannat. Med `+map` vid start stannar crevicelanding/labbuilding/servicetunnel alltid.
  Utslagning (10 laddningar var, 2026-10-21, `[game.anox]` i QindieGL.ini): allt på 3/10, alla tillägg av
  (remixapi, maplights, dlights, proctex, smoothnormals) **0/10**, bara API-delen av 5/10, bara proctex av 3/10,
  bara smoothnormals av 4/10. Ingen enskild funktion är orsaken; troligen ett tidsberoende lopp som varje
  tillägg kan utlösa. Nästa steg: trådstackar från bridge-servern (och spelet) medan den hänger.
- [ ] Strid: dlights ritas nu (QindieGL #30 hashfix, verifierat med testljus via `anoxcheck.py --ab-dlight`,
  QindieGL #31): styrka 300 intill Boots i rowdys = tydligt, ej utbränt (+0,84 EV). Anachronox skapar dlights
  bara från entiteters ljusfält i skript/strid (inga mynningsflammor; 0 dlights i alla startvyer inkl. cine).
  Kvar: kalibrera `dlight_scale` (nu 1) mot originalet i en riktig stridsvy.
  QindieGL #6 är redan mergad; välj flashblend-fallback bara från evidens
  och kontrollera att samma händelse inte belyses dubbelt.
- [ ] Fler TimeMinder-testplatser och repeterbara händelsescenarier.
- [ ] Kartljus utanför Rowdy's; kalibrera formeln först efter korrekt initiering.
- [ ] PBR-närbilder: ljusa kanter, glas och materialundantag; figurmaterialens
  roughness/metalness efter `smoothnormals`.
- [ ] Dimma i fler miljöer, inklusive den tidigare blockerade whitecaves-b-vyn.
- [ ] Dörrar/brush-normaler, partiklar, strålar och himmelsklassning i fler kartor.

## Separat bild- och underhållsarbete

- [ ] Rätt bildformat och högre renderupplösning utan felaktig UI-/musmappning.
- [ ] Komplettera UI-/intro-, partikel- och stråltexturlistor.
- [ ] Fasta CPU-/GPU-bildtider och VRAM-baslinjer innan prestandainställningar ändras.
- [ ] Remix overlay-/capture-hotkeys från riggen; konsolinput är separat och rättad.
- [ ] MSVC-bygge och Windows-verifiering; Linux-bygge bevisar inte dessa.
- [ ] Installations-/toggle-regression vid relevanta ändringar, runtime-uppgraderingar
  med Wine-fixarna bevarade, samt lämpliga upstream-PR:ar.
- [ ] Granska externa modellroutningsförslag separat: anoxrtx #28 och QindieGL #23
  var öppna vid dokumentationsöversynen.

## Implementerat och avgränsat verifierat

- [x] Linux-crossbygge med 385 exporter och fungerande Proton/Remix-grund.
- [x] Borderless fullscreen, mjuka modellnormaler och stabilare figurhashregel.
- [x] BSP-kartljus, spot/sol, per-karta-formel/config och filbaserade overrides.
- [x] QindieGL #21: nya Remix-identiteter rättar reproducerad ljusreload;
  båda Rowdy's-sparvyerna visar skala 0/1. Initialt ljusläge är fortfarande öppet.
- [x] Timerstilar 1–11 implementerade; detta är inte spelstyrda switchhändelser.
- [x] Emissiv-, PBR-/glas-, HD-himmel-/vätske-/modellgeneratorer samt Chuncki-
  hashmappning finns. Normaler och fem emissiva skyltar har synlig effekt i två
  Rowdy's-vyer; detta verifierar inte alla material eller miljöer.
- [x] DLSS fungerar under GE-Proton; DLAA är standard. NRC fungerar inte och
  hålls avstängt med `rtx.integrateIndirectMode = 0`.
- [x] GL-dimremap och per-karta-Numos finns; haze sedd i bricksb, sunstrip och Rowdy's.
- [x] Installerare och toggle-script finns; speldata genereras lokalt.
- [x] Riggstart, fokuserad rörelse och nonce-verifierad sparladdning finns.
- [x] anoxrtx #27: fysisk XKB-input rättad; 33 offline-tester, båda sparvyerna,
  lång gammal prompt, repeat-avvisning och avbrottsfrisläppning dokumenterade.

Detta är en dokumentationsavstämning av tidigare resultat, inte nya speltester.
Se [RESULTS.md](RESULTS.md) och de daterade rapporterna under `docs/`.
