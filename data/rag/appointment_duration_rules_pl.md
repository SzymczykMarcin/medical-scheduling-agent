# Reguły czasu trwania wizyt, konsultacji, badań i drobnych zabiegów

Wersja: demo RAG dla systemu umawiania wizyt.
Język: polski.
Zastosowanie: oszacowanie czasu wizyty na potrzeby kalendarza, bez diagnozowania pacjenta.

Ten dokument jest przykładową bazą wiedzy dla przychodni demonstracyjnej. Reguły opisują typowe czasy rezerwacji w grafiku, a nie gwarantowany czas medyczny. W realnej placówce należy zastąpić ten plik lokalnym cennikiem, listą usług, regulaminem rejestracji i zasadami pracy personelu.

## Zasada nadrzędna

System ma wybrać czas wizyty tylko spośród wartości obsługiwanych przez scheduler: 30, 60, 90 albo 120 minut.

Jeżeli opis pacjenta pasuje do kilku kategorii, wybierz dłuższy czas. Jeżeli pacjent zgłasza kilka niezależnych problemów, nowy problem przewlekły, potrzebę omówienia dokumentacji, wyników z wielu badań, kilka zaświadczeń albo oczekuje jednocześnie konsultacji i zabiegu, nie skracaj wizyty.

Jeżeli w zgłoszeniu pojawia się nagły ból w klatce piersiowej, duszność spoczynkowa, objawy udaru, utrata przytomności, silny uraz, krwawienie, objawy anafilaksji, myśli samobójcze, ciężki stan dziecka lub inne potencjalnie pilne zagrożenie życia, nie umawiaj standardowej wizyty automatycznie. Ustaw `requires_human_callback=true` i wyjaśnij, że wymagany jest kontakt z personelem lub pilna pomoc.

## Mapowanie czasu na slot

- 30 minut: prosta konsultacja, pojedynczy problem, krótkie badanie, wynik, recepta, skierowanie, pojedyncza drobna procedura.
- 60 minut: pierwsza konsultacja specjalistyczna, kilka problemów, pełniejszy wywiad, badanie z opisem, konsultacja z omówieniem dokumentacji, wizyta dziecka z szerszym wywiadem, drobny zabieg z przygotowaniem.
- 90 minut: złożone badanie lub pakiet badań, konsultacja wieloproblemowa, procedura z obserwacją, medycyna pracy z kilkoma elementami, rozbudowana rehabilitacja lub diagnostyka funkcjonalna.
- 120 minut: przegląd zdrowia, wielospecjalistyczny pakiet, zabieg wymagający przygotowania i obserwacji, dłuższa psychoterapia lub konsultacja diagnostyczna, procedura z dużą niepewnością czasu.

## Źródła orientacyjne użyte przy przygotowaniu demo

- Portal pacjent.gov.pl opisuje Internetowe Konto Pacjenta i centralną e-rejestrację jako kontekst umawiania świadczeń online.
- LUX MED opisuje EKG spoczynkowe jako badanie trwające kilka minut i niewymagające skomplikowanego przygotowania.
- LUX MED opisuje USG jamy brzusznej jako badanie trwające od kilkunastu do kilkudziesięciu minut.
- LUX MED i Medicover opisują spirometrię jako badanie czynnościowe układu oddechowego wymagające współpracy pacjenta i wykonania manewrów oddechowych.

Powyższe źródła są tylko orientacją dla demo. Konkretny czas slotu w przychodni powinien wynikać z lokalnych procedur, dostępności personelu i sposobu opisu wyniku.

## Reguły językowe dla rozpoznawania intencji

Synonimy wizyty podstawowej:
- lekarz rodzinny, internista, POZ, lekarz pierwszego kontaktu, ogólny, zwykła wizyta, konsultacja, porada.

Synonimy wizyty pilnej, ale niekoniecznie ratunkowej:
- pilnie, jak najszybciej, dziś, jutro rano, infekcja, gorączka, ból, zaostrzenie, kaszel, duszność przy wysiłku, wysypka.

