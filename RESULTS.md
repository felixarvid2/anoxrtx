# Resultat: fas 0–3 i PLAN.md

Alla tester är gjorda på Linux (GE-Proton 11-9, RTX 5060, Remix 1.5.2 release) i en nästlad
`Xwayland :7` med testriggen `tools/anoxrig.py`.

## Testmetod (fas 0)

- `anoxrig.py timeline PFX 60 90 120 150 180 240` startar ett nytt spel (New Universe → Normal) och tar
  bilder ett fast antal sekunder efter klicket, utan att hoppa över något. Öppningsfilmen är tidsstyrd,
  så **samma tidpunkt ger samma scen** varje gång (två körningar skiljer bara 1–4 i medelvärde per pixel,
  upp till ~10 där kameran rör sig snabbt). Scenerna täcker rymden, staden, gränden, Boots-scenen och
  Rowdy's bar.

  ![testscener, två körningar](docs/img/timeline-cmp.jpg)

- Upptäckter om spelet som riggen behöver:
  - Introt stannar på svart bild tills man trycker **Esc**.
  - Menyerna läser musen **relativt** (Quake 2-stil: `GetCursorPos` mot fönstrets mitt + `SetCursorPos`),
    så klick görs med relativa rörelser (`move`, `press`). `BorderlessFullscreen` fungerar därför med musen
    utan extra skalning; grenen `borderless-mouse` i QindieGL behövs inte.
  - Konsolen gick inte att öppna (varken `` ` `` eller tangentkod 49, med `+set console 1`).
  - `+map` från kommandoraden laddar inte en bana (utan Remix: titelskärm; med Remix: fastnar på
    "One moment......").
  - Sparning går bara vid TimeMinders; det fanns inga sparfiler, därför används öppningsfilmen som testbana.

## Fas 1: konfig

| Variant | Ändring | Resultat |
|---|---|---|
| v1 | QindieGL `[game.anox]`: `orthoskipuntextureddraws = 1`, `depthOffDisablesWrites = 1` | Ingen skillnad utöver brus i testscenerna |
| v2 | `r_novis 1`, `gl_dynamic 0`, `gl_flashblend 0`, `gl_polyblend 0` | Ingen tydlig kvalitetsskillnad (bilderna förskjuts lite i tid) |
| v3 | `cl_distancecull 0`, `cl_noheadcull 1`, `cl_weathercull 0` | Ingen skillnad utöver brus |
| v5 | `rtx.suppressLightKeeping = True`, `rtx.sceneScale = 0.4` | Ingen tydlig skillnad |

Inget av detta infördes som standard, eftersom det inte syntes någon förbättring. Variablerna kan
fortfarande spela roll i spelbanor med mer rörelse och dynamiska ljus (inte testat).

## Fas 2: ljus

- **v4, reservljus** (`rtx.fallbackLightMode = 2`): mörka scener blir något ljusare (gränden, neonskylten).
  Ett fast riktat ljus kan se fel ut inomhus, så det ligger **avstängt som kommentar** i `rtx.conf`.

  ![utan / med reservljus](docs/img/cmp-v4.jpg)

- **Spelets dynamiska ljus som Remix-ljus** (`flashblendlights`, QindieGL-gren `flashblend-lights`):
  QindieGL känner igen Quake 2:s "flashblend"-ritning av dynamiska ljus (additiv triangelfläkt med färgat
  centrum och svart kant) och lägger in ett Remix-ljus i stället via Remix API. Byggt och Remix API startar,
  men öppningsfilmen har inga dynamiska ljus, så **funktionen är inte prövad**. Avstängd som standard.
  Testa i en bana med strid/explosioner med `gl_flashblend 1`, `remixapi = 1`, `flashblendlights = 1` och
  `exposeRemixApi = True` i `.trex/bridge.conf`; loggen visar `flashblend light #N` när den slår till.
- **Ljus ur banfilerna** (`maplights`, QindieGL-gren `maplights`): fungerar.
  - `tools/adat.py` packar upp spelets ADAT-arkiv (format från hogsy/chronon); `tools/bspinfo.py` läser
    ljus, himmel och vätskeytor ur BSP-filerna (16 068 `light` i 97 av 98 banor, 21 skyboxar i
    `GRAPHICS.dat` `sky\`, 27 vätsketexturer); `tools/bsp2lights.py` skriver en `.lights`-fil per bana.
  - Ljus i `mod.usda` under `/RootNode/lights` fungerar **inte**: Remix (1.5.2, `rtx_mod_usd.cpp`) läser
    dem bara som ersättning av spelets egna ljus. En Remix-fångst för att hitta en ankarmesh gick inte att
    starta från riggen (Remix får inga syntetiska tangenttryck), så ljusen läggs in via Remix API i stället:
    QindieGL fångar `ref_gl.dll!ref_SetMapName`, läser `rtx-remix/maplights/<bana>.lights` och ritar
    ljusen varje bildruta. Kräver `remixapi = 1`, `maplights = 1` i `[game.anox]` och
    `exposeRemixApi = True` i `.trex/bridge.conf`.
  - Rowdy's (71 ljus), vänster utan, mitten `maplights_scale = 100`, höger 1000:

    ![kartljus av / 100 / 1000](docs/img/cmp-maplights.jpg)

## Fas 3: geometri

- **Mjuka normaler** (`smoothnormals = 1`, QindieGL-gren `smooth-normals`): QindieGL räknar ut mjuka
  normaler för modeller/figurer (inte världen). Anachronox ritar hela modeller i ett anrop (triangellistor,
  ~540 hörn), så utjämningen gäller hela modellen. Remix debug-vy *Shading Normal* (index 16 i 1.5.2):

  ![utan / med smoothnormals](docs/img/cmp-normals.jpg)

  Med detta behövs inte längre tricket med maxad roughness/metalness på figurer för att dölja kanterna.
- **Stabila hashar**: debug-vy *Geometry Hash* (277). Världens hashar är identiska mellan körningar.
  Figurer byter hash i varje animationsbildruta (vänster/höger nedan: bartendern och Boots har olika färg):

  ![geometrihash, två körningar](docs/img/cmp-hash.jpg)

  Med `rtx.geometryAssetHashRuleString = indices,texcoords,geometrydescriptor` (positioner utelämnade)
  får figurerna samma hash hela tiden, så deras geometri kan bytas ut. Infört i `rtx.conf`.

  ![med hashregeln: samma färger](docs/img/cmp-hash-rule.jpg)

- **Himmel och filmkamera**: inte undersökt närmare. Remix hittar kameran i alla filmscener i testerna
  (`Camera cut detected` vid varje klipp, inga `rejected an invalid camera` efter starten).

## Kvar att göra

- Testa `flashblendlights` i en bana med dynamiska ljus.
- Prova fas 1-variablerna i spelbanor (inte bara öppningsfilmen).
- Himmel (skyboxarna är 256x256: uppskalning/utbyte), vatten (27 vätsketexturer -> Remix-material), partiklar.
- Finjustera kartljusens styrka/radie per ljustyp (`falloff`, `cap`, `_cone` används inte än).
