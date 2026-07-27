# Kinesis — příběh jedné tradingové laboratoře

**Formát:** podcastový scénář pro audio/video. Dva hostitelé:
- **Verča** — moderátorka, zvědavá laička, klade otázky, které by položil posluchač.
- **Tom** — stavitel projektu, vysvětluje, co se dělo a proč.

Členěno do kapitol (střižných bloků). Čísla a fakta odpovídají reálné historii projektu (StockAnalyzer → Kinesis, `RESULTS.md`).

---

## Kapitola 1 — Kde to začalo (a co jsme si namlouvali)

**Verča:** Tome, pojďme začít od začátku. Co vlastně ten projekt měl původně dělat?

**Tom:** Původně se to jmenovalo StockAnalyzer a cíl byl docela sebevědomý: postavit systém, který pro každou akcii na burze řekne, jestla půjde nahoru nebo dolů. Cílovka byla šedesát procent úspěšnost predikce. Měli jsme tam všechno — svíčkové formace, grafické patterny, technické indikátory jako RSI a MACD, sentiment zpráv, dokonce i neuronové sítě. Prostě klasická představa „nasypeme data do umělé inteligence a ta nám řekne, co koupit".

**Verča:** A to zní rozumně, ne? Dneska každý mluví o AI na burze.

**Tom:** Zní to rozumně, a taky proto je to tak nebezpečné. Problém je v tom, že na likvidních velkých akciích — tedy přesně tam, kde trh chodí denně miliony lidí a počítačů — už tahle data v ceně jsou. Když si o NVDA přečteš, že má silný sentiment, tak to ví milion dalších lidí ve stejné vteřině. Takže ta informace nemá žádnou ceny. My jsme to ale tehdy nevěděli. Museli jsme si to dokázat sami, na vlastní kůži.

**Verča:** Takže jste prostě začali testovat.

**Tom:** Přesně tak. A tím začala ta nejzajímavější — i když bolestivá — část projektu.

---

## Kapitola 2 — Pád hlavní hypotézy (osm z osmi nic)

**Verča:** Co jste tedy testovali?

**Tom:** Hypotéza zněla: když ty signály chytré zkombinujeme, vznikne nám výhoda. Takže jsme je do sebe míchali — techniku, patterny, sentiment — a každý malý vylepšovák jsme testoval zpětně, backtestem. A pak jsme šli ještě dál: začali jsme zkoušet takzvaná alternativní data.

**Verča:** Co to je?

**Tom:** Jsou to data, co nejsou v ceně tak přímočaře. Krátké prodeje — kdo sází na pokles. Insajderské obchody — kdy management kupuje vlastní akcie. Přiznání společností, fundamenty. Mysleli jsme si: tady bude ta skrytá výhoda, tady nás trh ještě nevidí.

**Verča:** A našla se?

**Tom:** Ne. Ani v jednom. Osm z osmi signálů vyšlo statisticky nulové. Žádná výhoda, kterou by šlo rozumně, opakovatelně zpeněžit. To byl tvrdý moment. Člověk má tendenci si říkat „jen to musíme víc vyladit", ale pravda byla nepříjemná: na velkých likvidních akciích, v denním horizontu, v kombinaci signálů prostě žádná edge není.

**Verča:** To musela být drsná zpráva. Co se s tebou tehdy dělo v hlavě?

**Tom:** Upřímně? Smutek. Tři čtvrtě roku práce a výsledek je „ne". Ale pak přišla úleva. Protože ta odpověď je čistá a pravdivá. Vědět jistotu, že něco nefunguje, je nekonečně cennější než žít v iluzi, že funguje. Mnoho tradingových systémů na světě prostě jen prodává tu iluzi.

---

## Kapitola 3 — Tvrdá pravda a rozhodnutí začít nanovo

**Verča:** Takže co teď? Zahodit všechno?

**Tom:** To byla otázka, kterou jsme si museli odpovědět poctivě. A došli jsme k tomu, že nechceme zahodit celou tu infrastrukturu — backend, stahování dat, backtester, to všechno bylo poctivě postavené. Ale chtěli jsme zahodit ten mylný předpokaz. Tu ideu „predikovat každou akcii zvlášť".

**Verča:** A co místo ní?

**Tom:** Místo ní jsme se podívali na to, co na burze skutečně funguje a je zdokumentované v akademické literatuře. A tam existuje jedna věc, která se drží desítky let: momentum. Tedy pozorování, že věci, co rostou, mají tendenci chvíli růst dál. Z toho vzešel nový projekt. Jmenuje se Kinesis, což je řecky „pohyb".

