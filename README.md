# poe-timeless-jewel-multitool
A Path of Exile bot and basic site which allows the highly random timeless jewels to be searchable and presentable. It goes through all of the sockets and performs OCR on every socket node, after which it stores the data on all sockets' nodes in a Mongo database along with their random seed and other metadata to enable searching through the thousands of possible jewel-socket instances for just the stats you're looking for.

A single jewel analysis consisting of analyzing 21 socket instances, around 1500 nodes and many thousands of mods takes around 240 seconds, though this will vary depending on how many cores you can spare for the OCR (measured with 6 cores).

NOTICE: Although this bot does not play the game for you, performing timed actions and automated mouse movements violates Path of Exile's terms and is bannable.


### Setup
1. `pip install -r requirements.txt`
2. Install tesseract [as per the instructions](https://github.com/UB-Mannheim/tesseract/wiki)
3. Move the tesseract poe tesseract config file located in data/tesseract to the tesseract config folder (courtesy of klayveR)
4. Install and start a [MongoDB server](https://www.mongodb.com/download-center/community)
5. Check out the config.yml file for configuration. The bot is only tested for working with the 2560x1440 resolution.


### Usage
#### Bot
(0. Have a character with all of the tree's sockets allocated)
1. Make sure the skill tree does not have the ascendancy blob up and is maximally zoomed out.
2. Fill your inventory with jewels you want to search. 
3. Close all ingame windows. No inventory or other windows should be open.
4. Run `python3 run.py` and tab into the game.
5. The bot will automatically socket the jewels in your inventory into every socket and record all of the affected nodes.

Additionally, the bot may be set up to receive jewels through trade from players whispering to it by uncommenting the commented lines in the loop method in bot/bot.py. However, as a single jewel takes roughly 5 minutes to analyze, a full inventory of jewels would have the trader waiting 5 hours for his jewels back. Thus, this feature is not activated by default. Instead, the bot will by default solely analyze the jewels in the character's inventory.

The bot does not store information on how the key stones are transformed.

#### Site
A (very) simple site for searching through the database of jewels for specific mods is available in the site folder. It is run with `python3 run_site.py` and hosted [locally](http://127.0.0.1:8080). It allows searching for mods by comparing the levenshtein distance to known mods as well as weighting them such that mods with widely different value magnitudes can be summed together in a meaningful way. 


![alt text](https://github.com/johanahlqvist/poe-timeless-jewel-recorder/blob/master/site_example.png)
