# Rapporto di copertura — sbobina.py

Collaudo eseguito il 16 agosto 2026 sul PDF sintetico di `prova_sbobina.py`.

## Modifiche al codice

- `sbobina.py`
  - `_chunk_fonte()` ora torna anche le statistiche di taglio (`titoli`, `pagine`, `paragrafi`, `frasi`, `parole`).
  - `_riscrivi_chunked()` restituisce le statistiche e il numero di pezzi.
  - `processa_sezione()` salva nello stato `chunk` e `stats_taglio` per ogni sezione.
  - Nuove funzioni `rapporto_dati()` e `formatta_rapporto()`; `rapporto()` resta la versione leggibile.
- `prova_sbobina.py`
  - Aggiornate le chiamate a `_chunk_fonte()` per il nuovo return.
  - Nuova asserzione permanente `assert_copertura_rapporto()` che verifica:
    - `caratteri_coperti == caratteri_fonte`
    - `saltate_per_lunghezza == 0`

## Risultati del collaudo

```
slug: prova-sbobina
stadio: sbobinato
sezioni totali: 6
sezioni riscritte: 6
sezioni saltate: 0
caratteri fonte: 10,975
caratteri coperti: 10,975
sezioni divise: 0
pezzi totali: 6
livello taglio:
  - titoli: 0
  - pagine: 0
  - paragrafi: 0
  - frasi: 0
  - parole: 0
saltate per lunghezza: 0
numeri segnalati: 0
tempo impiegato: 175s
modello: qwen3:8b (500a1f067a9f)
vram durante il lavoro: 6852 MiB
```

## Verifica dell'invariante

`caratteri_coperti == caratteri_fonte`: 10.975 su 10.975.  
`saltate_per_lunghezza == 0`: zero.

La promessa "senza tralasciare nulla" e' un numero verificato, non marketing.
