# 🎓 Flashcard Tedesco

Un programma interattivo per insegnare il tedesco ai bambini attraverso flashcard con audio.

## 📋 Requisiti

- Python 3.7+
- gtts (Google Text-to-Speech - per la sintesi vocale online)
- tkinter (solitamente incluso con Python)
- Connessione internet (per il download dell'audio la prima volta)

## 🚀 Installazione

1. Apri il terminale nella cartella del progetto
2. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

## 🔊 Come Funziona l'Audio

Il programma usa **Google Text-to-Speech** tramite le **API pubbliche di Google**:

1. Quando clicchi il pulsante 🔊, il testo viene inviato ai server Google
2. Google genera un file audio MP3 con pronuncia naturale
3. Il file viene **salvato in cache** nella cartella `audio_cache/`
4. Dalle volte successive, il programma usa il file cache (senza scaricare di nuovo)

**Vantaggi:**
- ✅ Pronuncia naturale e accurata
- ✅ Supporto per 100+ lingue
- ✅ Nessuna voce robotica
- ✅ Nessuna configurazione richiesta (no chiavi API)
- ✅ Caching automatico (offline dopo il primo uso)

## 📖 Come Usare

1. Esegui il programma:
```bash
python main.py
```

2. **Schermata iniziale**: Seleziona il numero di giocatori
3. **Inserisci nomi**: Dai un nome a ogni giocatore e scegli un'icona simpatica (emoji)
4. **Gioca**:
   - Clicca sulla **flashcard** per farla girare e vedere la traduzione
   - Clicca sul pulsante **🔊 Ascolta** per sentire la pronuncia
   - Clicca **✅ GIUSTO** o **❌ SBAGLIATO** per passare alla prossima parola
   - I giocatori si alternano ad ogni parola
5. **Fine gioco**: Vedi la classifica finale con i punteggi

## 📚 Aggiungere Nuove Parole

Apri il file `data/words.txt` e aggiungi nuove parole nel formato:

```
Italiano|Tedesco
Gatto|Katze
Cane|Hund
```

Ogni riga deve contenere una parola in italiano e la relativa traduzione tedesca, separate da `|`.

## ⚙️ Personalizzazione

- Puoi cambiare il numero di emoji disponibili modificando la lista `self.emojis` in main.py
- Puoi modificare le dimensioni e i colori dei pulsanti
- Puoi aggiungere più file di parole (creare sottocartelle in data/)

## 🎯 Funzionalità

✅ Supporto multi-giocatore con turni  
✅ Scelta di icone personalizzate per ogni giocatore  
✅ Flashcard interattive con effetto flip  
✅ Audio text-to-speech in italiano e tedesco  
✅ Tracciamento dei punteggi in tempo reale  
✅ Classifica finale con medaglie  
✅ Gestione dinamica delle parole da file esterno  

## 🐛 Risoluzione Problemi

**Problema**: Il suono non funziona
- Soluzione 1: Controlla che tu abbia **connessione internet** (necessaria per il primo download)
- Soluzione 2: Assicurati che **gtts sia installato** correttamente: `pip install gtts`
- Soluzione 3: Verifica che gli altoparlanti siano accesi

**Problema**: Errore "Impossibile scaricare audio"
- Soluzione: Potrebbe essere un problema di connessione o firewall. Riprova con connessione stabile

**Problema**: Errore "FileNotFoundError"
- Soluzione: Assicurati che la cartella `data` esista e contenga il file `words.txt`

## 📝 Note

Il programma shuffla (mescola) le parole all'avvio, quindi ogni partita avrà un ordine diverso.
