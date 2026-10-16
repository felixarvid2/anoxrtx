# Plan framåt: RTX Remix för Anachronox

Den här planen bygger på det vi fått att fungera hittills (Linux, GE-Proton, QindieGL-bygget) och på
idéerna i [IDEAS.md](IDEAS.md). Den är ordnad så att varje fas går att testa innan nästa börjar.

## Läget i dag

**Fungerar**
- QindieGL byggs på Linux (llvm-mingw) med samma 385 exporter som originalet, inklusive per-spel-hookarna.
- RTX Remix 1.5.2 (release) körs under GE-Proton 11-9 med ett RTX 5060. Introt path-tracas och Remix
  hittar kameran.
- Fixar som krävs på Linux finns i `rtx.conf` och README:
  - `rtx.dlfg.enable = False` och `rtx.dlfg.enablePresentMetering = False` (annars hänger Remix i Present).
  - `rtx.useNewGuiInputMethod = False` (annars täcks spelet av ett vitt overlay-fönster).
  - `presentSemaphoreEnabled = False` i `.trex/bridge.conf`.
- Helskärm som fyller skärmen via QindieGL:s nya `BorderlessFullscreen = 1`.

**Kända problem**
| Problem | Orsak (känd eller trolig) | Åtgärd |
|---|---|---|
| Musklick hamnar fel i helskärm | Fönstret är 1920×1200 men spelet räknar i 640×480 | Fix skriven (gren `borderless-mouse` i QindieGL), **inte testad i spelet än** |
| Bilden är utsträckt 4:3 → 16:10 | Backbuffern sträcks till hela fönstret | Fas 5: svarta kanter (pillarbox) |
| Introt är överexponerat (vita logotyper) | Självlysande/additiv geometri utan ljus | Fas 1 |
| Banor utan egna Remix-ljus blir mörka | `rtx.fallbackLightMode = 0`, modden har bara ljus där bilderna togs | Fas 2 |
| `+map` vid start hänger på "One moment......" med Remix | Okänt; utan Remix ignoreras `+map` helt | Undvik, ladda sparade spel via menyn |
| DLSS laddas inte | NGX hittas inte under Wine | Fas 5 |
| Neural Radiance Cache startar inte | Fel vid kontroll av GPU-funktioner under Wine | Remix faller tillbaka själv; bevaka |
| Spelet pausar (svart) när fönstret saknar fokus | Normalt Quake 2-beteende | Testriggen måste ge fönstret fokus |

## Fas 0: Grund och testrigg (först)

Mål: kunna testa ändringar automatiskt och jämföra bilder, utan att störa skrivbordet.

1. **Testa musfixen** (`borderless-mouse`): klicka i menyn, ladda ett sparat spel, prova muslook.
   Fungerar den: merga. Krockar den med Remix egen fönsterhantering (bryggan varnade för
   `WndProc::set` utan `unset`): byt till att bara hooka `GetCursorPos`/`SetCursorPos`/`ClipCursor` och
   skippa subclassen.
2. **Nästlad testsession som standard**: `Xwayland :7 -geometry 1920x1200 -decorate` och `DISPLAY=:7`
   i startalternativet. Där har spelet alltid fokus, och en krasch tar bara med sig det fönstret.
3. **Skript för test** (finns i grova drag): starta, vänta på `Camera cut` i Remix-loggen, läs spelfönstret
   med python-xlib, klicka med XTest i spelets koordinater. Bygg ut till:
   - `load-save <nr>`: menyklick Restore Universe → välj sparfil;
   - `shot <namn>`: bild + medelljus + Remix-loggens felrader;
   - `compare A B`: två bilder sida vid sida.
4. **Fasta testplatser**: 3–4 sparfiler på olika miljöer (inomhus Bricks, utomhus, en bana med vatten, en
   med mycket partiklar). Samma vy varje gång gör att ändringar går att jämföra rättvist.
5. Spara testskripten i repot (`tools/`), så att de går att köra igen.

## Fas 1: Snabba konfig-vinster (bara inställningar)

Testa en ändring i taget på testplatserna, behåll det som blir bättre (se IDEAS.md avsnitt 1):
1. `[game.anox]` i QindieGL.ini: `orthoskipuntextureddraws = 1`, `depthOffDisablesWrites = 1`
   (samma som Quake 2- och Heretic 2-profilerna).
2. Spelvariabler (finns i Anachronox, kontrollerat): `r_novis 1`, `gl_dynamic 0`, `gl_flashblend 0`,
   `gl_polyblend 0`, prova `gl_lightmap`/`gl_monolightmap`, och Anachronox egna `cl_distancecull`,
   `cl_noheadcull`, `cl_weathercull` (avstängd culling ger stabilare path tracing).