Synonimy dokumentów:
- recepta, e-recepta, skierowanie, zaświadczenie, L4, zwolnienie, wynik, opis badania, dokumentacja, karta informacyjna, wypis ze szpitala.

Synonimy badań:
- krew, morfologia, lipidogram, TSH, mocz, EKG, echo serca, USG, spirometria, Holter, cytologia, wymaz, szczepienie, bilans, kontrola.

Synonimy zabiegów:
- zdjęcie szwów, opatrunek, rana, zastrzyk, iniekcja, blokada, płukanie ucha, usunięcie zmiany, brodawka, kurzajka, krioterapia, nacięcie, drenaż.

Jeżeli pacjent mówi tylko "chcę się umówić" bez powodu wizyty, ustaw 30 minut i niską pewność albo `requires_human_callback=true`, zależnie od dostępnych preferencji terminu.

## Konsultacje podstawowe POZ i internistyczne

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Przedłużenie stałej recepty bez nowych objawów | 30 | Krótka wizyta administracyjno-kontrolna. |
| Recepta plus krótka kontrola ciśnienia lub samopoczucia | 30 | Pojedynczy temat, brak nowych złożonych dolegliwości. |
| Omówienie jednego wyniku badania laboratoryjnego | 30 | Jeśli pacjent ma jeden wynik lub prostą kontrolę. |
| Skierowanie do specjalisty bez nowych objawów alarmowych | 30 | Administracyjna porada z krótkim wywiadem. |
| Infekcja górnych dróg oddechowych u dorosłego | 30 | Kaszel, katar, ból gardła, gorączka bez objawów alarmowych. |
| Grypa, COVID, infekcja z gorączką i oceną zwolnienia | 30 | Typowa konsultacja infekcyjna. |
| Ból brzucha bez objawów alarmowych | 30 | Jeżeli pacjent mówi o jednym epizodzie i potrzebuje konsultacji. |
| Ból pleców, karku, stawu bez urazu ciężkiego | 30 | Prosty problem bólowy. |
| Kontrola nadciśnienia, cukrzycy lub tarczycy stabilnej | 30 | Jedna choroba przewlekła, rutynowa kontrola. |
| Pierwsza wizyta u internisty z pełnym wywiadem | 60 | Nowy pacjent albo kilka tematów. |
| Kilka niezależnych problemów na jednej wizycie | 60 | Np. kaszel, bóle brzucha i omówienie wyników. |
| Omówienie dokumentacji po hospitalizacji | 60 | Wypis, nowe leki, plan dalszego leczenia. |
| Kontrola pacjenta starszego wielochorobowego | 60 | Wielolekowość, kilka chorób, ryzyko interakcji. |
| Zaświadczenie z badaniem i analizą dokumentów | 60 | Dłużej niż samo wystawienie dokumentu. |
| Przegląd zdrowia dorosłego, profilaktyka, bilans | 60 | Wywiad, pomiary, plan badań. |
| Bardzo złożony przegląd zdrowia z wieloma wynikami | 90 | Gdy pacjent mówi o "całym pakiecie", wielu wynikach lub długiej historii. |

## Pediatria

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Infekcja dziecka, kaszel, katar, gorączka bez alarmów | 30 | Jedna ostra dolegliwość. |
| Wysypka u dziecka, alergia skórna, świąd | 30 | Jeśli bez duszności, obrzęku twarzy lub ciężkiego stanu. |
| Kontrola po infekcji lub zaświadczenie do żłobka/przedszkola | 30 | Krótka kontrola. |
| Bilans zdrowia dziecka | 60 | Pomiary, rozwój, wywiad, dokumentacja. |
| Pierwsza wizyta pediatryczna nowego pacjenta | 60 | Szerszy wywiad rodzinny i rozwojowy. |
| Dziecko z kilkoma objawami lub długą historią choroby | 60 | Np. brzuch, sen, jedzenie, skóra. |
| Konsultacja niemowlęcia z karmieniem, masą ciała lub rozwojem | 60 | Wymaga spokojnego wywiadu. |
| Szczepienie kwalifikacja pediatryczna plus szczepienie | 30 | Jeśli jedna szczepionka i brak złożonych problemów. |
| Kilka szczepień lub nadrabianie kalendarza szczepień | 60 | Więcej pytań i dokumentacji. |

