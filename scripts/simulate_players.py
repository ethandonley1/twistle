import sys
import os
import random
from datetime import datetime, timedelta
import names  # pip install names
import uuid
from better_profanity import profanity

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app, db, User, UserStats, GameResult, UserDevice
from config import GAME_CONFIG

# List of country codes for random assignment
COUNTRY_CODES = ['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'ES', 'IT', 'JP', 'BR', 'IN']
DEVICE_TYPES = ['mobile', 'desktop', 'tablet']
BROWSER_TYPES = ['Chrome', 'Firefox', 'Safari', 'Edge']

def generate_user():
    """Generate random user data."""
    unique_id = str(uuid.uuid4())
    full_name = names.get_full_name()
    return dict(
        id_=unique_id,  # Note the underscore to match the create method
        name=full_name,
        email=f"player_{unique_id[:8]}@example.com",
        profile_pic=None  # Add this required parameter
    )

def simulate_game_result(user_id, date):
    """Simulate a single game result with realistic scoring."""
    total_words = 5  # Number of words per game
    words_solved = random.randint(2, total_words)  # Most players solve at least 2 words
    
    # Calculate a realistic score
    base_score = 40  # Base points per word
    time_bonus = random.randint(10, 30)  # Random time bonus
    attempt_bonus = random.randint(5, 20)  # Random attempt bonus
    
    score = words_solved * (base_score + time_bonus + attempt_bonus)
    
    # Sometimes add anagram bonuses
    anagrams_found = random.randint(0, words_solved * 2)
    score += anagrams_found * GAME_CONFIG['anagram_bonus']
    
    return GameResult(
        user_id=user_id,
        score=score,
        words_solved=words_solved,
        total_words=total_words,
        theme="Simulated Theme",
        share_id=str(random.randint(10000000, 99999999)),
        time_taken=random.randint(300, 900),  # 5-15 minutes
        anagrams_found=anagrams_found,
        game_date=date
    )

def create_user_device(user_id, browser_type=None, country=None):
    """Create a random user device record."""
    return UserDevice(
        user_id=user_id,
        ip_address=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
        device_type=random.choice(DEVICE_TYPES),
        browser_type=browser_type or random.choice(BROWSER_TYPES),
        country=country or random.choice(COUNTRY_CODES),
        last_login=datetime.utcnow()
    )

def simulate_players(num_players=50, days_of_history=30):
    """Simulate multiple players over a period of time."""
    with app.app_context():
        print(f"Simulating {num_players} players over {days_of_history} days...")
        
        for i in range(num_players):
            try:
                # Create user with valid parameters
                user_data = generate_user()
                print(f"Attempting to create user with data: {user_data}")
                user = User.create(**user_data)
                print(f"Created user {i+1}/{num_players}: {user.name} (ID: {user.id})")
                
                # Create device info with random browser and country
                device = create_user_device(
                    user.id,
                    browser_type=random.choice(BROWSER_TYPES),
                    country=random.choice(COUNTRY_CODES)
                )
                db.session.add(device)
                
                # Initialize stats
                stats = UserStats(
                    user_id=user.id,
                    games_played=0,
                    total_score=0,
                    best_score=0,
                    avg_score=0,
                    total_words_solved=0,
                    total_anagrams_found=0,
                    streak=0
                )
                
                # Simulate games over the past X days
                current_streak = 0
                last_played = None
                
                for day in range(days_of_history):
                    # 70% chance to play on any given day
                    if random.random() < 0.7:
                        game_date = datetime.utcnow() - timedelta(days=day)
                        game = simulate_game_result(user.id, game_date)
                        db.session.add(game)
                        
                        # Update stats
                        stats.games_played += 1
                        stats.total_score += game.score
                        stats.best_score = max(stats.best_score, game.score)
                        stats.avg_score = stats.total_score / stats.games_played
                        stats.total_words_solved += game.words_solved
                        stats.total_anagrams_found += game.anagrams_found
                        
                        # Update streak
                        if last_played and (last_played - game_date).days <= 1:
                            current_streak += 1
                        else:
                            current_streak = 1
                        
                        last_played = game_date
                
                stats.streak = current_streak
                stats.last_played = last_played
                db.session.add(stats)
                
                # Commit changes for each user
                db.session.commit()
            except Exception as e:
                print(f"Error creating user {i+1}: {str(e)}")
                continue
        
        print("Simulation complete!")

if __name__ == "__main__":
    # Install required package
    if os.system("pip install names") != 0:
        print("Failed to install required package 'names'")
        sys.exit(1)
    
    simulate_players(num_players=1050, days_of_history=30)