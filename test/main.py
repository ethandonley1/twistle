import json
import random
from game import play_game

if __name__ == "__main__":
    try:
        with open('src/data/games.json', 'r') as file:
            games_data = json.load(file)
    except FileNotFoundError:
        print("Error: games.json not found.")
        exit()
    
    #Choose a random game from the JSON data
    random_game = random.choice(games_data)

    play_game(random_game)