## Ginekologia i położnictwo

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Standardowa konsultacja ginekologiczna | 30 | Jeden problem, kontrola, antykoncepcja. |
| Recepta antykoncepcyjna i krótka kontrola | 30 | Bez nowych dolegliwości. |
| Cytologia bez dodatkowych problemów | 30 | Pobranie materiału i krótki wywiad. |
| Kontrola wyniku cytologii lub wymazu | 30 | Omówienie pojedynczego wyniku. |
| Pierwsza wizyta ginekologiczna | 60 | Szerszy wywiad, edukacja, badanie. |
| Wizyta z USG ginekologicznym | 60 | Konsultacja plus badanie obrazowe. |
| Prowadzenie ciąży, rutynowa kontrola | 30 | Jeśli bez USG rozszerzonego i bez powikłań. |
| Pierwsza wizyta ciążowa | 60 | Wywiad, dokumenty, badania, zalecenia. |
| Konsultacja niepłodności lub planowania ciąży | 60 | Wymaga dokumentacji i wywiadu obojga partnerów lub historii leczenia. |
| Założenie lub usunięcie wkładki domacicznej | 60 | Procedura, zgoda, przygotowanie, kontrola. |
| Krwawienie, ból podbrzusza, podejrzenie infekcji | 30 | Jeśli bez objawów nagłych; przy ciężkim stanie callback. |

## Dermatologia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja dermatologiczna jednego problemu | 30 | Trądzik, wysypka, łuszczenie, świąd. |
| Kontrola leczenia trądziku lub łuszczycy | 30 | Bez nowych rozległych zmian. |
| Dermatoskopia jednej lub kilku zmian | 30 | Jeśli pacjent mówi o pojedynczym pieprzyku albo kilku zmianach. |
| Przegląd znamion całego ciała | 60 | Wymaga dokładniejszego badania. |
| Usunięcie drobnej zmiany skórnej | 60 | Zabieg, przygotowanie, opatrunek, zalecenia. |
| Krioterapia kurzajki/brodawki pojedynczej | 30 | Krótki zabieg. |
| Krioterapia wielu zmian | 60 | Więcej czasu na kwalifikację i zabieg. |
| Biopsja skóry | 60 | Procedura, znieczulenie, dokumentacja. |
| Pilna reakcja alergiczna skóry bez duszności | 30 | Jeśli objawy ograniczone do skóry. |

## Ortopedia, urazy i narząd ruchu

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja ortopedyczna jednego stawu | 30 | Ból kolana, barku, nadgarstka, biodra. |
| Kontrola po urazie lub zdjęciu RTG | 30 | Omówienie jednego wyniku i plan. |
| Pierwsza konsultacja ortopedyczna z dokumentacją | 60 | Kilka wyników, MRI/RTG, dłuższa historia. |
| Ból kręgosłupa z promieniowaniem | 60 | Wymaga dokładniejszego badania neurologicznego. |
| Blokada/iniekcja dostawowa | 30 | Jeśli jedna okolica i pacjent kwalifikowany. |
| Iniekcja pod kontrolą USG | 60 | Dodatkowe przygotowanie i obrazowanie. |
| Zdjęcie gipsu i kontrola | 30 | Jeśli bez skomplikowanej rany. |
| Założenie opatrunku ortopedycznego lub ortezy | 30 | Prosta procedura. |
| Podejrzenie złamania, świeży uraz, silny ból po wypadku | callback | Wymaga oceny pilności i miejsca wykonania diagnostyki. |

