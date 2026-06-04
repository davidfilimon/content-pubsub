# Raport de evaluare - sistem publish/subscribe content-based

## Configuratie

Sistemul evaluat foloseste 2 publisheri, 3 brokeri in overlay de tip ring si 3 subscriberi. Subscriptiile sunt distribuite printr-un mecanism Balanced Rendezvous Routing: cheia de rutare este derivata din continutul subscriptiei, iar alegerea brokerului tine cont de balansarea subscriptiilor aceluiasi subscriber si de incarcarea globala a brokerilor.

Publicatiile sunt serializate binar in format Protocol Buffers wire format pentru legatura publisher -> broker. Dupa intrarea in overlay, publicatia este propagata prin brokeri, iar fiecare broker face matching doar pe subscriptiile locale/replicate.

## Rezultate

| Egalitate pe campul `company` | Publicatii emise | Publicatii livrate cu succes | Notificari livrate | Latenta medie [ms] | Latenta p95 [ms] | Rata matching |
|---:|---:|---:|---:|---:|---:|---:|
| 100% | 4500 | 4500 | 5626212 | 2.0858 | 3.1045 | 12.5027% |
| 25% | 4500 | 4500 | 30772309 | 5.8143 | 7.2644 | 68.3829% |

## Interpretare

Cazul cu 100% operator de egalitate pe campul `company` este mai selectiv: o publicatie se potriveste doar cu subscriptiile care cer exact aceeasi valoare. In cazul cu aproximativ 25% egalitate, restul subscriptiilor folosesc `!=`, ceea ce este mai putin selectiv si mareste rata de matching. Latenta ramane mica deoarece filtrarea este impartita intre brokeri, iar fiecare broker verifica numai subscriptiile proprii, nu o baza centralizata unica.

## Toleranta la caderi

Fiecare subscriptie este stocata pe un broker primar si replicata pe urmatorul broker viu din ring. Daca un broker cade, publicatiile evita nodul indisponibil, iar brokerii vecini pot folosi copiile replicate pentru a livra notificari. Subscriberii au deduplicare pe perechea `(publication_id, subscription_id)`, deci aceeasi notificare nu este livrata de doua ori.

## Limitari

Implementarea este o simulare intr-un singur proces pentru a putea fi rulata usor la prezentare. Arhitectura este separata pe noduri logice, deci poate fi extinsa ulterior la procese reale/TCP/UDP fara schimbarea modelului de rutare si matching.
