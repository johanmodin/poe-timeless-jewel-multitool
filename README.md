# poe-timeless-jewel-multitool
A Path of Exile timeless jewel analyzing bot and simple jewel search site which allows the highly random timeless jewels to be stored and presented. 

The application is able to analyze timeless jewels. This is done by, for every jewel in your inventory, automatically going through all of the sockets and performing OCR on every socket node to reveal how the jewel transforms the node. The data is stored in a Mongo database to enable searching through the thousands of possible jewel-socket instances for just the stats you're looking for.

[![Tool Demonstration](https://img.youtube.com/vi/5PHUHtf39yA/0.jpg)](https://www.youtube.com/watch?v=5PHUHtf39yA)

  *A YouTube preview of the tool's basic features*


A single jewel analysis consisting of analyzing 21 socket instances, around 1500 nodes and many thousands of mods takes around 240 seconds, though this will vary depending on how many cores you can spare for the OCR (measured with 6 cores).

NOTICE: Although this tool is benevolent in the manner that it does not help you kill monsters or make you richer directly in any way, performing timed actions and automated mouse movements does violate Path of Exile's terms and is bannable. 

### Requirements
- Python 3.x (tested with 3.7)
- Tesseract (tested with 5.0.0 alpha 20190708)
- MongoDB
- Python packages as specified by `requirements.txt`

### Setup
(0. If you're new to Python on Windows, I recommend [downloading Anaconda](https://www.anaconda.com/distribution/#download-section) and [setting up a virtual environment](https://uoa-eresearch.github.io/eresearch-cookbook/recipe/2014/11/20/conda/))
1. `pip3 install -r requirements.txt`
2. Install tesseract [as per the instructions](https://github.com/UB-Mannheim/tesseract/wiki) (make sure that tesseract is in your PATH)
3. Move the tesseract poe tesseract config file (courtesy of klayveR) located in *data/tesseract* to the Tesseract config folder 
4. [Install](https://www.mongodb.com/download-center/community) and [start](https://docs.mongodb.com/v3.2/tutorial/install-mongodb-on-windows/#start-mongodb) a MongoDB server
5. If you want to search through a lot of jewels for one with the correct stats, you should install the accompanying database by extracting `database.json` from `database.zip` and importing it to your Mongo database by running `mongoimport --db project_timeless --collection jewels --file database.json`, this will allow you to search roughly 700 jewel instances
6. Set your resolution in the config.yml. The bot will currently only work for the 2560x1440 and 1920x1080 resolutions. 
7. Make sure your Path of Exile key config is pretty standard, e.g. inventory on "i", nothing bound on "c", skill tree on "p".


### Usage
#### Bot
(0. Have a character with all of the tree's sockets allocated)
1. Make sure the skill tree does not have the ascendancy blob up and is maximally zoomed out.
2. Fill your inventory with jewels you want to search. 
3. Close all ingame windows. No inventory or other windows should be open. Chat should be off. 
4. Run `python3 run.py` and tab into the game.
5. The bot will automatically socket the jewels in your inventory into every socket and store all of the affected nodes.
6. The bot can be stopped by pressing the exit_hotkey button as defined in the config, which defaults to F4.

Additionally, the bot may be set up to receive jewels through trade from players whispering to it by uncommenting the commented lines in the loop method in bot/bot.py. However, as a single jewel takes roughly 5 minutes to analyze, a full inventory of jewels would have the trader waiting 5 hours for his jewels back. Thus, this feature is not activated by default. Instead, the bot will by default solely analyze the jewels in the character's inventory. This feature is activated by setting accept_trades in the config file to True.

The bot does not store information on how the key stones are transformed.

#### Site
A (very) simple site for searching through the database of jewels for specific mods is available in the site folder. It is run with `python3 run_site.py` and hosted [locally](http://127.0.0.1:8080). It allows searching for mods by comparing the levenshtein distance to known mods as well as weighting them such that mods with widely different value magnitudes can be summed together in a meaningful way. 

Additionally, there is a feature for showing the latest jewel additions to the database. The mods shown in green when using this feature are the jewel's mods that are the most interesting based on a simple metric. This metric is simply the factor of how much greater that mod's value is than the average value of that mod, based on all jewels in the database. For example, if a jewel has a sum of 120% to Melee Critical Multiplier and the average jewel with that mod has, say, 40% to Melee Critical Multiplier, that mod would receive a score of 3. The mods displayed with a green background are the ones that had the highest such scores.


![alt text](https://github.com/johanahlqvist/poe-timeless-jewel-recorder/blob/master/site_example.png)

### Contributing to the db
If you have found and analyzed a sizeable amount of new jewels and wish to contribute to the database, you are more than welcome to upload your database to the repository! By doing this, we will eventually be able to get a complete map of all possible jewels. To do this, follow the few, simple steps outlined below.
1. Get the newest version of the database from this repository (i.e. the database.zip file) and extract the database.json from the zip-file
2. Import the repository's database into your database by performing the same command as in the setup. `mongoimport --db project_timeless --collection jewels --file database.json`
3. Delete the old `database.json` file and dump the updated database to a new json-file by running `mongoexport --db project_timeless --collection jewels --out database.json`
4. Zip the `database.json` file and either 1) send it directly to me (ponen) in the [Historic Bazaar discord server](https://discord.gg/yWfZNHA) or 2. if you're into git, perform a pull request with the new database