## Kardiologia i badania serca

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja kardiologiczna pierwszorazowa | 60 | Wywiad, leki, pomiary, dokumentacja. |
| Kontrola kardiologiczna stabilna | 30 | Jedna choroba i rutynowe omówienie leczenia. |
| Omówienie Holtera, EKG lub echo serca | 30 | Pojedynczy wynik, brak nowych objawów alarmowych. |
| EKG spoczynkowe | 30 | Samo badanie trwa kilka minut, ale slot obejmuje przygotowanie, wykonanie i obsługę wyniku. |
| Próba wysiłkowa | 60 | Przygotowanie, wykonanie, obserwacja i opis. |
| Echo serca | 60 | Badanie USG serca z opisem. |
| Założenie Holtera EKG | 30 | Krótka procedura techniczna z instruktażem. |
| Zdjęcie Holtera EKG | 30 | Zdjęcie urządzenia i przekazanie do analizy. |
| Holter ciśnieniowy założenie | 30 | Urządzenie, instrukcja, mankiet. |
| Ból w klatce piersiowej, omdlenie, duszność spoczynkowa | callback | Nie umawiać automatycznie na zwykły slot. |

## Pulmonologia i alergologia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja pulmonologiczna pierwszorazowa | 60 | Wywiad, dokumentacja, wyniki badań. |
| Kontrola astmy lub POChP stabilnej | 30 | Rutynowa kontrola leczenia. |
| Kaszel przewlekły ponad kilka tygodni | 60 | Wymaga szerszego wywiadu. |
| Spirometria bez konsultacji | 30 | Badanie wymaga instruktażu i powtarzanych manewrów oddechowych. |
| Spirometria z próbą rozkurczową | 60 | Badanie przed i po leku, przerwa i powtórzenie. |
| Konsultacja alergologiczna pierwsza | 60 | Wywiad sezonowy, leki, ekspozycje. |
| Testy skórne punktowe | 60 | Przygotowanie, wykonanie, odczyt. |
| Odczulanie kolejna dawka | 30 | Krótka procedura plus obserwacja według lokalnych zasad. |
| Silna duszność, świszczący oddech w spoczynku, obrzęk twarzy | callback | Możliwy stan pilny. |

## Diagnostyka obrazowa USG

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| USG jamy brzusznej | 30 | Typowo kilkanaście do kilkudziesięciu minut; w demo rezerwuj 30. |
| USG tarczycy | 30 | Jedna okolica, standardowy opis. |
| USG piersi | 30 | Jedna usługa diagnostyczna. |
| USG węzłów chłonnych | 30 | Jedna okolica. |
| USG układu moczowego | 30 | Nerki, pęcherz, czasem prostata; jeśli pełny zakres, nadal 30 lub 60 przy złożoności. |
| USG prostaty przez powłoki brzuszne | 30 | Standardowe badanie. |
| USG jąder | 30 | Jedna okolica. |
| USG ślinianek | 30 | Jedna okolica. |
| USG tkanek miękkich, guzka, przepukliny | 30 | Ograniczony obszar. |
| USG Doppler jednej okolicy | 60 | Naczynia wymagają dłuższej oceny i opisu. |
| USG dwóch różnych okolic | 60 | Np. tarczyca i brzuch. |
| USG kilku okolic lub pacjent z obfitą dokumentacją | 90 | Gdy pacjent oczekuje szerokiego badania wielu obszarów. |
| USG ginekologiczne z konsultacją | 60 | Łączone z wywiadem i omówieniem. |