**Verča:** A proč je tahle идея jiná než to předtím?

**Tom:** Protože předtím jsme se snažili uhodnout každou jednotlivou akcii. Teď vůbec neřešíme predikci. Místo toho se díváme na celý trh, seřadíme ho podle síly trendu a držíme ty nejlepší. Není to křišťálová koule, je to systematický filtr. To je obrovský rozdíl v myšlení.

---

## Kapitola 4 — Jak strategie funguje (čtyři principy)

**Verča:** Rozbal mi to. Jak konkrétně ten „filtr" funguje?

**Tom:** Můžeš si představit, že trh je dlouhá tabulka. Každý den ten systém vezme zhruba tři sta nejlikvidnějších amerických akcií — to je náš univerzum — a seřadí je podle toho, jak moc vystoupaly za poslední rok. Těchto dvanáct měsíců je prostě měřítko síly trendu. A pak držíme jen prvních deset. Největší rostoucí jména.

**Verča:** A když akcie spadne z první desítky?

**Tom:** Tak ji vyměníme za další. To je ten základní mechanismus. Ale samotný výběr je jen první princip. Jsou ještě tři další, a ty jsou vlastně důležitější.

**Verča:** Jaké?

**Tom:** Druhý: každé jméno je naskladno tak, aby mělo stejný risk. Takže prudká, volatile akcie má menší váhu a klidná akcie větší. Nikdo jednotlivec nám neotevře pozici natolik, aby nás zničil. Tomu se říká equal-risk sizing.

**Verča:** To zní rozumně.

**Tom:** Třetí princip je takzvaný regime gate, brána režimu. Když je celý trh pod svým dvousetdenním průměrem — tedy zjednodušeně řečeno, když je medvědí trh — tak prostě přejdeme do hotovosti. Sedíme si na rukou. Proč? Protože i ty nejlepší akcie padají, když padá celý trh. Čtvrtý princip je bear defense, medvědí obrana — k tomu se ještě vrátím, je to naše chlubka.

**Verča:** Takže shrnuto: vybrat silné, držet rovnoměrně, v medvědím trhu couvnout, a mít ještě nějakou obranu.

**Tom:** Přesně. A tady je ten klíčový posun oproti předtím: na velkých denních akciích není výnos v tom, že uhodneš správnou akcii. Výnos je v risk managementu. V tom, jak se postavíš vůči riziku. To je lekce, která nás stála rok hledání, ale stála za to.

---

## Kapitola 5 — Bear defense, aneb co nás zachrání v propadu

**Verča:** Říkal jsi, že bear defense je chlubka. Co přesně dělá?

**Tom:** Představ si, že jedeš po dálnici a řídíš podle toho, jaký je provoz. Když je provoz klidný, můžeš jet rychle. Když se začne dít nečekané věci, volatita stoupá, tak zpomalíš. Bear defense dělá přesně tohle s portfoliem. Sleduje, jak moc celá kniha skáče, a když volatility vylétne, automaticky zmenší expozici.

**Verča:** A ta druhá část?

**Tom:** A druhá část je takový nouzový brzdič: když hodnota portfolia klesne z maxima o víc než určitý práh — dejme tomu o víc než dvanáct procent — tak se expozice přerízne na polovinu. Prostě instinktivní reakce „něco je špatně, couvneme".

**Verča:** A funguje to?

**Tom:** Tady je třeba být poctivý. První verze, kterou jsme měli nastavenou moc agresivně, nám naopak ublížila — brzdila i v době, kdy brzdit neměla, a výsledek byl horší než trh. Museli jsme ji přeladit. A tady se dostáváme k jedné velké a poučné kapitole, protože právě u té obrany se nám stala věc, která nás skoro dostala.

---

## Kapitola 6 — Dramat s daty aneb proč důvěřovat, ale ověřovat

**Verča:** Co se stalo?

**Tom:** Vypadalo to fantasticky. Bear defense se zdál jako dar z nebe — z původního propadu třicet procent nás dostal na osmnáct, a přitom se zdálo, že Sharpeovo číslo zůstalo stejné. Sharpe, pro posluchače, je klíčové měřítko: výnos převedený na jednotku risku. Takže „získat výnos, ale s menším riskem" — to je svatý grál. Oslavovali jsme.

**Verča:** A?

