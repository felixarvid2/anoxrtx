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
  för 5 banor), 10 banor inom ±0,3 EV mot originalet (2026-10-19). Övriga 69 banor mätta 2026-10-22: 60 användbara,
  37 fick egna värden (0,1–6) i två varv; 49 av 60 nu inom ±0,35 EV.
- [ ] Figurer för ljusa även vid `model_fill = 0.1` (rummets ljus räcker): tensil -0,9, bricksd -0,66, hephfactory
  -0,58, sendormitory -0,56, waukees -0,5, franks -0,48, levant1 -0,44 EV. fortressgrounds/grumpos +0,6/+0,9 för
  mörka och påverkas inte av fyllnadsljuset.
- [x] greattree/waukees: lila ton (2026-10-22) kom från den gulvita dimman som volymdimma; dimma av på båda.
- [x] labbuilding (2026-10-21): fönstret visade grått i stället för staden: Remix gjorde kartans dimma till volymdimma
  som täckte himlen; `enableFogRemap = False` för banan. `model_fill = 0.6` (figur +0,17 EV), exponering global (median 0,0).
- [x] labbuilding: diset över staden (2026-10-25) är inte dimma (himlen ritas utan GL-dimma, enligt gl_log) utan
  fönsterglaset `sunder/sun_glass3` (ljus blåvit, SURF_TRANS33, 33 % över staden). pbr_layer.py gjorde det till klart
  AperturePBR_Translucent-glas: diset borta och rummet speglades i rutan. Nu `HAZE_GLASS`, inget material: diset och
  strimmorna syns, inga speglingar; rutan är något gråare än originalet (opacity_constant 0,2/0,33 och emission
  provade: ingen skillnad resp. mjölkvit ruta). Dimma-remap av ger svart himmel, inte dis.
- [x] labbuilding: grönturkos ton i korridorerna saknades under Remix (2026-10-25, goto-vyer spot4/8/9: grönandel av
  linjärt ljus 0,36–0,40 i originalet, 0,35 under Remix). Inte dimma (enda func_fog är liten och vit) och inte
  textur (originalrenderaren använder samma HD-texturer). Ljusfärgerna går rätt in i `.lights` (34 gröna lampor
  0,62 0,80 0,59 / 200 bredvid vita 85), men ×2/×4 via `labbuilding.override` (`N scale S`) flyttar grönandelen bara
  0,347 → 0,355: de lysande takpanelerna dominerar. ×16 ger 0,37–0,38 utan att bilden blir ljusare (×32 0,38–0,39):
  `maps/overrides/labbuilding.override` (34 rader `N scale 16`), installeras av `lights`-steget om ingen egen finns.
- [ ] labbuilding: en lampa rakt ovanför en figur i trappan bränner ut den (-1,2 EV mot bilden), oberoende av
  `model_fill`.
- [x] Andra banor med `fog` och himmel bakom glas/öppningar (2026-10-22): vyer mot himlen (`find_views.py --sky`)
  på 26 banor; 13 har himmel synlig från startens PVS. Bara tours hade dimma framför himlen (dimma av; bild
  -1,72 → -1,59 EV). Övriga banor går inte att se mot himlen från banstarten (behöver sparfiler).
- [x] Graphical Enhancements 0.3 (ModDB) installerat 2026-10-23 (`install.py --ge ZIP`): 1573 lösa modell- och
  himmelstexturer; dess `textures/` hoppas över (Chuncki täcker dem). Nya hashar läggs till bredvid de gamla
  (`rehash_textures.py add`, `maps/ge_texmap.tsv`): himmelslistan, dekaler, skeppets emission, materialöverskrivningar
  och FLUX-affischerna; GE:s uppskalning vinner över `models_hd`/`hd_sky`. Kontroll: crevicelanding -0,24/-0,60 EV
  (före -0,23/-0,63), sendormitory -0,08, tours himmel ritas som himmel (bild -0,48 EV, före -1,59).
  GE:s 12 bantexturer (`bricks/01comp`, `02comp`, sexmachine-flaskor/glas, `#alphatest`) är originalen med solid
  alfa i stället för grå; `merge_alpha.py` ger Chunckis 4x-bilder den alfan. sexmach-hyllan: ingen synlig skillnad
  under Remix (skillnad inom brus). Graffitit (grumpos/tours/tenements) inte sett: vyerna hamnade utanför PVS.
- [x] tours: stadssilhuetten i skyboxen (2026-10-25, ny A/B mot originalet: sky0 och fyra vyer 40° uppåt från
  758 735 946): skyboxen `blue3` med staden, det gröna skenet och ACORP-tornet syns under Remix som i originalet.
  Troligen löst av 5640072 (HD-paketets nya himmelshashar i `rtx.skyBoxTextures`); de nuvarande filernas hashar
  finns där, `hd_sky.usda` matchar bara de gamla.