## Badania laboratoryjne i punkty pobrań

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pobranie krwi pojedyncze | 30 | W demo najkrótszy obsługiwany slot. |
| Pobranie krwi plus mocz | 30 | Standardowy punkt pobrań. |
| Pakiet badań profilaktycznych | 30 | Pobranie materiału, bez konsultacji. |
| Krzywa cukrowa OGTT | 120 | Wymaga wypicia glukozy i kolejnych pobrań w czasie. |
| Test obciążenia insuliną lub wielopunktowe pobrania | 120 | Dłuższa obserwacja i pobrania. |
| Wymaz z gardła/nosa | 30 | Krótka procedura. |
| Wymaz ginekologiczny bez konsultacji | 30 | Krótka procedura. |
| Badanie kału, moczu, dostarczenie materiału | 30 | Organizacyjnie krótki slot. |
| Pobranie u dziecka trudne lub pacjent mdlejący | 60 | Więcej czasu na uspokojenie i obserwację. |

## Szczepienia i iniekcje

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Kwalifikacja do szczepienia dorosłego | 30 | Krótki wywiad i kwalifikacja. |
| Szczepienie dorosłego jedna szczepionka | 30 | Kwalifikacja plus podanie, jeśli lokalnie łączone. |
| Szczepienie dziecka jedna szczepionka | 30 | Jeśli rutynowe i bez złożonej historii. |
| Nadrabianie szczepień lub plan szczepień | 60 | Wymaga dokumentacji i planu. |
| Szczepienie podróżne z konsultacją | 60 | Wywiad o trasie, ryzykach i zaleceniach. |
| Zastrzyk domięśniowy lub podskórny | 30 | Prosta iniekcja. |
| Seria iniekcji lub lek wymagający obserwacji | 60 | Jeśli placówka wymaga obserwacji po podaniu. |
| Wlew dożylny, kroplówka | 90 | Czas zależy od preparatu; w demo 90, przy dłuższych preparatach 120. |

## Laryngologia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja laryngologiczna pierwszorazowa | 30 | Jeden problem: ucho, gardło, nos, zatoki. |
| Kontrola laryngologiczna | 30 | Krótka wizyta. |
| Płukanie ucha | 30 | Prosta procedura. |
| Usunięcie woskowiny pod kontrolą wzroku | 30 | Krótki zabieg. |
| Badanie słuchu orientacyjne | 30 | Jeśli podstawowe. |
| Audiometria tonalna | 30 | Badanie techniczne. |
| Konsultacja z endoskopią nosa/gardła | 60 | Dodatkowa procedura i opis. |
| Nawracające zawroty głowy, szumy uszne, dokumentacja | 60 | Szerszy wywiad i badania. |
| Krwawienie z nosa aktualne, duszność, ciało obce u dziecka | callback | Może wymagać pilnej interwencji. |

## Okulistyka

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Kontrola okulistyczna dorosłego | 30 | Standardowe badanie, bez rozszerzania diagnostyki. |
| Dobór okularów | 30 | Refrakcja i podstawowe badanie. |
| Pierwsza wizyta okulistyczna | 60 | Szerszy wywiad i pełniejsze badanie. |
| Badanie dna oka z kroplami | 60 | Czas na rozszerzenie źrenic i badanie. |
| Pomiar ciśnienia wewnątrzgałkowego | 30 | Krótkie badanie. |
| OCT | 30 | Badanie techniczne jednej okolicy. |
| Pole widzenia | 60 | Wymaga czasu i współpracy pacjenta. |
| Nagłe pogorszenie widzenia, uraz oka, silny ból oka | callback | Nie umawiać automatycznie na zwykły slot. |

## Neurologia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pierwsza konsultacja neurologiczna | 60 | Wywiad, badanie neurologiczne, dokumentacja. |
| Kontrola neurologiczna stabilna | 30 | Omówienie leczenia i jednego problemu. |
| Bóle głowy przewlekłe | 60 | Wymaga szczegółowego wywiadu. |
| Drętwienia, zawroty głowy, omówienie MRI/CT | 60 | Dokumentacja i badanie. |
| Padaczka, utraty przytomności w wywiadzie | 60 | Szerszy wywiad i bezpieczeństwo. |
| Objawy udaru: opadanie kącika ust, niedowład, zaburzenia mowy | callback | Pilna pomoc, nie zwykła rejestracja. |

