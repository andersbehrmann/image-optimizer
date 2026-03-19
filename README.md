# Image Optimizer

En skrivbordsapp för att optimera bilder för webben. Appen skalar ner JPG-bilder till max 1920px bredd, konverterar dem till WebP-format och komprimerar dem med TinyPNG API för optimal SEO-prestanda.

## Funktioner

- ✅ Välj en eller flera JPG-filer
- ✅ Skalar automatiskt ner bilder till max 1920px bredd (konfigurerbart)
- ✅ Konverterar till WebP-format
- ✅ Komprimerar med TinyPNG API för optimal filstorlek
- ✅ Enkelt grafiskt gränssnitt
- ✅ Progress bar för att följa behandlingen
- ✅ Välj output-mapp eller spara bredvid originalfiler

## Installation

### 1. Klona eller ladda ner projektet

```bash
cd /Users/anbeac/Python/image-optimizer
```

### 2. Skapa virtuell miljö (rekommenderas)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installera beroenden

```bash
pip install -r requirements.txt
```

### 4. Konfigurera TinyPNG API-nyckel

Du behöver en API-nyckel från TinyPNG:

1. Gå till https://tinypng.com/developers
2. Registrera dig och få din API-nyckel
3. Ange nyckeln i appen vid första användningen (eller redigera `config.json`)

Med ett Pro-konto får du:
- 500 komprimeringer/månad gratis
- Sedan $0.009 per bild
- Inga begränsningar på filstorlek

## Användning

### Starta appen

```bash
python3 main.py
```

### Bygg macOS-app (.app)

Projektet använder **PyInstaller** (se `Image Optimizer.spec`). Kör:

```bash
./build_app.sh
```

Appen hamnar i `dist/Image Optimizer.app`. (Eldre `py2app`-bygge kan krascha på vissa macOS-versioner när Tk laddas under bygget.)

**API-nyckel i .app:** När du sparar nyckeln i den byggda appen skrivs `config.json` till  
`~/Library/Application Support/Image Optimizer/config.json` (inte i själva .app-bunten, som kan vara skrivskyddad).

## Versioning

Projektet använder en fristående `VERSION`-fil (i repo-roten) som single source of truth för semver (`MAJOR.MINOR.PATCH`).

Den används vid bygg:
- `setup.py` läser `VERSION` och sätter `CFBundleShortVersionString`/`CFBundleVersion` i appens `Info.plist` (py2app).
- `Image Optimizer.spec` läser `VERSION` och sätter samma plist-nycklar (PyInstaller).

### Bump av version och changelog

Scriptet `scripts/bump_version.py`:
- läser nuvarande version från `VERSION`
- tolkar Conventional Commits
- räknar semver-bump (breaking -> `major`, `feat` -> `minor`, annars -> `patch`)
- uppdaterar `VERSION`
- flyttar innehållet i `## Unreleased` till en ny versionssektion i `CHANGELOG.md` och lägger till commit-bullets under `### Added`/`### Fixed` (och övrigt under `### Changed`)

Vid behov kan scriptet även:
- skapa en git-commit för version- och changelog-ändringar (`--commit-changes`)
- skapa en git-tag för releasen (`--create-tag`)
- pusha taggen till GitHub (`--push-tag`, kräver att du har en `origin`-remote)

Exempel (ingen git-historik):
1. Skapa `commits.txt` med en commit per rad (eller separerade block med tom rad), t.ex.
   - `feat: stöd bulk-komprimering av bilder`
   - `fix: hantera tom fil-lista`
2. Kör:
```bash
python3 scripts/bump_version.py --commits-file commits.txt
```

För att även commit:a och tagga:
```bash
python3 scripts/bump_version.py --commits-file commits.txt --commit-changes --create-tag
```

Exempel (om git-historik finns):
```bash
python3 scripts/bump_version.py --git-range v1.0.0..HEAD --commit-changes --create-tag
```

För att även pusha taggen:
```bash
python3 scripts/bump_version.py --git-range v1.0.0..HEAD --commit-changes --create-tag --push-tag
```

Förhandskörning utan ändringar:
```bash
python3 scripts/bump_version.py --git-range v1.0.0..HEAD --dry-run
```

### Conventional Commits för semver

- Patch (`fix`): `fix: handle missing API key`
- Minor (`feat`): `feat: support bulk PNG + WebP output`
- Major (breaking):
  - `feat!: rename config.json key`
  - eller:
    - `feat: rename config.json key`
    - `BREAKING CHANGE: config.json formatet ändras; tidigare nycklar stöds inte längre.`