3. `rtx.conf`: `rtx.suppressLightKeeping`, `rtx.viewModel.enable`, `rtx.skyAutoDetect`,
   `rtx.sceneScale` (Quake-enheter är små), exponering (`rtx.autoExposure.evMinValue`).
4. Intro/meny: lägg logotyp- och menytexturer i `rtx.uiTextures` så att de inte path-tracas.

Klart när: menyer och intro ser ut som originalet, och testplatserna inte flimrar eller tappar geometri.

## Fas 2: Ljus (störst synlig skillnad)

1. **Tillfälligt ljus överallt**: prova `rtx.fallbackLightMode` (distant/ambient), så att banor utan
   handgjorda ljus syns alls. Ger en grund att bygga vidare på.
2. **Spelets dynamiska ljus som Remix-ljus**: QindieGL har redan `remixapi` och `qdx_light_add()`.
   Hitta ref_gl:s dlight-funktion i Anachronox (mönster/offset i `[game.anox]`, som för FAKK2) och skicka
   varje dlight som ett Remix-ljus. Kräver `exposeRemixApi = True` i `.trex/bridge.conf`.
   Ger explosioner, vapenblixtar och skriptade ljus.
3. **Ljus från banornas egna ljuskällor**: om BSP-filerna har kvar sina `light`-entiteter kan ett skript
   läsa ut dem och skriva Remix-ljus i `mod.usda` per bana: ett automatiskt första utkast för alla 97 banor
   i stället för handplacering. Inte kontrollerat än: `MAPS.dat` är komprimerad och måste packas upp först.

Klart när: alla testplatser är rimligt upplysta utan att varje ljus är handplacerat.

## Fas 3: Geometri och modeller (QindieGL)

1. **Stabila hashar** för världens ytor: statiska ytor i fasta vertexbuffrar (som QuakeRTX), så att utbytta
   material och meshar fastnar varje gång. Mät först: logga hur ofta samma vägg byter hash.
2. **Mjuka normaler på figurer**: beräkna per-vertex-normaler i QindieGL för entitetsritning (Heretic 2-
   koden finns som förebild). Gör sedan om modden utan max-roughness/metalness-tricket på figurer.
   Görs **innan** mer innehåll skapas, eftersom normalerna ändrar hasharna.
3. **Himmel**: kontrollera i Remix debug-vy att himlen klassas rätt på alla testplatser; annars rita om den
   som riktig skybox.
4. **Kamera i filmsekvenser**: Anachronox har eget filmkamerasystem; logga kameraklipp i cutscenes och
   bygg ut kamerauppfattningen om den tappar.

## Fas 4: Innehåll

1. Material/texturer per område, med ett `mod.usda`-lager per bana så att arbetet kan delas upp
   (som Quake 3-remastern, 27 banor).
2. Vatten: fasta UV + Remix-vattenmaterial i stället för spelets vertexvarpning.
3. Partiklar: gå igenom `rtx.particleTextures`/`rtx.beamTextures`, låt vissa effekter bli ljuskällor.
4. Notera: RTX Remix Toolkit (för att redigera) finns bara för Windows. På Linux går det att fånga
   scener och redigera USD-filer för hand eller med skript; större innehållsarbete görs enklast i Windows.

## Fas 5: Putsa

1. **Rätt bildformat**: pillarbox (svarta kanter) i stället för utsträckt bild, t.ex. genom att QindieGL
   ritar spelets 640×480 centrerat i en skärmstor backbuffer.
2. **Högre upplösning**: låt Remix rendera i skärmens upplösning och skala upp spelets 2D-gränssnitt,
   i stället för att sträcka en 640×480-bild.
3. **DLSS under Proton**: prova `PROTON_ENABLE_NGX_UPDATER=1`/`PROTON_ENABLE_NVAPI=1`, annars en annan
   uppskalare uttryckligen.
4. Prestanda: mät FPS på testplatserna (Remix kan visa det), justera `rtx.graphicsPreset`, studsar mm.
5. Paketera: en zip/installationsskript för Linux (QindieGL-DLL, `.trex`, configs, startalternativ).

## Risker

- Binära patchar i spelet (fas 2.2, 3) kan krascha om adresser/mönster är fel; görs alltid bakom en
  inställning i QindieGL.ini och testas i den nästlade sessionen.
- `PROTON_ENABLE_WAYLAND=1` kraschade skrivbordssessionen en gång: testa inte det utanför nästlad session.
- Remix-uppdateringar kan ändra standardvärden (t.ex. ny GUI-input), så Linux-fixarna i `rtx.conf` ska
  kontrolleras vid varje ny Remix-version.

## Nästa konkreta steg

1. Du: testa musen i menyn när du är vid datorn (eller låt mig göra det i nästlad session).
2. Jag: bygga ut testriggen (fas 0.3–0.5) och sedan köra fas 1 punkt för punkt med före/efter-bilder.