## Endokrynologia, diabetologia i dietetyka

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pierwsza konsultacja endokrynologiczna | 60 | Hormony, objawy, wyniki, leki. |
| Kontrola tarczycy stabilna | 30 | Omówienie TSH/FT3/FT4 i dawkowania. |
| Konsultacja diabetologiczna pierwsza | 60 | Pomiary, leki, dieta, wyniki. |
| Kontrola cukrzycy stabilnej | 30 | Jedna choroba, rutynowo. |
| Omówienie krzywej cukrowej lub insuliny | 30 | Jeśli tylko wynik; 60 przy pierwszej diagnozie. |
| Pierwsza konsultacja dietetyczna | 60 | Wywiad żywieniowy, cele, pomiary. |
| Kontrola dietetyczna | 30 | Korekta planu. |
| Otyłość, insulinooporność, kilka chorób metabolicznych | 60 | Złożone zalecenia. |

## Psychiatria, psychologia i zdrowie psychiczne

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pierwsza konsultacja psychiatryczna | 60 | Pełny wywiad i plan leczenia. |
| Kontrola psychiatryczna stabilna | 30 | Kontrola leków i samopoczucia. |
| Zmiana leczenia psychiatrycznego | 60 | Więcej czasu na bezpieczeństwo i działania niepożądane. |
| Pierwsza konsultacja psychologiczna | 60 | Wywiad, cel terapii, plan. |
| Psychoterapia indywidualna standardowa | 60 | Standardowa sesja. |
| Konsultacja pary lub rodzinna | 90 | Więcej osób i szerszy kontekst. |
| Diagnoza psychologiczna, testy, opinia | 90 | Może wymagać kilku spotkań; w demo 90. |
| Myśli samobójcze, zamiar samookaleczenia, zagrożenie dla siebie lub innych | callback | Pilny kontakt z pomocą kryzysową/personel. |

## Chirurgia, drobne zabiegi i opatrunki

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja chirurgiczna jednego problemu | 30 | Guzek, przepuklina, ból, kwalifikacja. |
| Kontrola rany po zabiegu | 30 | Opatrunek i ocena gojenia. |
| Zmiana opatrunku prosta | 30 | Mała rana. |
| Zmiana opatrunku rozległa lub trudno gojąca rana | 60 | Więcej czasu na oczyszczenie i dokumentację. |
| Zdjęcie szwów proste | 30 | Krótka procedura. |
| Zdjęcie szwów z rozległej rany lub kilku miejsc | 60 | Dłuższa procedura. |
| Nacięcie drobnego ropnia | 60 | Zabieg, znieczulenie, opatrunek. |
| Usunięcie drobnej zmiany skórnej chirurgicznie | 60 | Zabieg i dokumentacja. |
| Wrastający paznokieć konsultacja | 30 | Sama kwalifikacja. |
| Wrastający paznokieć zabieg | 60 | Procedura. |
| Krwawiąca rana, świeże głębokie skaleczenie, uraz głowy | callback | Może wymagać pilnej pomocy. |

## Urologia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pierwsza konsultacja urologiczna | 60 | Wywiad, wyniki, objawy, badanie. |
| Kontrola urologiczna stabilna | 30 | Pojedynczy wynik lub leczenie. |
| Objawy infekcji układu moczowego u mężczyzny | 30 | Jeśli bez gorączki i bólu nerek. |
| Omówienie PSA | 30 | Jeden wynik. |
| USG układu moczowego z konsultacją | 60 | Badanie plus omówienie. |
| Ból jądra nagły, zatrzymanie moczu, gorączka z bólem nerek | callback | Potencjalnie pilne. |

