# Content-based Publish/Subscribe Overlay

Proiect complet pentru tema: arhitectura publish/subscribe content-based cu publisheri, brokeri, subscriberi, rutare balansata, evaluare si bonusuri implementate.

## Ce contine proiectul

- **1-2 publisheri** care genereaza publicatii cu valori aleatoare.
- **3 brokeri** intr-un overlay de tip ring.
- **2-3 subscriberi** care se conecteaza aleatoriu la brokeri si inregistreaza subscriptii generate aleatoriu.
- **Filtrare content-based** pe campuri precum `company`, `city`, `category`, `value`.
- **Rutare avansata la inregistrarea subscriptiilor** prin Balanced Rendezvous Routing.
- **Publicatii propagate prin mai multi brokeri**, nu matching centralizat intr-un singur broker.
- **Evaluare pentru 10.000 subscriptii simple**, inclusiv comparatie intre 100% egalitate si 25% egalitate pe campul `company`.
- **Serializare binara Protocol Buffers wire format** pentru transmiterea publicatiilor de la publisher la broker.
- **Toleranta la caderea unui broker** prin replicarea subscriptiilor pe un broker backup.
- **Demo de matching pe continut ascuns/criptat** folosind tokenuri HMAC pentru egalitate.

## Structura

```text
content_pubsub_project/
├── proto/publication.proto          # schema protobuf a publicatiei
├── src/pubsub/
│   ├── broker.py                    # nod broker
│   ├── demo.py                      # demo scurt, vizibil la prezentare
│   ├── encrypted_demo.py            # demo bonus: matching fara continut raw
│   ├── encrypted_filter.py          # HMAC token matching
│   ├── evaluation.py                # evaluare 10.000 subscriptii / 3 minute
│   ├── models.py                    # Publication, Subscription, Condition
│   ├── overlay.py                   # overlay brokeri + routing publicatii
│   ├── protobuf_codec.py            # encoder/decoder protobuf wire format
│   ├── publisher.py                 # publisher node
│   ├── routing.py                   # Balanced Rendezvous Router
│   └── subscriber.py                # subscriber node
├── scripts/run_required_evaluation.sh
├── REPORT.md                        # raport scurt pentru proiect
├── requirements.txt
└── pyproject.toml
```

## Rulare rapida

Din folderul proiectului:

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
pip install -e .
```

Demo functional:

```bash
python -m pubsub.demo
```

Demo bonus pentru matching criptat / fara acces la continut:

```bash
python -m pubsub.encrypted_demo
```

## Evaluarea ceruta in tema

Pentru rulare exacta pe feed continuu de **3 minute**:

```bash
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare
```

Pentru test rapid, accelerat, fara asteptare real-time:

```bash
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare --no-sleep
```

Cu simulare de cadere broker:

```bash
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare --failure-demo
```

Rezultatele se salveaza in `results/` ca JSON si raport Markdown.

## Explicatia mecanismului de rutare

La inregistrarea unei subscriptii, subscriberul se conecteaza la un broker ales aleatoriu. Brokerul de intrare nu pastreaza automat toate subscriptiile. In schimb:

1. Se calculeaza o cheie de rutare din continutul subscriptiei, de exemplu `company:=:Tesla`.
2. Pentru fiecare broker se calculeaza un scor Rendezvous Hashing.
3. Se aleg 2 brokeri candidati cu scorul cel mai bun.
4. Se selecteaza candidatul care mentine cel mai bine balansarea subscriptiilor aceluiasi subscriber si incarcarea globala a overlay-ului.
5. Subscriptia este trimisa prin overlay catre brokerul tinta.
6. Subscriptia este replicata pe urmatorul broker viu pentru failover.

Astfel, subscriptiile aceluiasi subscriber ajung distribuite pe mai multi brokeri, iar matching-ul este impartit intre noduri.

## Explicatia livrarii publicatiilor

Publisherul genereaza publicatia si o serializeaza binar in format protobuf-wire. Publicatia intra in overlay printr-un broker ales aleatoriu. Brokerii o propaga prin ring, iar fiecare broker face matching doar pe subscriptiile locale. Daca exista un broker cazut, brokerii vecini pot folosi copiile replicate.

## Observatie importanta

Implementarea este o simulare intr-un singur proces, ca sa fie usor de rulat la prezentare. Nodurile sunt separate logic in clase independente (`PublisherNode`, `BrokerNode`, `SubscriberNode`) si pot fi mutate ulterior in procese diferite/TCP fara schimbarea logicii principale.