**Tom:** A pak jsem si všiml něčeho divného. Některé akcie měly v datech nesmyslné skoky — jedna firma tam měla zapsaný nárůst tisíc tři sta devadesát pět procent za jediný den. Fyzicky nemožné. Co se stalo: sedm titulů v databázi mělo takzvaná placeholder data, odpadky z toho, jak jsou data dodávána. Špinavá, placatá data, která pak najednou uskočila do reality.

**Verča:** A ta špinavá data nám zkreslila výsledky?

**Tom:** Přesně. A to nejzáludnější na tom je, že nás zkreslila přesně ve prospěch té obrany. Ta placatá data totiž vypadala jako klidné období s nízkou volatilitou, takže obrana reagovala míň, expozice byla vyšší, a výsledek vypadal lépe, než ve skutečnosti byl. Byla to iluze postavená na odpadcích.

**Verča:** Hustý. Co jsi dělal?

**Tom:** Postavil jsem validátor, který každý titul zkontroluje — jestli nemá jednodenní skok větší než osmdesát procent nebo jestli není dlouho placatý — a takové rovnou vyřadí. Opravil jsem stahování dat, aby bralo opravené ceny, naučil systém rozpoznat přejmenované akcie, jako když se Facebook přejmenoval na Meta. Prošel jsem znovu všechno čistými daty. Univerzum se tím změnilo ze tří set dvanácti na tři sta šest čistých titulů.

**Verča:** A po tom čištění… ta obrana pořád fungovala?

**Tom:** Tady je ta poctivá odpověď. Samotný výběr, ten momentum, ano — zůstal silný. Sharpe jedna celá jedna oproti pasivnímu držení nula sedm deset, to je reálné. Ale ta původní obrana byla na čistých datech přeladěná špatně. Musel jsem ji znovu nastavit, jiný parametr — a ten nový, správný, dal Sharpovo číslo jedna celá nula pět, s maximálním propadem minus dvacet celých pět procenta. To je lepší než trh na obou čelních frontách.

**Verča:** Takže lekce zní: nepřestávat ověřovat data.

**Tom:** Datový kvalitativní ověřování je polovina úspěchu. Tenhle projekt mě naučil víc o tom, jak se nezbláznit z vlastních čísel, než o samotném tradingu.

---

## Kapitola 7 — Poctivá věda (PSR0, walk-forward, a ta nevyhnutná hvězdička)

**Verča:** Vzpomínáš, jak jsi říkal, že mnoho systémů jen prodává iluzi. Jak my víme, že naše čísla nejsou taky jen štěstí?

**Tom:** To je ta nejdůležitější otázka, jakou vůbec lze položit. A myslím, že je to to, co mě na tomhle projektu nejvíc baví. Máme na to několik nástrojů. První se jmenuje PSR0 — zjednodušeně to je pravděpodobnost, že naše Sharpovo číslo je skutečně kladné, ne jen náhoda. Když je nad nula celá devadesát pět, je to statisticky signifikantní. My jsme někde kolem nula celá osmdesát devět — tedy slibné, ale ne stoprocentní. Tohle si upřímně přiznáváme.

**Verča:** A co walk-forward?

**Tom:** To je druhý nástroj, a je to klíčový. Nemůžeš ladit parametry na datech, na kterých je pak taky testuješ — to je podvádění. Takže rozdělíš historii na dvě části. Na první půlce si nastavíš strategii, a pak ji otestuješ na té druhé, druhé polovině, kterou strategie nikdy neviděla. A to je ten test reality.

**Verča:** A prošel?

**Tom:** Bear defense prošel pro to, co dělat má — redukuje propad. Ale musíme si přiznat jednu věc, a to je ta nepříjemná hvězdička u celého projektu. My jsme testovali na období, které obsahuje obrovský býčí trh, tenhle AI a polovodičový boom posledních let. To znamená, že část našeho výnosu je prostě tím, že jsme byli v akciích, když akcie rostly. Když jsme strategii rozdělili na půlku, tak ta starší, pomalejší polovina měla Sharpovo číslo nula celá čtyřicet pět, zatímco ta novší, býčí, měla jedna celá třicet pět. To znamená, že je to systém, co funguje v růstu. To je upřímné přiznání.

**Verča:** To je tedy solní. Kolik projektů by tohle nepřiznalo.

**Tom:** A právě proto to přiznáváme. Celá pointa je v tom si neodborně nalhávat. Pokud ti někdo slibuje stabilní zisky bez jediné hvězdičky, tak ti buď lže, nebo sám neví, že lže.

---

