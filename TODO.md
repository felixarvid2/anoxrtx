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
  ett ljus som tänds under spel, paus och save-återställning. Lampytans emission följer en tändning och en
  sparladdning (tours, punkt 5); själva Remix-ljuset mättes inte där.
- [x] **4. BSP/PVS:** mätt med riggkamera och `--ab-cfg "set r_novis 1"` (docs/culling-check.md): ingen synlig
  skillnad i sex vyer, upp till 60 % längre bildtid i votowne. Spelets PVS behålls; prova `r_novis 1` per bana
  om ljusläckor eller saknade skuggor syns.
- [x] **5. Dynamisk emission:** synkronisera ett verifierat material med
  ljushändelser, utan kvarhängande tillstånd eller dubbel illumination.
  Första version 2026-10-27 (QindieGL #37 `styledemission`, `tools/emissive_styles.py`, installsteget `estyles`):
  lampytor vars ljuskarta har en ljusstil (dface styles, 118 ytor på 9 banor) ritas med en texturkopia som skiljer
  sig i en byte per nivå (faktor 0, 1/3, 2/3), och `emissive_styles.usda` ger kopiorna dämpad emission. fortress1
  (stil 11): taklamporna pulserar (takytan 45/41/39/43 över tio bilder, utan inställningen 44-45); spiralerna
  (`bricks/light1a`, emission 5) syns knappt ändras men byts (spiralerna sitter på func_wall: ytor på
  brush-entiteter matchar, även när de rör sig, eftersom QindieGL jämför modellkoordinaterna). Banbyte
  fortress1 → fortress2 fungerar. Tändning och sparladdning 2026-10-27 på tours (stil 32, ljuset `explosion`,
  START_OFF; QindieGL #39 loggar varje nivåbyte): lysröret `bricks2/dwlight2` är släckt vid start, tänds när
  spelaren (`goto`) går in i dess `trigger_multiple` (som växlar det av/på medan spelaren står kvar, spelets
  logik), är släckt efter en ny `map tours` och tänt efter `loadgame` av en sparning gjord med det tänt.
  Kartljuset (Remix-ljuset, inte emissionen) mätt 2026-10-28 i rummet runt ljuset (1280 -32 -80, 330), fyra vyer
  släckt/tänt: Remix +0,01..+0,26 EV, originalet +0,54..+1,44 EV. Ljuset tänds, men rummet är redan 2,0–3,9 EV för
  ljust släckt (se nedan: icke-ljusytor med lysande texturer), så tändningen syns knappt. Triggern sitter i taket
  (1239 228 -91, spelaren får inte plats); den löser bara ut via `goto` från en giltig plats (1280 -32 -100).
- [x] **Lysande texturer på vanliga ytor (2026-10-28):** `emissive.usda` gör en textur emissiv om någon yta i någon
  bana har SURF_LIGHT, och Remix-material gäller per textur. 295 texturer används både som ljus och som vanlig yta:
  183 000 vanliga ytor (91 banor) mot 50 000 ljusytor, t.ex. `baseanox/clear` 27 450/610, `bricks/empty` 21 692/16,
  `shuttle/sschrome` 11 058/427, `bricks/twall01` 3 210/22. I originalet lyser de bara via ljuskartan. Förslag: samma
  variantteknik som `styledemission`, per textur listas minoritetsytorna (~14 500 totalt) och får den andra
  varianten (emission av/på). Ändrar alla banors ljusnivå, så exponeringen per bana måste mätas om. Klart 2026-10-28 (QindieGL #41): vanliga ytor
  får stil 0 i `.estyles` (173 882 rader, 91 banor); bias omräknad för slounge, hephtower2, mystech2, scommons, tours
  (docs/exposure-match.md). Ingen prestandakostnad. slounge: rätt medelnivå men annan ljusfördelning än originalet.
- [ ] **6. PBR-klassificering:** vidareutveckla befintliga namnregler med
  dataregler, undantag, BSP-flaggor och osäkerhetsrapport; kan gå parallellt.
  2026-10-28: regler som data (`tools/pbr_rules.json`: klasser, ordnade nyckelord, undantag, haze_glass),
  `tools/pbr_classify.py` (BSP-användning: ytor/banor, SURF_LIGHT/TRANS-andel, brush-contents, animationsramar;
  rapport `pbr_report.md` med oklassade, svaga, konflikter och modellkällor), `pbr_layer.py` använder den.
  Utan Jev: oklassade 2683 -> 1700 av 3676 (nya klasser sign/light/organic; tidigare klassade oförändrade).
  Med Jev (som installeras): samma material som förut utom undantagen; 305 konflikter regel mot Jev listas.
  DeepSeek (`--deepseek`, bara text, ~0,09 USD) gav klass åt 159 av 1700 oklassade, sa "default" om resten,
  och hittade regelfel (thatch/hatch, curtainrods) som blev undantag; förslag används bara med `--ai`.
  Kvar: granska konflikterna (t.ex. `baseanox/clear`, `bricks/windowplain`), fler undantag, närbilder i spelet.
  2026-10-28: DeepSeek ser texturerna (`--deepseek-vision`, 5x5-kontaktark med 128 px-miniatyrer, `deepseek-flash`,
  ~0,12 USD för 780 texturer). Kalibrering 50/50 rätt (tydliga namn där regel och Jev är eniga). Överens med Jev
  78 % (slumpprov 143), 75 % (300 största oklassade), 46 % (305 konflikter regel mot Jev); med textläget 65 %.
  Egen granskning av kontaktarken: i konflikterna har bilden oftast rätt (`bricks2/bricksrock*` sten, inte metall;
  mattor/soffor/tält tyg; tavlor skylt), men sämre än Jev på t.ex. dörrar (`tensil/door02` blir tech, inte trä) och
  svarta/genomskinliga miniatyrer (`*/clear`). Därför: stark namnregel + bildsvar med hög säkerhet slår Jev
  (`rule+vision`, 68 texturer, konflikter 305 -> 237); installern använder cachen när den finns.
  Installerat 2026-10-28 (69 texturer ändrade inkl. undantag; normalkartor oförändrade): undantag `tensil/door02`/`door03`
  trä, `baltown/doorwall-101top` glas, `sunder/monitor-btm3` tech. A/B gammal/ny i spelet (13 vyer, 13 banor): högst
  1,6 % pixlar ändrade, inga krascher; skillnaden (roughness/metallic) syns knappt i vyerna.
  2026-10-28: installern: arbetskatalogen är nu `~/.cache/anoxrtx/work` (där `jev_classes.json` redan låg),
  `--maps DIR` för kartor extraherade på annat ställe (här `event-lighting-2026-10-18/maps`), steg som behöver
  kartor avbryter med fel i stället för att köra verktygen utan kartor, och `pbr`/`emissive` lägger själva till
  GE-hasharna (förut bara `mod`), så `install.sh pbr` ensamt ger ett komplett `pbr.usda`.
  2026-10-28: alla 237 konflikter granskade ([docs/pbr-conflict-review.md](docs/pbr-conflict-review.md)):
  `deepseek-flash` dömde från kontaktark (128 px) med regelns och Jevs klass och Geminis beskrivning (10 anrop,
  ~0,02 USD, cache `deepseek_conflicts.json`), sedan egen granskning av varje ark. 205 nya undantag (t.ex.
  `bricks/windowplain` glas, `commbase/compside-*` tech, `whitendon/in_rafter*` trä, `sunder/bardrink-*` skärm);
  konflikter 237 -> 31 (kvar: svarta `*/clear`, limbus-pelare, ballotine-pelare m.fl., listade i dokumentet).
  Undantag som bekräftar Jevs material behåller Jevs värden, så 67 texturer ändrar roughness/metallic mot main.
  Installerat 2026-10-28 (granskat lager, 63 texturer ändrade mot visionlagret). Närbilder med handplacerade vyer
  (goto + rigcam: tält på commiteon, säten på starport, pelare på fortress1, stol på whitendon) gamla/nya lagret:
  0-4 % pixlar ändrade, för att vyerna mest visar oförändrade varianter (`tent1-2`, `tent2-1`). Spegeltest (alla
  `commbase/tent*` metallic 1, roughness 0,02) ändrade 87-89 % av pixlarna: materialvärdena når Remix. Kontroll
  whitendon, starport, commiteon, senderss: ok, inga fel. Kvar: närbilder av `bricks/windowplain` och `*/clear`.
  Försök 2026-10-29 (`find_views.py` utan --pvs, goto 60 enheter bakom kameran, Remix + original): 8 vyer på
  bricksd, tenements, routubes1, mystech1, baltown, sunstrip, limbus gav mest svart, utanför världen eller fel plats;
  bara sunstrip `baseanox/clear` (vattenyta) syns lika i båda. Behöver handvalda vyer från spelarplatser/sparningar.
- [ ] **7. Ankarmeshar:** stabila författar-ID:n, per-karta-data, ersättnings-
  och resurslivscykel; statiska ankare först.
- [ ] **8. Dimma/miljötillstånd:** mjuka, verifierade övergångar och återgång
  till kartbaslinjen; ingen global Numos-himmel.
- [ ] **9. Väta/regn:** en utomhuskarta först, skydd inomhus, upptorkning,
  runtime-fallback och uppmätt prestanda.

## Befintligt som fortfarande behöver spelverifiering

- [ ] Utomhusbaslinje: HD-himmel och Numos sol-/skuggriktning på avsedda kartor.
  2026-10-26: Numos av på sunstrip, comhills, baltown (och starport): Numos tog bort sunstrips stadssiluett,
  comhills soliga ökenhimmel och baltowns lila skymning (vyer mot horisonten +1,6 till +2,7 EV). Banornas sol
  var avstängd (`sun_scale = 0`, Numos skulle ge solen); nu på igen. Solen var ~60x för svag: Remix sprider en
  distant lights strålning över solskivan (2°), så `_sun_light / 200` lyste knappt; global `sun_scale = 12`
  (2026-10-26). Riktningen (från solen in i scenen) var rätt: #92:s riktningsbyte byggde på brus och återställdes
  i #93, och de tester med sol x64/x256 som såg verkningslösa ut gjordes med omvänd riktning.
  comhills: dimfärg av (blå dimma färgade den solbelysta marken blå), `skyBrightness = 24`, bias -0,4: startvy
  -0,23, horisontvyer +0,4 till +1,3 (förr +1,2 till +1,8, svart terräng).
  Exponering: sunstrip -4,3 → -2,4, comhills -2,4 → -1,8, baltown -0,5 → -1,8; startvyer -0,09/+0,16/-0,02,
  baltown vyer -0,1 (med sol x12: startvy -0,62, vyer -0,12 till +0,16). sunstrips och starports vyer ändras inte
  av solen (vyerna ligger i skugga/inomhus). baltownr har kvar Numos (ej bedömd: vyerna hamnade inomhus).
- [x] baltownr Numos av (2026-10-27): på/av gav samma bild i alla fem vyer (EV skiljer högst 0,05), så Numos är
  nu av överallt och kartsolen på (`sun_scale = 0` borttagen).
- [x] baltownr startschaktet (2026-10-27): vyer rakt upp (344 -3850 1380, pitch -75) är 7 EV mörkare under Remix;
  originalet visar molnig natthimmel med måne (`balsun`) och solbelysta väggar. Förstärkt syns himmelsrutan som
  mörka radiella strimmor. Uteslutet: Numos, volymetrisk dimma (`enableFogRemap = False`), `skyBrightness = 8`,
  himmelstexturerna (alla sex balsun-hashar, original och GE, står i `rtx.skyBoxTextures`; HD-dds är hela) och
  riggkameran (den ersätter spelets vieworg, så himmelskuben ritas runt den). Det är kartans enda himmelsöppning.
  Orsak (capture 2026-10-27): schaktet ligger inne i en bergskulle, `ob_commhill02` (origin 314 -3464 387, offset
  -319 -317 232, skala 1,15 3,4 10,75, vinkel 255; 842 x 3032 x 1810 enheter, z 619-2429). ref_gl ser inte dess
  baksidor, Remix träffar insidan. Med kullens textur i `rtx.ignoreTextures` (0x6F93AEF4B3688C86) syns natthimlen,
  månen och de solbelysta väggarna som i originalet. Samma fel som tåget på starport. Fungerade inte:
  `rtx.enableCulling = True` (per karta och i rtx.conf) och en QindieGL-test som vände cull-riktningen; Remix
  culling tar inte bort insidan åt något håll. Texturen kan inte döljas (25 kullar på baltownr delar den), och
  meshhashen saknar positioner (`indices,texcoords,geometrydescriptor`), så alla kullar delar den också. Löst
  med QindieGL #38 `skipenclosingmodels = 25` (installern sätter det): en modell med baksidesgallring ritas inte
  när dess insida täcker minst 25 % av sfären runt kameran (vinkelsumma/winding number, behöver ingen entitet).
  Kullen täcker 86 % rakt upp i schaktet och hoppas över: natthimlen och månen syns (+8,45 → +2,94 EV, resten är
  exponeringen; väggar och golv är mörkare än originalet). Under kullens öppna botten (s0, z 404) är det 31 %
  enligt capture-meshen; de vågräta s0/s1-vyerna är oförändrade. rowdys oförändrad, ingen Remix-krasch.
  Kostnad (tillfälligt mätbygge): 0,03 ms/bildruta på baltownr, 0,09 rowdys, 0,14 starport (av ~18). Spelaren
  startar i schaktet; med kullen borta var startvyn +2,35 EV, nu +0,54 med ett fyllnadsljus
  (`maps/overrides/baltownr.override`, docs/exposure-match.md).
- [x] starport exponering (2026-10-28): utomhusgången var +3,2/+2,6 EV för mörk på spelarplatser (autoexponeringen
  jämnar ut ute/inne, originalet är ~4x ljusare ute). `evMin`/`evMaxValue` verkar inte när de sätts vid körning,
  `skyBrightness` 30/100 knappt; autoexponering av + bias 0: start +0,19, gången +0,45/+0,52, ljusgården -0,39.
- [x] starport kaféfönstret (2026-10-28): glaset (`braintrain/glass-1b`, emissivt på andra banor) genomskinligt sedan
  static-off; himlen bakom var grå av volymetrisk dimma: `enableFogRemap = False` på starport, kaféet +2,59 -> -0,55 EV.
- [x] tours-rummet (2026-10-29): stil 32 är 0,000 släckt och 1,000 tänt i både originalet och Remix (QindieGL #42
  loggar faktorn). Fläcken i originalet syns lika i tänt och släckt läge: ånga från `spew`-entiteterna under lampan,
  som originalet ritar självlysande. Löst 2026-10-29: `[rtxconf.tours] enableEmissiveBlendEmissiveOverride`,
  intensitet 2,5: rummets vyer släckt +1,52/+3,23 -> -0,12/+0,09 EV, startvyn -0,07 (10 blev för ljust, -0,88).
- [x] `spew`-ånga på andra banor (2026-10-29): basement, sphere3, sunstrip, limbus, hephtower1, hephpoor, onegatestn
  med och utan emissive blend-override (2,5) mot originalet: ingen vy ändrades mer än 0,13 EV, ingen bana fick den
  (docs/exposure-match.md).
- [ ] sunstrip: originalets vita ångdis över bassängen saknas i Remix (+1,9 EV). Undersökt 2026-10-29
  (QindieGL #43 `TraceBlendDraws`): partiklarna (`burst_04`, `magical_08`) når Remix som vanlig alfablandning
  (SRC_ALPHA/ONE_MINUS_SRC_ALPHA, ingen djupskrivning), inte additivt, och belyses av den mörka hallen. Ingen
  effekt av: dolda `_default` synlig, `particleSoftnessFactor = 0`, `magical_08` i `particleTextures`; fog remap gav
  mörk dimma. Nästa: göra `burst_04`/`magical_08` självlysande i mod-lagret och kolla andra banor (docs/exposure-match.md).
- [x] baltownr uppåtvyn (2026-10-28): autoexponering av, bias -0,5: uppåt +3,05 -> +0,72 EV, median -0,24.
- [x] ballotine/kraptonmaze "svart bild" (2026-10-28): anoxcheck läste gamla rader i QindieGL.log och väntade inte;
  rättat, plus omtag av svart första bild. ballotine bias -1,5 (+0,07 EV).
- [ ] Bakat ljus utan Remix-ljus (2026-10-28, `tools/baked_light_gaps.py`, docs/baked-light-gaps.md): ljuskartan mot
  uppskattat direktljus i Remix på alla 98 banor; kandidater (otestade) utanför repot. slounge-hytten: lampytan
  `celight2` släcks av en stil 0-rad i `.estyles` (lampans ovansida 2 enheter bort, QindieGL matchar inom 2), samma
  krock släcker 108 ljusytor på 13 banor; rätta i `emissive_styles.py`. tours-fläcken ligger i stil 32-blocket
  (släckt läge är inte 0 i originalet). Krocken rättad 2026-10-28 (`emissive_styles.py` hoppar över stil 0-rader nära
  ostilade ljusytor, 123 rader): slounge/vendomart bias -3,2/-3,6, -0,14/-0,05 EV. votowne, sexmach och fortress2 testade
  2026-10-29 med goto: kandidatljusen ändrar inget märkbart (autoexponering, saknad studs), inga behålls.
- [x] slounge ljusfördelning (2026-10-28): lampytan var släckt av en `.estyles`-krock, inte en ljusmodellsskillnad.
- [x] Dimma bakom glas (2026-10-28): vyer genom genomskinliga ytor mot himlen på 72 dimbanor; dimma av på sunstrip,
  fortressgrounds, fortress2 (sunstrip start +2,14 -> -0,29 EV). starport-ljusgården: -1,1 EV var ett mätfel
  (konsolen låg över originalbilden). Ny mätning 2026-10-29 utan konsol: start -0,15, ljusgård -0,26, gången
  +0,23/-0,25; bara kaféet -1,7 (solbelysta husmodeller bakom glaset). Himmel 0,5 / sol 8 flyttar kaféet 0,4 EV men
  gången lika mycket åt andra hållet: inställningarna behålls.
- [x] baltownr exponering (2026-10-27): de nedre nivåerna var 1,5 EV för ljusa (median av 8 vyer); bias -3,8 och
  slemgolvet `ballotine/slime01a` intensitet 2 (docs/exposure-match.md), efter: median -0,07 EV (-1,7 till +1,3). Kvar: s1_1 längs slemkorridoren -1,7.
- [x] fortress2 blå ton (2026-10-27): originalets cyanfärgade dörrparti (färg/luminans 0,82 1,05 1,02) motsvarar exakt
  de närmaste lamporna (`_color` 0,79 1 1); Remix blandar in mer neutralt ljus (0,96 1,01 0,98). Panelernas emission
  (`naude-blue-5`) 15/60/240 och de två vita lamporna släckta ändrade inget. Över 89 A/B-par är Remix inte
  systematiskt varmare (blått, median +0,026); fortress2 (+0,08) ligger inom spridningen. Ingen ändring.
- [ ] Vatten: genomskinlighet, stabil geometrihash och material i relevant vy.
  2026-10-26 (`find_views.py` vattentexturer, `--ab-original`): greattree-sjön (`waukees/h2002`, warp utan TRANS,
  alltså opak i originalet) blev nästan svart med mörka fläckar som genomskinligt vatten; nu opak blank yta
  (`WATER_OPAQUE` i make_layers.py, grovhet 0,1): ser ut som originalet (bild +2,5 → +1,0 EV). fortress1-poolen
  (genomskinlig) ser bra ut. hovel `bricks2/brownwater` (TRANS33) är klarare än originalets bruna lager;
  `transmittance_measurement_distance` 64 → 8 syntes inte, oförändrad. Kvar: limbus, senderss, tensil, sunstrip,
  starport har vatten utanför startens PVS (rigkameran ser inget där, också med nya `find_views.py --pvs`), behöver
  sparfiler. Geometrihashen: `geometryAssetHashRuleString` innehåller texcoords, som warp-ytor räknar om varje
  bildruta; inget flimmer sett (settle 0,0–0,06), så ingen ändring.
- [x] Lava: `proc_lava` fryses (256x256, hash 0x561447B2DFA181FD) och ersättningsmaterialet syns i levant2 (2026-10-18). Orsak: HD-paketets uppskalade palett (anoxgfx kräver 256 px bred) + QindieGL fyllde gammal D3D-textur. `proc_lavafloe` ej sedd i bild än. levant1 och hephlava går inte att se med riggkameran (banstarten ritar ingen värld, även originalet svart, 2026-10-19); kräver en sparfil nära lavan.
- [x] Figurer för mörka: fyllnadsljus per figur relativt kartljusen (QindieGL #30/#32, `model_fill = 1.5` + egna värden
  för 5 banor), 10 banor inom ±0,3 EV mot originalet (2026-10-19). Övriga 69 banor mätta 2026-10-22: 60 användbara,
  37 fick egna värden (0,1–6) i två varv; 49 av 60 nu inom ±0,35 EV.
- [x] Figurer för ljusa även vid `model_fill = 0.1` (rummets ljus räcker): tensil -0,9, bricksd -0,66, hephfactory
  -0,58, sendormitory -0,56, waukees -0,5, franks -0,48, levant1 -0,44 EV. Orsak: Remix dielektriska spekulära lob
  (F0 0,04) på legacy-material, som originalets diffusa modellskuggning saknar (hörnfärg och albedo per bana
  provade 2026-10-25 utan effekt). Löst 2026-10-26 per bana: `rtx.legacyMaterial.metallicConstant = 0.5`,
  `roughnessConstant = 1` i `[rtxconf.<bana>]` för de sju banorna; nu -0,23 till +0,23 EV. Globalt metallic 1
  (planen från 2026-10-25) gjorde figurerna 0,8–1,5 EV för mörka på nästan alla 71 banor (den tidigare mätningen
  saknade sRGB/gamma-hanteringen i `ab_ev.py`), så det rullades inte ut. docs/exposure-match.md
- [x] fortressgrounds/grumpos: figurerna +0,6/+0,9 EV för mörka. Fyllnadsljuset verkar, men bara ~0,2 EV per
  fördubbling (ljusa ytor framför Boots, autoexponeringen tar tillbaka en del); `model_fill = 32` ger -0,35/+0,18
  EV, fortressgrounds exponering -2,9 → -2,6 (2026-10-26).
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
- [x] labbuilding: en lampa rakt ovanför en figur i trappan bränner ut den (-1,2 EV mot bilden), oberoende av
  `model_fill` (2026-10-25). Figuren är spelaren vid `info_player_start` (-2034 1697 296), lampan är ljus 191
  (66 enheter ovanför). Med nuvarande installation (QindieGL #36, polyblend-overlay) är figuren inte utbränd.
  `191 scale 0.5`/`0.25` ändrar bilden knappt (0,1–0,25 EV); skenet kommer från lampans emissiva textur, inte
  ljuset. Ingen override behövs. Lampans glas är ljusare än originalets (känd begränsning, emissiv).
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
  24 vyer från startens PVS (`find_views.py --entity`, 2026-10-22). starports bakgrundshus (ob_s_building-*) var
  nästan svarta och Numos-himlen ersatte stadsskyboxen. Löst 2026-10-26: Numos av på starport (stadssiluetten
  tillbaka) och emission 1 på husens 29 texturer (`maps/model_emission.tsv`, background/*): husen ljusa som i
  originalet. Samma hus finns på sunstrip, labbuilding, servicetunnel, braintrain-b, cine1; startvyerna oförändrade. Skeppen i chamber/warshipbay och
  sendernet ser ut som originalet. Två starport-vyer (ob_s_building-3_0, -14b_3) var helt svarta, också himlen:
  kameran står i luften inuti `ob_btrain` (skala 16,2, ~2700x830x650 enheter), som originalet inte ser inifrån
  (baksidor bortplockade). Med tågets texturer i `rtx.ignoreTextures` syns staden (ljusstyrka 11-13 → 53),
  2026-10-26. Ett testvalsfel, inte ett spelfel; `find_views.py` kollar bara BSP:n. 2026-10-27 i Blender (frame 0
  exporterad till OBJ med entitetens origin, angle och skala; `offset` används inte): tåget står still (fem
  översiktsbilder i följd identiska) och renderingen stämmer med originalet och Remix. 3_0 ligger inuti skrovet;
  14b_3 ligger inom tågets låda men strax utanför frame 0-skrovet, ändå svart i Remix och utan tåg i originalet.
  Ett automatiskt modelltest i find_views är därför inte pålitligt. Löst 2026-10-27 med QindieGL #38
  `skipenclosingmodels`: tåget (582 trianglar) ritas inte i de två vyerna och staden syns (fortfarande +2,8 EV,
  exponering).
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
- [x] func_fog labbuilding (2026-10-25): enda volymen (*74, vit, 48×48×36 vid -2728 3288 426) är projektorkäglan över
  hologrambordet (kamera -2508 3288 474 pitch 6,2 yaw 180, goto -2398 3288 458). Originalet visar ett ljust dis i käglan. Under Remix
  syns den knappt; override 20/40 gör den svagt synlig men bleker hologramemblemet (brunt i originalet) till vitrött,
  eftersom emblemet också ritas additivt. Övriga vyer oförändrade. Override av: emblemet väger tyngre än diset.
- [x] hephfactory/fortressgrounds "2,5–3 EV för mörka" (2026-10-25): vyerna fylldes av dimman, så autoexponeringen
  jämnade ut. På avstånd (find_views --entity func_fog 450) ser fortressgrounds turkosa låda ut som originalet vid 8
  (30 bleker den); hephfactorys pelare ändras inte med intensiteten (+2,67/+2,52 EV). Originalets gula ton är
  additiv blandning som klipps per kanal (0,7 0,4 0 staplas mot gulvitt); Remix klipper inte, pelaren förblir orange.
- [x] hephfactory: vid den orangea dimvolymen *63 (kamera -142 2449 -160, yaw 45) visar originalet scenen, Remix en
  jämn grå bild (även med polyblend-fixen). gl_log under Remix vid 20 2612 -160: ingen värld ritad, bara en svart
  polyblend-kvadrat. Inte återskapat efter ny banladdning + direkt goto (-185 2407 -176): världen ritas, scenen syns
  (2026-10-25). De gråa bilderna kom när spelaren flyttats in i/förbi dimvolymer med goto (spelarens punkt i ett
  blad med dimvolymens innehåll 0x8010000); troligen motorns läge "spelaren i dimma", inte Remix. Kolla i vanligt
  spel om man kan gå in i *63 (94×71×94 vid golvet) och vad som syns då.
  Kontrollerat 2026-10-25: *63 är mynningen till en låg gång norrut (golv -255, tak -161, väggar x 129/223), samma
  golv som rummet söderut. Spelaren gick in från goto 176 2620 -230 med `w` genom dimman till gångens slut och
  tillbaka med `s`: Remix och originalet visar scenen i alla bilder, ingen grå bild. Inget att åtgärda.
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
