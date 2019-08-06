# poe-timeless-jewel-recorder
A Path of Exile bot which allows the highly random timeless jewels to be searchable and presentable. Stores all sockets' nodes in a Mongo database along with their random seed and other metadata to enable searching through thousands of possible jewel-socket instances for just the stats you're looking for.

NOTICE: Although this bot does not play the game for you, performing timed actions and automated mouse movements violates Path of Exile's terms and is bannable.


### Setup
1. `pip install -r requirements.txt`
2. Install tesseract [as per the instructions](https://github.com/UB-Mannheim/tesseract/wiki)
3. Move the tesseract poe tesseract config file located in data/tesseract to the tesseract config folder (courtesy of klayveR)
4. Install MongoDB 
5. Check out the config.yml file for configuration. The bot is only tested for working with the 2560x1440 resolution.


### Usage
#### Bot
(0. Have a character with all of the tree's sockets allocated)
1. Make sure the skill tree does not have the ascendancy blob up and is maximally zoomed out.
2. Stand close to your stash. No inventory or other windows should be open.
3. Run `python3 run.py` and tab into the game.
4. The bot will automatically socket the jewel into every socket and record all of the affected nodes.

Additionally, the bot may be set up to receive jewels through trade from players whispering to it by uncommenting the commented lines in the loop method in bot/bot.py. However, as a single jewel takes roughly 5 minutes to analyze, a full inventory of jewels would have the trader waiting 5 hours for his jewels back. Thus, this feature is not activated by default. Instead, the bot will by default solely analyze the jewels in the character's inventory.

#### Site
A (very) simple site for searching through the database of jewels for specific mods is available in the site folder. It is run with `python3 server.py`. 

Currently, the database query only sorts results by text relevance. If a site with this functionality is to be made public, a new database scheme with easier access to summed mod values should be created as this would increase performance and improve search results as the current query only sorts after text relevance, not mod value. 