- [x] tours: DETTACORP-tornets fönsterljus (2026-10-25) är modeller (`ob_newbuild4`, texturer `objects/newbuild4`/`newbuild4a`,
  ritade som vanliga modeller) och lyste inte under Remix. `maps/model_emission.tsv`: fönsterremsorna 0,5, skylten 1.
  Fönstren och DETTACORP-skylten lyser som i originalet; bilden blir 0,2 EV ljusare än förut (sky0 -0,48 → -0,70).
  1 på fönstren lyste upp trumman bredvid vit. SENETECH/DETTATECH-skyltar, ljusrör, `glowindow1` och `newbuild7`
  provades också (bilden -1,0 EV, trumman vit) och togs bort.
- [x] bricksd (2026-10-23): neonskyltarna (FIGHTING/TRAINING/BOXING) är modeller (`ob_whacksign1-5`, entity.dat
  lighting 0) som i originalet lyser av sin egen ljusa textur; under Remix +3,2 EV för mörka. Emission 1 från egen
  textur (`maps/model_emission.tsv`): skyltarna -0,2 EV (2: -0,65 och urblekta). Väggen runt dem blir ljusare
  (-1,0 EV mot -0,57), banans exponering kan behöva justeras.
- [x] bricksd exponering (2026-10-24): bias -2,0 -> -2,4 (tre vyer -0,32..-0,54 -> -0,06..-0,21 EV,
  docs/exposure-match.md).
- [x] bricksd (2026-10-24): den höga cyanfärgade energipelaren i schaktet (vy `bricksd spot2 300 -1776 107 10
  67.5`) är additiva effektnät (SRC_ALPHA, ONE) som Remix ritar nästan osynligt svaga (+2,6 EV). Fix:
  `[rtxconf.bricksd] rtx.enableEmissiveBlendEmissiveOverride = True`, intensitet 2,5 (+0,13 EV, övriga vyer
  oförändrade). Ett av lagren använder Time Minders reflektionstextur `npcs/minderef` (0x62F8D2EF6E35D3AF), som
  står i `rtx.ignoreTextures`; utan den posten ritades Time Minder i rowdys blåvit (originalet: beige; Remix med
  posten kvar inte fotograferad), så den får stå kvar, pelaren lyser ändå.
- [x] mmuseum (2026-10-23): de vita "fönstren" är ljuspaneler med `bricks/color10` (enfärgad blå 52,67,111,
  ljusvärde 2500 -> emission 15, utbränt vitt). Intensitet 1 (`maps/emissive_intensity.tsv`): blå, i balans med
  resten av bilden (-0,11 EV relativt). Banan saknar `sky`-nyckel (30 banor gör det); dess himmelsytor ritas med
  en kvarlämnad textur, men de syns inte här (en `sky = NAMN` per bana via R_SetSky i QindieGL provades och togs bort).
- [x] mmuseum (2026-10-24): exponeringen -1,1 -> -1,5 efter fem vyer till (median -0,34 -> 0,00 EV,
  docs/exposure-match.md). Takvyn (sky1) är kvar -2,1 EV: en taklampas hotspot, ljussättning och inte exponering.
- [x] crevicelanding (2026-10-22): det landade skeppet (`ob_shuttlewhol6`) var nästan oupplyst under Remix. Det har
  entity.dat lighting = 1, dvs. renderfx 0x800 (`RF_DIRLIGHT`, modelljus som figurerna, inte fullbright) men får
  inget fyllnadsljus (bara figurer nära kameran). Emission från egen textur, 0,5 (`maps/model_emission.tsv`,
  emissive.usda): vy 1 +2,0 → -0,23 EV, vy 4 -0,63. `rtx.worldSpaceUiTextures` gjorde skeppet platt och ~1 EV för ljust.
- [ ] Rekvisita med modelljus (`RF_DIRLIGHT`, entity.dat lighting 1, ej figurer): 54 placerade typer, 372 platser;
  24 vyer från startens PVS (`find_views.py --entity`, 2026-10-22). Avvikande: starports bakgrundshus (ob_s_building-*)
  nästan svarta, men bilden domineras av Numos-himlen som ersätter stadsskyboxen (+2,4 EV); emission 0,5 hjälpte
  knappt och samma texturer finns på sunstrip (bias -4,3), så ingen intensitet satt. Skeppen i chamber/warshipbay och
  sendernet ser ut som originalet.
- [x] `func_fog` (lokala färgade dimvolymer, 12 banor: onegate 13, fortress2 9, hephfactory 7, pay2pray/vendomart/bricksd
  5, temple 4 …), 2026-10-23: ref_gl ritar volymerna otexturerade (GL_POLYGON, färg per hörn med alfagradient genom
  lådan, blend SRC_ALPHA/ONE, ingen djupskrivning), samma sort som commbase-strålarna; Remix gjorde dem svarta.
  QindieGL #33 `untexturedadditive = 1` (på för Anachronox): lådan runt bönekapseln i pay2pray blir genomskinlig och
  kapseln syns, temples svarta paneler försvinner. Originalets blå sken saknas fortfarande.
