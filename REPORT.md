# Raport de evaluare a solutiei

## 1. Descriere generala

Sistemul implementat este o arhitectura publish/subscribe content-based. Publicatiile sunt generate de noduri publisher, trec printr-o retea de brokeri si sunt livrate catre subscriberi doar daca respecta subscriptiile inregistrate.

Implementarea contine:

- 2 publisheri logici;
- 3 brokeri intr-un overlay de tip ring;
- 3 subscriberi;
- subscriptii generate aleatoriu;
- filtrare content-based;
- rutare balansata a subscriptiilor;
- evaluare automata pentru 10.000 subscriptii;
- serializare binara de tip Protocol Buffers wire format;
- suport pentru caderea unui broker;
- demo de matching pe tokenuri HMAC, fara expunerea continutului raw.

## 2. Modelul publicatiilor si subscriptiilor

O publicatie are urmatoarele campuri principale:

- `company` - valoare string;
- `city` - valoare string;
- `category` - valoare string;
- `value` - valoare numerica;
- `source` - publisherul care a emis mesajul;
- `created_ns` - timestamp pentru masurarea latentei.

O subscriptie contine una sau mai multe conditii de forma:

```text
field operator value
```

Exemple:

```text
company = Tesla
city = Bucuresti
value >= 500
category = auto
```

Matching-ul se face conjunctiv: o publicatie se potriveste cu o subscriptie doar daca toate conditiile sunt adevarate.

## 3. Rutarea subscriptiilor

Pentru a evita centralizarea, subscriptiile nu sunt stocate pe un singur broker. La inregistrare, subscriberul se conecteaza la un broker aleatoriu, iar acesta ruteaza subscriptia catre un broker tinta.

Mecanismul folosit este **Balanced Rendezvous Routing**:

1. se extrage cheia de rutare din conditia principala a subscriptiei;
2. se calculeaza scoruri stabile pentru brokeri folosind hash;
3. se aleg candidatii cei mai potriviti pentru cheia respectiva;
4. se selecteaza brokerul care mentine cea mai buna balansare pentru acel subscriber si pentru incarcarea globala;
5. subscriptia este stocata pe brokerul tinta si replicata pe un broker backup.

Prin acest mecanism, subscriptiile aceluiasi subscriber sunt distribuite pe mai multi brokeri.

## 4. Rutarea publicatiilor

Publicatia este transmisa de publisher catre broker folosind serializare binara in format Protocol Buffers wire format. Dupa ce intra in overlay, publicatia este propagata prin ring. Fiecare broker verifica doar subscriptiile locale, deci matching-ul este distribuit.

Nu exista un broker unic care contine toate subscriptiile si face toate verificarile.

## 5. Evaluare

Evaluarea ceruta se ruleaza cu:

```bash
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare
```

Aceasta comanda ruleaza doua scenarii:

1. 100% dintre subscriptii folosesc operatorul `=` pe campul `company`;
2. aproximativ 25% dintre subscriptii folosesc operatorul `=` pe campul `company`, iar restul folosesc `!=`.

Statisticile masurate sunt:

- numarul de publicatii emise;
- cate publicatii au fost livrate cu succes catre cel putin un subscriber;
- numarul total de notificari livrate;
- latenta medie de livrare;
- latenta p95;
- rata de matching.

Rata de matching este calculata ca:

```text
notificari_livrate / (publicatii_emise * numar_subscriptii)
```

Rezultatele sunt salvate automat in folderul `results/`.

## 6. Bonus: toleranta la caderi

Fiecare subscriptie are un broker primar si un broker backup. Daca un broker cade, publicatiile evita nodul indisponibil, iar copiile replicate pot fi folosite pentru livrare. Subscriberii fac deduplicare dupa perechea:

```text
(publication_id, subscription_id)
```

Astfel, acelasi match nu este livrat de doua ori.

Rulare demo:

```bash
python -m pubsub.evaluation --subscriptions 10000 --duration 180 --publisher-rate 25 --compare --failure-demo
```

## 7. Bonus: filtrare fara acces la continut

Pentru matching pe continut ascuns, proiectul include o varianta bazata pe tokenuri HMAC. Subscriberul transforma conditia de egalitate intr-un token, iar publisherul transforma campurile publicatiei in tokenuri. Brokerul compara doar tokenurile, fara sa vada valorile reale.

Rulare:

```bash
python -m pubsub.encrypted_demo
```

Limitare: varianta HMAC suporta natural operatorul de egalitate. Operatorii de tip range (`>`, `<`) necesita mecanisme criptografice mai avansate.

## 8. Limitari

Solutia este implementata ca simulare intr-un singur proces pentru simplitate si portabilitate. Totusi, componentele sunt separate logic si pot fi mutate in procese separate cu comunicatie TCP/UDP. Scopul proiectului este demonstrarea arhitecturii, a rutarii si a matching-ului distribuit.
