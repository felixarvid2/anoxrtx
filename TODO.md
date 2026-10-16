# Att göra: förbättra RTX Remix för Anachronox

Läget och tidigare resultat finns i [RESULTS.md](RESULTS.md), planen i [PLAN.md](PLAN.md).
Ordnat ungefär efter nytta. ✅ = klart, 🔶 = gjort men inte sett i spelet.

## 1. Verifiera det som redan är byggt
- [ ] 🔶 **HD-himlar** (`hd_sky.usda`): titta i en bana med ljus himmel (t.ex. Sunder, `sunder2`, eller banor
      med `blue`/`outside`/`forest`). Introt visar bara stjärnhimlar.
- [ ] 🔶 **Vätskematerial** (`liquids.usda`): Limbus (vatten), Levant (lava), Hive/Krapton (kristaller/glöd),
      Ballotine (slem). Justera IOR, `transmittance_measurement_distance` och glödstyrka efter vad som syns.
- [ ] 🔶 **Flashblend-ljus** (QindieGL PR #6): testa i en strid/explosion med `gl_flashblend 1`, merga om det fungerar.
- [ ] **Kartljus i fler banor**: hittills bara jämfört i Rowdy's. Gå igenom några olika miljöer och justera
      `maplights_scale` (eventuellt en skala per bana).
- [ ] **Testriggen**: fler fasta testplatser. Spara spel vid TimeMinders och lägg till ett riggkommando som
      laddar en sparfil, så att senare banor går att testa automatiskt.

## 2. Ljus
- [ ] **Kalibrera tumregeln för `cap`/`falloff`/`_cone`** mot banornas egna ljuskartor: BSP-filerna har
      ljuskartorna kvar, så ljusstyrka nära varje ljus kan mätas och jämföras med Remix-bilden.
- [ ] **Ljusstilar och tändbara ljus**: ljus med `style`/`targetname` blinkar eller tänds och släcks i spelet,
      men är statiska i Remix nu.
- [ ] **Lampobjekt** (`ob_streetlight1`, `ob_light-1`, `ob_spotlight`, `ob_volight`, `cine_spotlight` …):
      har egna positioner men räknas inte som ljus än.
- [ ] **Självlysande ytor** (`SURF_LIGHT`, t.ex. `bricks/lightstrip1(450)`): gör dem till emissiva
      Remix-material via `remixhash.py`, så att lysrör och skyltar lyser upp omgivningen.
- [ ] **Dimma**: 72 banor har `fog` i `worldspawn`; se till att Remix-dimman (`rtx.enableFog`,
      volumetrik) matchar.
- [ ] **Sol/himmelsljus** för utomhusbanor (riktat ljus per bana).
- [ ] **De två `proc_lava*`-texturerna** genereras medan spelet kör: hasha dem med `DumpTextures` i Levant
      och lägg till i `liquids.usda`.

## 3. Material och texturer
- [ ] **Uppskala banornas texturer** (TEXTURES.dat) och lägg dem som Remix-ersättningar via hash,
      på samma sätt som himlarna. Undvik eller specialbehandla texturer med fina detaljer (som stjärnor).
- [ ] **PBR-material**: roughness-, normal- och metal-kartor för de vanligaste texturerna, t.ex.
      genererade med ett verktyg och finjusterade för hand.
- [ ] **Figurmaterial**: med `smoothnormals` behövs inte längre maxad roughness/metalness på figurer
      för att dölja kantigheten; gör om de materialen i `mod.usda`.
- [ ] **UI och intro**: lägg logotyper/menyer som saknas i `rtx.uiTextures` (hashar från `DumpTextures`),
      så att det överexponerade introt och menyerna ritas som vanligt.
- [ ] **Partiklar och strålar** (`rtx.particleTextures`, `rtx.beamTextures`): komplettera listorna med dumpen.

## 4. Geometri
- [ ] **Vatten**: kontrollera att vattenytornas geometrihash är stabil (spelet varpar vattnet), och att
      genomskinligheten inte bryts av det.
- [ ] **Dörrar och andra brush-entiteter** får också genererade normaler av `smoothnormals`: kontrollera att
      det ser rätt ut.
- [ ] **Himmelsdetektering**: kontrollera i Remix debug-vy att himlen klassas rätt i alla banor (nu 103 hashar).

## 5. Bild och prestanda
- [ ] **Rätt bildformat**: svarta kanter (4:3) i stället för utsträckt bild i `BorderlessFullscreen`.
- [ ] **Högre renderupplösning**: låt Remix rendera i skärmens upplösning i stället för spelets 640×480.
- [ ] **DLSS under Proton**: NGX laddas inte nu (`PROTON_ENABLE_NGX_UPDATER=1`, `PROTON_ENABLE_NVAPI=1`).
- [ ] **Neural Radiance Cache** startar inte under Wine; undersök eller stäng av inställningarna för den.
- [ ] **Mät FPS** på testplatserna och justera `rtx.graphicsPreset`, antal studsar m.m.

## 6. Teknik och underhåll
- [ ] **Remix-input under Wine**: riktiga tangenter fungerar (Alt+X), men syntetiska (XTest) når inte Remix.
      Löses detta kan riggen göra fångster automatiskt.
- [ ] **Windows-bygget av QindieGL**: alla ändringar är bara byggda med llvm-mingw; bygg och testa med MSVC.
- [ ] **Skicka ändringar uppströms** till whisperglen/QindieGL (Linux-bygget, `BorderlessFullscreen`,
      `smoothnormals`, `maplights`, `DumpTextures`) och vinevi1/anoxrtx (Linux-fixarna i `rtx.conf`).
- [ ] **Paketering**: ett skript som installerar allt (QindieGL-DLL, Remix, `.trex`-config, `rtx.conf`,
      kartljus, uppskalade himlar/vätskor) och sätter Steams startalternativ.
- [ ] **Nya Remix-versioner**: kontrollera Linux-fixarna (`rtx.dlfg.enable`, `rtx.useNewGuiInputMethod`) och
      hashregeln vid varje uppdatering.

## Redan klart
- ✅ QindieGL byggs på Linux (llvm-mingw), per-spel-hookar portade.
- ✅ Remix fungerar under Proton (frame generation av, ny GUI-input av, present-semaforen av).
- ✅ Kantlös helskärm (`BorderlessFullscreen`).
- ✅ Mjuka normaler på figurer (`smoothnormals`).
- ✅ Stabila geometrihashar för figurer (`rtx.geometryAssetHashRuleString`).
- ✅ Kartljus ur banfilerna via Remix API (`maplights`), med spotljus.
- ✅ Remix texturhashar utan fångst (`DumpTextures`, `tools/remixhash.py`).
- ✅ Verktyg: `adat.py`, `bspinfo.py`, `bsp2lights.py`, `make_layers.py`, testriggen `anoxrig.py`.