## Medycyna pracy i zaświadczenia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Proste zaświadczenie na podstawie badania | 30 | Bez obszernej dokumentacji. |
| Badanie medycyny pracy podstawowe | 30 | Jedno stanowisko, bez dodatkowych badań. |
| Medycyna pracy z wynikami, EKG lub okulistą | 60 | Kilka elementów. |
| Kierowca zawodowy, operator maszyn, praca na wysokości | 90 | Więcej elementów i dokumentacji. |
| Orzeczenie sportowe dziecka z EKG | 60 | Wywiad, badanie, EKG/wynik. |
| Zaświadczenie z analizą wieloletniej dokumentacji | 60 | Nie traktować jako prostej administracji. |

## Rehabilitacja i fizjoterapia

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Pierwsza konsultacja fizjoterapeutyczna | 60 | Wywiad, testy funkcjonalne, plan. |
| Terapia manualna standardowa | 60 | Jedna sesja. |
| Kontrola fizjoterapeutyczna krótka | 30 | Ocena postępu i korekta ćwiczeń. |
| Instruktaż ćwiczeń domowych | 30 | Prosty plan. |
| Rehabilitacja pooperacyjna pierwsza | 60 | Dokumentacja, ograniczenia, plan. |
| Rehabilitacja neurologiczna lub wieloobszarowa | 90 | Większa złożoność. |
| Pakiet zabiegów fizykoterapii jednego dnia | 60 | Kilka krótkich procedur w jednym bloku. |

## Stomatologia podstawowa

| Usługa / opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Przegląd stomatologiczny | 30 | Bez leczenia. |
| Konsultacja bólu zęba | 30 | Ocena i plan, bez zabiegu. |
| Higienizacja, skaling, piaskowanie | 60 | Standardowy blok higienizacyjny. |
| Wypełnienie jednego ubytku | 60 | Typowe leczenie zachowawcze. |
| Leczenie kanałowe konsultacja | 30 | Sama kwalifikacja. |
| Leczenie kanałowe jednej wizyty | 90 | Dłuższy zabieg. |
| Ekstrakcja prosta | 60 | Zabieg i instrukcje. |
| Ekstrakcja chirurgiczna | 90 | Większa złożoność. |
| Silny obrzęk twarzy, gorączka, szczękościsk | callback | Może wymagać pilnego trybu. |

## Pakiety i wizyty łączone

| Opis pacjenta | Czas | Reguła |
| --- | ---: | --- |
| Konsultacja plus EKG | 60 | Nie łączyć jako 30, chyba że lokalna procedura tak mówi. |
| Konsultacja plus USG jednej okolicy | 60 | Badanie i omówienie. |
| Konsultacja plus spirometria | 60 | Badanie wymaga przygotowania i interpretacji. |
| Konsultacja plus pobranie krwi | 60 | Jeśli podczas tej samej wizyty. |
| Dwie różne konsultacje specjalistyczne | callback | Wymaga osobnych zasobów/personelu. |
| Kilka badań technicznych w jednym dniu | 90 | Jeśli mają być w jednym bloku i w jednej pracowni. |
| Przegląd zdrowia z badaniami, EKG i omówieniem | 120 | Pakiet kompleksowy. |
| Pacjent nie wie, jaką usługę wybrać | callback | Lepiej oddzwonić niż błędnie zarezerwować zasób. |

## Zasady podnoszenia i obniżania czasu

Podnieś czas o jeden poziom, maksymalnie do 120 minut, jeśli:
- pacjent jest nowy w placówce i mówi o długiej historii choroby,
- pacjent ma wiele wyników lub wypis ze szpitala,
- pacjent chce załatwić kilka spraw na jednej wizycie,
- wizyta obejmuje konsultację i badanie,
- pacjent jest dzieckiem, osobą starszą lub potrzebuje więcej czasu na komunikację,
- pacjent mówi o procedurze zabiegowej, opatrunku, obserwacji albo zgodzie.

