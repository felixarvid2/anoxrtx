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
- [x] greattree/waukees: lila ton (2026-10-22) kom från den gulvita dimman som volymdimma; dimma av på båda.
- [x] labbuilding (2026-10-21): fönstret visade grått i stället för staden: Remix gjorde kartans dimma till volymdimma
  som täckte himlen; `enableFogRemap = False` för banan. `model_fill = 0.6` (figur +0,17 EV), exponering global (median 0,0).
- [ ] labbuilding: originalets dis över staden och turkosa ton i en korridor saknas under Remix; en lampa rakt ovanför
  en figur i trappan bränner ut den (-1,2 EV mot bilden), oberoende av `model_fill`.
- [x] Andra banor med `fog` och himmel bakom glas/öppningar (2026-10-22): vyer mot himlen (`find_views.py --sky`)
  på 26 banor; 13 har himmel synlig från startens PVS. Bara tours hade dimma framför himlen (dimma av; bild
  -1,72 → -1,59 EV). Övriga banor går inte att se mot himlen från banstarten (behöver sparfiler).
- [ ] tours: stadssilhuetten i skyboxen (ACORP-tornet, neonskyltar) syns inte under Remix, himlen blir en jämn
  turkos yta; `skyBrightness = 140` gör den bara vit och ljussätter hela gatan. Inte dimma.
- [ ] bricksd: neonskyltarna (FIGHTING/TRAINING/BOXING) är matta under Remix mot klart lysande i originalet;
  oförändrat med dimma av (emissivt material).
- [ ] mmuseum: fönstren är vita under Remix, blå i originalet; oförändrat med dimma av.
- [x] crevicelanding (2026-10-22): det landade skeppet (`ob_shuttlewhol6`) är fullbright i originalet (entity.dat
  lighting = 1) och var nästan oupplyst under Remix. Emission från egen HD-textur, intensitet 0,5 (mod.usda):
  vy 1 +2,0 → -0,24 EV, vy 4 -0,61. `rtx.worldSpaceUiTextures` gjorde skeppet platt och ~1 EV för ljust.
- [ ] 705 entitetstyper i entity.dat har lighting = 1 (fullbright i originalet); fler kan vara oupplysta under Remix.
- [x] Himmel commbase/commiteon (2026-10-21): skyboxen ritades men autoexponeringen anpassade sig till den soliga marken,
  så himlen blev 4–7 EV för mörk. `rtx.skyBrightness = 140`, bias -0,2 och dimma av (turkos dimma färgade marken).
  Bild median +0,03 EV, himmel +0,2–0,9 EV.
- [x] Andra utomhusbanor med skybox (2026-10-22): uppåtvyer på 24 banor. whitendon hade samma mörka himmel
  (`skyBrightness = 100`, bias -4,0, median -0,3 EV); waukees bias -0,4. Övriga utan himmelsfel.
- [x] hephaestus/fortressgrounds (2026-10-22): hephaestus bias -2,0 (startvy +0,13, vyer median -0,7);
  fortressgrounds oförändrad (startvy -0,04, bara den vita helikopterplattan mörkare).
- [ ] commbase: de gula laserstrålarna (från `ob_lasersentinel`) är mörka under Remix (2026-10-22 undersökt).
  Spelet ritar dem otexturerade (GL_QUAD_STRIP, 24 hörn, blend SRC_ALPHA/ONE, färg ffcc00, kärna alfa 1 + halo 0,5).
  De gröna linjerna (`ob_commlaser`, `objects/commlaser.tga`) ser redan ut som originalet. Provat utan resultat:
  `enableEmissiveBlendEmissiveOverride` (även intensitet 100, även i rtx.conf), commlaser-hashen ur `beamTextures`,
  emissivt material. QindieGL-grenen `wip/untextured-additive` ger dem en 4x4-textur i deras färg (hash
  0xF9CE231054C9B9AC): inte längre svarta men bara svaga. Nästa steg: titta på instansen i Remix dev-menyn.
  (+0,8–1,4 EV mörkare bild, 2026-10-19). slevant saknar originalets orange dis över lavan. Exponering inte satt för dessa.
- [x] **Bridge-stopp vid banladdning (löst 2026-10-21):** Remix-bryggan låste sig när en bana laddades
  (`Data Queue overwrite` utan "resolved"): spelet väntade i `UnlockRect` på plats i dataringen medan servern,
  sysslolös, väntade på nästa kommando (trådstackar via winedbg). Risken styrs av ringens storlek
  `clientChannelMemSize`: servicetunnel 48 MB 10/10, 96 MB (standard) 3–5/10, **192 MB 0/10** laddningar;
  `clientDataQueueSize` 30000 hjälpte inte (5/10). Med 192 MB laddar även crevicelanding/labbuilding/servicetunnel
  med `+map` och fem stora banor från menyn. Installern skriver `clientChannelMemSize = 201326592`.
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
