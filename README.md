# 🎓 Flashcard Tedesco 3D

Un programma interattivo per insegnare il tedesco ai bambini attraverso flashcard
**3D animate** con audio. Interfaccia desktop multi-giocatore con turni, punteggi e
classifica finale.

## 📋 Requisiti

- Python 3.7+
- [PyQt6](https://pypi.org/project/PyQt6/) — interfaccia grafica
- [gTTS](https://pypi.org/project/gTTS/) — Google Text-to-Speech (sintesi vocale online)
- Connessione internet (solo per il primo download dell'audio di ogni parola)

> L'audio viene riprodotto con i player nativi del sistema operativo:
> **Windows** (`winmm`), **macOS** (`afplay`), **Linux** (`aplay`/`paplay`).

## 🚀 Installazione

1. Apri il terminale nella cartella del progetto
2. Installa le dipendenze:

```bash
pip install -r requirements.txt
```

## 🔊 Come Funziona l'Audio

Il programma usa **Google Text-to-Speech** tramite le **API pubbliche di Google**:

1. Quando clicchi **🔊 Ascolta**, il testo viene inviato ai server Google
2. Google genera un file audio MP3 con pronuncia naturale
3. Il file viene **salvato in cache** nella cartella `audio_cache/` (creata in automatico)
4. Dalle volte successive il programma usa il file in cache (nessun nuovo download)

**Vantaggi:**
- ✅ Pronuncia naturale e accurata
- ✅ Supporto per 100+ lingue
- ✅ Nessuna configurazione richiesta (no chiavi API)
- ✅ Caching automatico (offline dopo il primo uso di ogni parola)

> La cartella `audio_cache/` è generata a runtime e **non** è inclusa nel repository.

## 📖 Come Usare

1. Esegui il programma:

```bash
python main.py
```

2. **Schermata iniziale**: scegli il numero di giocatori, la **difficoltà**
   (Facile / Medio / Difficile) ed eventualmente attiva il **timer**.
3. **Nomi e icone**: dai un nome a ogni giocatore e scegli un'emoji.
4. **Gioca**:
   - Clicca sulla **carta** (o premi `Spazio`) per girarla con l'animazione 3D
     e vedere la traduzione tedesca
   - Clicca **🔊 Ascolta** (o premi `A`) per sentire la pronuncia
   - Clicca **✅ GIUSTO** / **❌ SBAGLIATO** (o usa le frecce `→` / `←`)
     per passare alla parola successiva
   - I giocatori si alternano a ogni parola
5. **Fine gioco**: classifica finale con medaglie 🥇🥈🥉; puoi rigiocare o tornare al menu.

### ⌨️ Scorciatoie da tastiera

| Tasto | Azione |
|-------|--------|
| `Spazio` | Gira la carta (flip 3D) |
| `→` | Risposta corretta |
| `←` | Risposta sbagliata |
| `A` | Riproduci l'audio |

## 📚 Aggiungere Nuove Parole

Apri il file `data/words.txt` e aggiungi una parola per riga nel formato
`Italiano|Tedesco` (la categoria è opzionale):

```
Gatto|Katze
Cane|Hund
Mela|Apfel|Cibo
```

- I primi due campi (`Italiano|Tedesco`) sono obbligatori.
- Il terzo campo opzionale è la **categoria** (default: `Generale`).

## ⚙️ Personalizzazione

- Le emoji disponibili sono nella lista `emojis` in `main.py` (`_init_names_ui`)
- Difficoltà: filtra le parole per lunghezza (Facile ≤ 6 lettere, Difficile ≥ 5)
- Timer: configurabile tramite `GameSettings.timer_seconds`
- Colori, dimensioni e animazioni sono regolabili dalle costanti in cima a `main.py`
  (`CARD_SIZE`, `ANIMATION_DURATION`, `PERSPECTIVE_SHEAR_FACTOR`, …)

## 🎯 Funzionalità

✅ Supporto multi-giocatore con turni
✅ Scelta di nome e icona per ogni giocatore
✅ Flashcard **3D** con animazione di flip e prospettiva
✅ Audio text-to-speech in italiano e tedesco (cross-platform)
✅ Difficoltà selezionabile e timer opzionale
✅ Tracciamento dei punteggi in tempo reale
✅ Classifica finale con medaglie
✅ Gestione dinamica delle parole da file esterno

## 🐛 Risoluzione Problemi

**Problema**: `ModuleNotFoundError: No module named 'PyQt6'`
- Soluzione: installa le dipendenze con `pip install -r requirements.txt`

**Problema**: il suono non funziona
- Controlla di avere **connessione internet** (necessaria al primo download)
- Assicurati che **gTTS** sia installato: `pip install gtts`
- Verifica che gli altoparlanti siano accesi
- Su Linux potrebbe servire `alsa-utils` (`aplay`) o `pulseaudio-utils` (`paplay`)

**Problema**: errore "Impossibile scaricare audio"
- Possibile problema di connessione o firewall: riprova con una connessione stabile

## 📝 Note

Il programma mescola (shuffle) le parole a ogni partita, quindi l'ordine cambia
ogni volta.
