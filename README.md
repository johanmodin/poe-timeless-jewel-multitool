# poe-timeless-jewel-recorder
A Path of Exile bot which allows the highly random timeless jewels to be presentable and searchable.


### Processen
1. X whisprar botten och detta avläses i client.txt
2. Botten invitar X (/invite X)
3. Botten väntar på att X kommer till hideout
4. Botten bjuder in X till trade (/tradewith X)
5. Botten väntar på accept
6. Botten väntar på att X sätter in en juvel i windowet (obs: bör initialt begränsa det till en juvel, men senare är det smidigt om man typ kan ge ett helt window med juveler)
7. Botten acceptar
8. Botten öppnar inventory och skill tree
9. Botten plockar upp juvelen från den plats i inventory som den vet att juvelen hamnat på
10. Botten navigerar till övre vänstra hörnet av skillträdet
11. Botten utvärderar varje juvelslot
    1. Navigera till slot (var ska vi - var är vi)
    2. Sätt in juvel i slot
    3. Navigera till varje nod inom radien
    4. Utför teknik för att känna igen vilka stats noden har (OCR?)
    5. Ta upp juvelen
12. Spara mappning t ex med juvelseed (description) -> ```{'slot_1': {'stat_1': '+5 dexterity', 'stat_2': '+5 intelligence', ...}, 'slot_2': {'stat_1': '+5 strength', 'stat_2': '+5 mana', ...}}```
13. Lägg tillbaka juvelen på samma ställe som den togs från
14a. Om X är kvar i arean så tradea tillbaka juvelen (/tradewith X)
14b. Om X har lämnat arean, behåll juvelen (/kick X), eventuellt lägg den i en tab för att inte få full inventory
15. Om X är kvar i party, kicka X (/kick X)

### Tankar
1. Invita folk som vill ha sina juveler checkade: kolla client.txt i Path of Exile\logs. Mappen bör kunna hittas genom att kolla på informationen från poe-processen, t ex PathOfExile_x64Steam.exe.
2. Skillträdet är för stort för att synas på en skärm. Vi kan navigera genom att alltid börja med att dra skillträdet så att vår skärm hamnar i övre vänstra hörnet och sedan utgå därifrån. Så länge vi vet var varje juvel slot finns (x, y) och vi vet var vår skärm är centrerad (x, y) så bör detta gå att göra.
3. Vi måste hålla reda på vår inventory. Vilka slots är lediga? I vilken slot kommer ett item vi får tradeat att hamna? Detta måste vi veta för att tradea tillbaka rätt item. 