Nie obniżaj czasu tylko dlatego, że pacjent prosi o "krótką wizytę", jeśli opis wskazuje na procedurę lub kilka problemów.

Możesz utrzymać 30 minut, jeśli:
- pacjent mówi o jednej prostej sprawie,
- chodzi o rutynową kontrolę stabilnego leczenia,
- chodzi o pojedynczy wynik, receptę, skierowanie lub proste badanie techniczne,
- nie ma sygnałów alarmowych i nie ma wielu tematów.

## Zasady dla niepewności

Jeśli nie można rozpoznać rodzaju wizyty, ale pacjent podał preferencje terminu, zwróć 30 minut z niską pewnością lub poproś o kontakt telefoniczny.

Jeśli pacjent podał rodzaj problemu, ale nie podał dnia ani okna czasowego, można zaproponować pierwszy wolny slot tylko wtedy, gdy system demonstracyjny tak działa. W przeciwnym razie ustaw `requires_human_callback=true`.

Jeśli pacjent podał sprzeczne preferencje, np. "wtorek po 10, ale nie wtorek" albo "rano po 16", ustaw `requires_human_callback=true`.

Jeśli pacjent podał konkretny termin, który jest zajęty, scheduler nie powinien wybierać innego dnia bez zgody. Odpowiedź: kontakt telefoniczny lub prośba o inny termin.

## Przykłady interpretacji

Pacjent: "Boli mnie gardło i mam gorączkę, najlepiej wtorek po 10."
Reguła: infekcja dorosłego, 30 minut, preferowany wtorek po 10.

Pacjent: "Chciałbym omówić wyniki krwi i wypis ze szpitala po zabiegu."
Reguła: dokumentacja po hospitalizacji, 60 minut.

Pacjent: "Potrzebuję USG brzucha, czasem boli mnie z prawej strony."
Reguła: USG jamy brzusznej, 30 minut, jeśli samo badanie; 60 minut, jeśli konsultacja z omówieniem.

Pacjent: "Mam kaszel od dwóch miesięcy i chciałbym spirometrię."
Reguła: konsultacja pulmonologiczna plus spirometria, 60 minut.

Pacjent: "Chcę sprawdzić wszystkie pieprzyki."
Reguła: przegląd znamion całego ciała, 60 minut.

Pacjent: "Mam ból w klatce piersiowej i duszność."
Reguła: nie umawiać automatycznie; wymaga pilnego kontaktu.

Pacjent: "Potrzebuję recepty na leki, które biorę od lat."
Reguła: 30 minut.

Pacjent: "Pierwsza wizyta u endokrynologa, mam dużo wyników tarczycy i cukru."
Reguła: 60 minut.

Pacjent: "Chcę zrobić krzywą cukrową."
Reguła: 120 minut.

Pacjent: "Dziecko ma wysypkę i gorączkę, ale oddycha normalnie."
Reguła: pediatria infekcyjno-skórna, 30 minut, chyba że opis wskazuje ciężki stan.

Pacjent: "Muszę zdjąć szwy po małym zabiegu."
Reguła: 30 minut.

Pacjent: "Mam ranę, trzeba zmienić duży opatrunek i coś się sączy."
Reguła: 60 minut albo callback, jeśli brzmi pilnie.

## Jak placówka ma zastąpić ten dokument

Najłatwiejszy format wymiany:
1. Zostawić nagłówki specjalizacji.
2. W tabelach podmienić nazwy usług, czasy i reguły.
3. Dodać lokalne słowa pacjentów, np. nazwy pakietów, komercyjne nazwy badań, skróty używane w rejestracji.
4. Oznaczyć usługi wymagające konkretnego zasobu, np. USG, zabiegowy, punkt pobrań, pielęgniarka, lekarz specjalista.
5. Oznaczyć usługi, których nie wolno umawiać automatycznie.

Nie należy traktować tego dokumentu jako porady medycznej. To zbiór reguł organizacyjnych dla demo umawiania wizyt.