## Kapitola 8 — Až dochlípek k uživateli, aneb proč UI/UX bolí

**Verča:** Dobre, takže matematika je poctivá. Ale vraťme se k současnosti. Co se na projektu děje teď, poslední dobou?

**Tom:** Zabýváme se něčím úplně jiným — tím, jak to všechno ukázat člověku. Protože přišla tvrdá realization: klidně máme skvělý backtester, ale když se na to podívá někdo, kdo není kvant, tak neví, co vidí. Sharpe jedna celá nula pět — je to dobrý? Nebo špatný? Target vol nula celá dvacet dva — co to znamená? Byli jsme tak pohlcení čísly, že jsme zapomněli, že číslo bez kontextu je pro člověka k ničemu.

**Verča:** To zní jako něco, co potká každý projekt s technickým jádrem.

**Tom:** Úplně. A řešíme to postupně. Napřed jsme udělali takovou pomůcku — místo abys viděl holé číslo, vidíš rovnou verdikt. Sharpe jedna celá nula pět, silné, lepší než trh, co má nula šedesát devět. Propad minus dvacet procenta, mírný. Každé číslo má teď svůj rámec.

**Verča:** To je fajn. A co ta „laboratoř"?

**Tom:** To je moje oblíbená část. Místo abys měl před sebou formulář s jedenácti poličkama a musel hádat, co které dělá, tak teď můžeš vzít jeden parametr — třeba tu obranu — a nechat ho „přejet" přes celou škálu. A systém ti nakreslí krabici křivek, každou pro jinou hodnotu. Vidíš doslova, jak se mění tvůj kumulovaný majetek, když ten parametr točíš. To je vzdálenost od „nechápu" k „aha, takhle to funguje".

**Verča:** A když chci pochopit i ta slova, co znamenají?

**Tom:** Na to jsme přidali záložku Učit se, jako taková investopedie uvnitř aplikace. Krátké, lidské vysvětlení, co je momentum, co dělá brána režimu, jak číst propad. A u každého parametru je otazník, který tě rovnou navede na správné místo.

**Verča:** Takže projekt dospěl z „co data říkají" až po „jak to člověku vysvětlit".

**Tom:** Přesně tak. A upřímně, ta druhá půlka je těžší než ta první.

---

## Kapitola 9 — Co jsme se naučili (a co by řekl každému, kdo to zkouší)

**Verča:** Závěrečná otázka, Tome. Kdybys měl shrnout, co tě ten projekt naučil, co by to bylo?

**Tom:** První lekce: nezačínej od představy, že chytrý systém uhodne trh. Začíná od poctivé otázky, co na tomhle trhu skutečně funguje, a buď připraven slyšet „nic". Druhá lekce: data lhí. Lehkou rukou, nenápadně, přesně tak, jak nejmíň čekáš. Takže ověřuj, ověřuj, ověřuj. Třetí lekce: risk management není dodatečná myšlenka, je to sám zdroj výnosu. Čtvrtá lekce, a ta nejtvrdší: nejhorší, co můžeš udělat, je sám sebe oklamat laděním parametrů na datech, která pak testuješ. Pátá: každé číslo musí mít rámec, jinak je k ničemu — a to platí pro tebe i pro lidi, kterým to ukazuješ.

**Verča:** A ten cíl, těch šedesát procent, co jsme zmiňovali na začátku?

**Tom:** Ten cíl byl špatně položený. A to je v pořádku. Někdy musíš dojít na konec špatné cesty, abys poznal, kde vůbec ta správná je. Dneska už neříkáme „predikujeme trh". Říkáme „systematicky participujeme na trendech a chráníme se před propady". A to je rozdíl mezi slibováním a reálným engineeringem.

**Verča:** Tome, děkuju. To byl příběh o tom, jak nepřestat ptát se „a opravdu to funguje?" — a proč je tahle otázka ta nejcennější, co v tradingu máš.

**Tom:** Děkuju. A každému, kdo poslouchá: bez ohledu na to, jestlize tvoříte vlastní systém, pamatujte — poctivost k vlastním výsledkům je ta jediná výhoda, kterou nemůže nikdo vzít.

---

*Poznámka pro produkci: celý scénář je možno rozdělit na samostatné epizody po kapitolách (např. 1–3 jako „Příběh", 4–5 jako „Jak to funguje", 6–7 jako „Poctivost", 8 jako „UX", 9 jako závěr). Všechna čísla odpovídají reálné historii projektu zdokumentované v `RESULTS.md`.*