### Steg-för-steg

1. **Ange API-nyckel**: Klistra in din TinyPNG API-nyckel och klicka "Spara nyckel"
2. **Välj bilder**: Klicka "Välj JPG-filer" och välj en eller flera bilder
3. **Välj output-mapp** (valfritt): Om du vill spara de optimerade bilderna i en specifik mapp
4. **Justera inställningar**: Ändra max bredd om 1920px inte passar
5. **Optimera**: Klicka "Optimera bilder" och vänta
6. **Klart!**: Dina WebP-bilder är sparade och redo för publicering

## Exempel

**Input**: `foto.jpg` (3840x2160px, 4.5MB)  
**Output**: `foto.webp` (1920x1080px, ~180KB)

## TinyPNG API-dokumentation

Fullständig dokumentation: https://tinypng.com/developers/reference

### Vad gör TinyPNG?

- **Smart komprimering**: Minskar filstorleken med 60-80% utan synlig kvalitetsförlust
- **WebP-konvertering**: Konverterar automatiskt till modernt WebP-format
- **Bevarad kvalitet**: Använder smart lossy compression som behåller bildkvalitet

### API-gränser

- **Gratis tier**: 500 bilder/månad
- **Pro tier**: Obegränsat antal, betala per bild
- **Max filstorlek**: 5MB per bild (kan ökas med Pro)

## Teknisk information

### Arbetsgång

1. Bilden laddas in med Pillow
2. Om bredd > 1920px: Skala ner lokalt med bibehållet aspect ratio
3. Ladda upp till TinyPNG API
4. TinyPNG komprimerar och konverterar till WebP
5. Ladda ner och spara den optimerade bilden

### Filformat

- **Input**: JPG/JPEG
- **Output**: WebP (modernt webbformat med bättre komprimering än JPG)

### Varför WebP?

- Upp till 30% mindre filstorlek än JPG vid samma kvalitet
- Stöds av alla moderna webbläsare
- Bättre för SEO (snabbare laddningstider)
- Stödjer både lossy och lossless komprimering

## Felsökning

### "API-nyckel saknas"
- Kontrollera att du har angett din TinyPNG API-nyckel
- Klicka "Spara nyckel" efter att ha klistrat in den

### "Unauthorized" eller "401 error"
- Din API-nyckel är ogiltig
- Hämta en ny nyckel från https://tinypng.com/developers

### "Too many requests"
- Du har nått din månadsgräns (500 bilder på gratis tier)
- Uppgradera till Pro eller vänta till nästa månad

### Appen startar inte
- Kontrollera att du har installerat alla beroenden: `pip install -r requirements.txt`
- Aktivera din virtuella miljö: `source venv/bin/activate`

### Många kopior av appen öppnas (löst i senare versioner)
I en PyInstaller-bundlad `.app` får man **inte** starta `sys.executable` med `-c …` för att “testa Tk” — det är samma binär som hela appen och kan ge en kaskad av nya instanser. Koden hoppar nu över det testet när appen körs som `frozen`.

### Appen kraschar direkt vid start (macOS 26+, `TkpInit` / `Tcl_Panic` i kraschrapport)
Det beror på att **Apples system-Tk 8.5** inte fungerar med din macOS-version. Lösningen är att bygga `.app` med en Python som **innehåller egna Tcl/Tk-frameworks** (standard för **python.org**-installern), så de packas in i appen.

- Kör `./build_app.sh` — den varnar och avbryter om Tcl/Tk saknas i din `python3`.
- Bygg sedan med t.ex.  
  `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m PyInstaller "Image Optimizer.spec"`  
  (efter `pip install -r requirements.txt` med samma interpreter).

`boot.py` sätter `TCL_LIBRARY` / `TK_LIBRARY` till de inbundna frameworks innan Tk laddas.

## Systemkrav

- macOS (eller annat Unix-baserat system)
- Python 3.8 eller senare
- Internet-anslutning (för TinyPNG API)

## Licens

Fri att använda för personligt och kommersiellt bruk.

## Support

För frågor om TinyPNG API: https://tinypng.com/developers
För tekniska problem: Kontakta utvecklaren

---

**Tips**: För bästa resultat, börja med högkvalitativa originalbilder. TinyPNG kan göra underverk, men det går inte att återställa kvalitet som redan förlorats i tidigare komprimering.