- [x] func_fog-skenet i pay2pray (2026-10-24): QindieGL #34 ger den färgade texturen texturkoordinater; utan dem
  behandlade Remix ritanropen som otexturerade och emissive blend override verkade inte. `[rtxconf.pay2pray]`
  override på, intensitet 8: bönekapseln lyser blått som i originalet (kapselvy +2,10 → +1,75 EV, resten är väggarna).
- [x] func_fog på övriga banor (2026-10-24): vyer nås med `set debug 1;goto X Y Z` (gamex86, flyttar spelaren så att
  dimman hamnar i PVS) och rigcam. Override intensitet 8 på onegate, temple, vendomart, fortressgrounds, hephfactory,
  20 på hive: skenet syns (onegate fog0 +4,34 → +0,83 EV; hive röda dis saknades, 8 ger +1,92, 20 ger +0,95). QindieGL #35: färgcachen
  (16 färger, aldrig tömd) fylldes av labbuildings slumpfärgseffekt och gjorde senare banors dimlådor svarta igen.
- [x] fortress2 func_fog (2026-10-25): originalvyerna gick att ta (fortress2 laddad som första bana); originalet har
  vita genomskinliga ljusschakt vid robotarna (func_fog 1 1 1), Remix utan override inga, override 8 ger dem. På.
- [ ] func_fog kvar: labbuilding (ingen skillnad med override).
- [x] hephfactory/fortressgrounds "2,5–3 EV för mörka" (2026-10-25): vyerna fylldes av dimman, så autoexponeringen
  jämnade ut. På avstånd (find_views --entity func_fog 450) ser fortressgrounds turkosa låda ut som originalet vid 8
  (30 bleker den); hephfactorys pelare ändras inte med intensiteten (+2,67/+2,52 EV). Originalets gula ton är
  additiv blandning som klipps per kanal (0,7 0,4 0 staplas mot gulvitt); Remix klipper inte, pelaren förblir orange.
- [ ] hephfactory: vid den orangea dimvolymen *63 (kamera -142 2449 -160, yaw 45) visar originalet scenen, Remix en
  jämn grå bild (även med polyblend-fixen). gl_log under Remix vid 20 2612 -160: ingen värld ritad, bara en svart
  polyblend-kvadrat. Inte återskapat efter ny banladdning + direkt goto (-185 2407 -176): världen ritas, scenen syns
  (2026-10-25). De gråa bilderna kom när spelaren flyttats in i/förbi dimvolymer med goto (spelarens punkt i ett
  blad med dimvolymens innehåll 0x8010000); troligen motorns läge "spelaren i dimma", inte Remix. Kolla i vanligt
  spel om man kan gå in i *63 (94×71×94 vid golvet) och vad som syns då.
- [x] R_PolyBlend (helskärmsfärg: skadeblink, undervatten, `setblend`-fades, intoningen vid varje banstart),
  2026-10-25: Remix ritade kvadraten framför kameran som en grå ogenomskinlig skiva oavsett färg/alfa. QindieGL #36
  `polyblendoverlay = 1` ritar den som UI-överlägg med en egen 2×2 vit textur, hash `0x722A202F07A4B313` i
  `rtx.uiTextures`. temple med setblend röd/svart/vit: samma ton som originalet.
- [x] Modelltexturerna med mellanslag i namnet (2026-10-25, 28 st. i MODELS.dat): 26 finns redan som 4x-versioner från
  Graphical Enhancements 0.3 (lösa filer i `anoxdata/models`, spelet laddar dem), så de är HD utan models_hd.usda.
  De två utan (`objects/banners copy.tga`, `banners copy1.tga`) används inte av någon md2 eller entity.dat.
- [x] Himmel commbase/commiteon (2026-10-21): skyboxen ritades men autoexponeringen anpassade sig till den soliga marken,
  så himlen blev 4–7 EV för mörk. `rtx.skyBrightness = 140`, bias -0,2 och dimma av (turkos dimma färgade marken).
  Bild median +0,03 EV, himmel +0,2–0,9 EV.
- [x] Andra utomhusbanor med skybox (2026-10-22): uppåtvyer på 24 banor. whitendon hade samma mörka himmel
  (`skyBrightness = 100`, bias -4,0, median -0,3 EV); waukees bias -0,4. Övriga utan himmelsfel.
- [x] hephaestus/fortressgrounds (2026-10-22): hephaestus bias -2,0 (startvy +0,13, vyer median -0,7);
  fortressgrounds oförändrad (startvy -0,04, bara den vita helikopterplattan mörkare).
- [x] commbase: de gula laserstrålarna (från `ob_lasersentinel`, otexturerade GL_QUAD_STRIP, blend SRC_ALPHA/ONE,
  färg ffcc00) var mörka/grå under Remix. Löst 2026-10-24: QindieGL #34 (texturkoordinater för den färgade texturen)
  plus `[rtxconf.commbase]` override på, intensitet 150 (solbelyst bana, låg exponering; 4 gav inget, 40 orange och
  svagt). Strålarna gula som i originalet, något mer orange; bildens EV oförändrad (+0,14).
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
