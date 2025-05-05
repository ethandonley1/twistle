"""
Twistle - A word jumble game built with Flask
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user
from flask_migrate import Migrate
from auth import login_manager, client, get_google_provider_cfg
import random
import json
import os
import time
from datetime import datetime, timedelta
import uuid
import nltk
from nltk.corpus import words
from config import GAME_CONFIG, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
import requests
from db import db, User, UserStats, GameResult, UserDevice
from better_profanity import profanity
import re

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth without HTTPS in dev

# Create database directory if it doesn't exist
db_dir = os.path.join(os.path.expanduser('~'), 'twistle')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(db_dir, "twistle.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)

db.init_app(app)
migrate = Migrate(app, db)
login_manager.init_app(app)

# Configure profanity filter - add this after other configurations
profanity.load_censor_words()

def ensure_db_permissions():
    """Ensure database file and directory have proper permissions."""
    db_dir = os.path.join(os.path.expanduser('~'), 'twistle')
    db_file = os.path.join(db_dir, 'twistle.db')
    
    # Ensure directory exists and has proper permissions
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, mode=0o755)
    else:
        os.chmod(db_dir, 0o755)
    
    # Ensure database file has proper permissions if it exists
    if os.path.exists(db_file):
        os.chmod(db_file, 0o644)

with app.app_context():
    ensure_db_permissions()
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Sample game data - in a real app, this would come from a database
# Load game data from a JSON file
with open('src/data/games.json', 'r') as file:
    SAMPLE_GAMES = json.load(file)

# Load NLTK words corpus for word validation
nltk.download('words')
english_words = set(words.words())

def is_valid_word(word):
    """Check if a word is valid (exists in the English dictionary)."""
    return word.lower() in english_words

def is_valid_anagram(word1, word2):
    """Check if two words are anagrams of each other."""
    return sorted(word1.lower()) == sorted(word2.lower()) and is_valid_word(word1) and is_valid_word(word2)

def jumble_word(word):
    """Jumbles the letters of a word."""
    shuffled_word = list(word)
    random.shuffle(shuffled_word)
    # Make sure the jumbled word is different from the original
    while ''.join(shuffled_word) == word:
        random.shuffle(shuffled_word)
    return ''.join(shuffled_word)

def get_today_game(random_mode=False):
    """Returns today's game based on date or randomly if random_mode is True."""
    if random_mode:
        game = random.choice(SAMPLE_GAMES)
    else:
        today_date = datetime.now().strftime('%Y-%m-%d')
        game = random.choice(SAMPLE_GAMES)
        random.seed()
        
    # Create sorted list of (word, hint) tuples based on word length
    sorted_words = sorted(game['daily_words'].items(), key=lambda x: len(x[0]))
    
    # Add jumbled versions of each word
    game_data = game.copy()
    game_data['daily_words'] = dict(sorted_words)  # Convert back to dict
    game_data['jumbled_words'] = [jumble_word(word) for word in game_data['daily_words'].keys()]
    
    return game_data

def init_game_session():
    """Initialize a new game session."""
    game_data = get_today_game(random_mode=GAME_CONFIG['random_mode'])
    
    # Track if user is logged in
    session['is_logged_in'] = current_user.is_authenticated
    session['user_id'] = current_user.id if current_user.is_authenticated else None
    
    session['game_id'] = game_data['id']
    session['daily_theme'] = game_data['daily_theme']
    session['theme_reflection'] = game_data['theme_reflection']
    session['daily_words'] = list(game_data['daily_words'].keys())  # Store words as list
    session['word_hints'] = list(game_data['daily_words'].values())  # Store hints as list
    session['jumbled_words'] = game_data['jumbled_words']
    session['current_word_index'] = 0
    session['score'] = 0
    session['results'] = []  # To store results for each word
    session['game_start_time'] = time.time()
    session['word_start_time'] = time.time()  # Track when each word started
    session['word_time_remaining'] = GAME_CONFIG['word_time_limit']  # Track remaining time for current word
    session['attempt_number'] = 1
    session['hint_revealed'] = False
    session['game_completed'] = False
    session['shuffles_remaining'] = GAME_CONFIG['shuffle_limit']  # Add shuffle tracking
    session['used_anagrams'] = []  # Add this line to track used anagrams
    session['time_boost_available'] = True  # Add this line
    
    # Generate a unique game ID for sharing
    session['share_id'] = str(uuid.uuid4())[:8]

def calculate_score(time_remaining, attempt_number, word_index):
    """Calculate the score for a word based on time remaining, attempts, and word index."""
    time_bonus = time_remaining
    attempt_bonus = (4 - attempt_number) * 10
    # word_bonus = word_index * 2  # More points for harder words
    return 40 + time_bonus + attempt_bonus

def get_redirect_uri():
    """Get the appropriate redirect URI based on the request host."""
    # Strip port from host if present
    host = request.host.split(':')[0]
    port = ':5000' if app.debug else ''
    scheme = 'http' if app.debug else 'https'
    return f"{scheme}://{host}{port}/login/callback"

# Add these helper functions at the top of your file
def get_client_ip():
    """Get client IP address."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def get_device_type():
    """Determine device type from user agent."""
    user_agent = request.user_agent.string.lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        return 'mobile'
    elif 'tablet' in user_agent or 'ipad' in user_agent:
        return 'tablet'
    return 'desktop'

def get_browser_type():
    """Determine browser type from user agent."""
    user_agent = request.user_agent.string.lower()
    if 'firefox' in user_agent:
        return 'Firefox'
    elif 'chrome' in user_agent:
        return 'Chrome'
    elif 'safari' in user_agent:
        return 'Safari'
    elif 'edge' in user_agent:
        return 'Edge'
    return 'Other'

def get_country_from_ip(ip_address):
    """Get country code from IP address using ipapi.co service."""
    try:
        
        response = requests.get(f'https://ipapi.co/{ip_address}/country/', timeout=2)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return 'UN'  # Unknown/fallback country code

def get_country_flag(country_code):
    """Convert country code to flag emoji."""
    if country_code in ['UN', 'Undefined'] or not country_code:
        return '🌐'  # Globe emoji for unknown
    # Convert country code to flag emoji using regional indicator symbols
    return ''.join(chr(ord('🇦') + ord(c.upper()) - ord('A')) for c in country_code)

def validate_screen_name(name):
    """Validate screen name for length and content."""
    if not name or len(name.strip()) < 2:
        return False, "Screen name must be at least 2 characters long."
    
    if len(name) > 20:
        return False, "Screen name cannot be longer than 20 characters."
    
    # Check for profanity in the name, including concatenated words
    if profanity.contains_profanity(name) or any(str(slur) in name.lower() for slur in profanity.CENSOR_WORDSET):
        return False, "Please choose an appropriate screen name."
    
    if any(char * 3 in name for char in name):
        return False, "Screen name contains too many repeated characters."
    
    if not all(c.isalnum() or c.isspace() or c in '.-_' for c in name):
        return False, "Screen name can only contain letters, numbers, spaces, and basic punctuation."
    
    return True, ""

@app.route('/')
def index():
    """Main game page."""
    # Show start screen if no game is in progress
    if 'game_id' not in session:
        return render_template('start.html')

    # If game is completed, redirect to results
    if session.get('game_completed', False):
        return redirect(url_for('results'))
    
    # If all words have been attempted, redirect to results
    if session.get('current_word_index', 0) >= len(session.get('daily_words', [])):
        session['game_completed'] = True
        return redirect(url_for('results'))
        
    game_data = {
        'current_word_index': session.get('current_word_index', 0),
        'total_words': len(session.get('daily_words', [])),
        'jumbled_word': session.get('jumbled_words', [])[session.get('current_word_index', 0)],
        'word_length': len(session.get('daily_words', [])[session.get('current_word_index', 0)]),
        'score': session.get('score', 0),
        'attempt_number': session.get('attempt_number', 1),
        'remaining_attempts': 3 - session.get('attempt_number', 0) + 1,
        'hint_revealed': session.get('hint_revealed', False),
        'word_hints': session.get('word_hints', ''),
        'words_solved': sum(1 for result in session.get('results', []) if result.get('solved', False)),
        'theme': session.get('daily_theme', ''),
        'shuffle_limit': GAME_CONFIG['shuffle_limit'],
        'shuffles_remaining': session.get('shuffles_remaining', GAME_CONFIG['shuffle_limit']),
        'bonus_time': GAME_CONFIG['bonus_time'],  # Add this line
        'time_boost_available': session.get('time_boost_available', True),  # Add this line
        'time_boost_amount': GAME_CONFIG['time_boost']  # Add this line
    }
    
    return render_template('game.jinja2', game=game_data, config=GAME_CONFIG)

@app.route('/start', methods=['POST'])
def start_game():
    """Initialize and start a new game."""
    init_game_session()
    return redirect(url_for('index'))

@app.route('/login')
def login():
    """Handle Google OAuth login."""
    # Store the page user came from
    session['next'] = request.args.get('next', '/')
    
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=get_redirect_uri(),
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route('/login/callback')
def callback():
    """Handle Google OAuth callback."""
    try:
        # Get authorization code Google sent back
        code = request.args.get("code")
        google_provider_cfg = get_google_provider_cfg()
        token_endpoint = google_provider_cfg["token_endpoint"]

        # Prepare and send request to get tokens
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=get_redirect_uri(),  # Use same redirect URI as login
            code=code,
        )
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        # Parse the tokens
        client.parse_request_body_response(json.dumps(token_response.json()))

        # Get user info from Google
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if userinfo_response.json().get("email_verified"):
            unique_id = userinfo_response.json()["sub"]
            users_email = userinfo_response.json()["email"]
            given_name = userinfo_response.json().get("given_name", "")
            family_name = userinfo_response.json().get("family_name", "")
            picture = userinfo_response.json().get("picture", "")
            
            # Create default name from given name and family initial
            default_name = f"{given_name} {family_name[0]}." if given_name and family_name else users_email.split('@')[0]
            
            # Try to get existing user first
            user = User.query.get(unique_id)
            
            if not user:
                user = User.create(
                    id_=unique_id,
                    name=default_name,
                    email=users_email,
                    profile_pic=picture
                )
            
            # Track device information and login
            try:
                ip_address = get_client_ip()
                device_type = get_device_type()
                browser_type = get_browser_type()
                country = get_country_from_ip(ip_address)
                
                UserDevice.create_or_update(
                    user_id=user.id,
                    ip_address=ip_address,
                    device_type=device_type,
                    browser_type=browser_type,
                    country=country
                )
            except Exception as e:
                print(f"Error updating device info: {e}")
            
            login_user(user)
            next_page = session.get('next', '/')
            return redirect(next_page)
            
    except Exception as e:
        print(f"Login error: {e}")
        flash("An error occurred during login. Please try again.", "error")
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Handle logout and clear game session."""
    logout_user()
    session.clear()  # Clear all session data including game progress
    return redirect(url_for('index'))

@app.route('/setup_name')
def setup_name():
    """Show screen name setup page for new users."""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    default_name = request.args.get('default_name', current_user.name)
    next_url = request.args.get('next', '/')
    
    return render_template('setup_name.html', 
                         default_name=default_name,
                         next_url=next_url)

@app.route('/set_screen_name', methods=['POST'])
def set_screen_name():
    """Handle screen name submission."""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    screen_name = request.form.get('screen_name', '').strip()
    next_url = request.form.get('next', '/')
    
    # Validate screen name
    is_valid, error_message = validate_screen_name(screen_name)
    
    if not is_valid:
        flash(error_message, 'error')
        return redirect(url_for('setup_name', 
                              default_name=current_user.name,
                              next=next_url))
    
    try:
        # Update user's name
        current_user.name = screen_name
        db.session.commit()
        flash('Screen name updated successfully!', 'success')
    except Exception as e:
        flash('An error occurred while updating your screen name.', 'error')
        return redirect(url_for('setup_name', 
                              default_name=current_user.name,
                              next=next_url))
    
    return redirect(next_url)

@app.route('/check_guess', methods=['POST'])
def check_guess():
    """Check guess or handle retry."""
    if request.form.get('action') == 'retry':
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        data = request.get_json()
        guess = data.get('guess', '').lower().strip()
        elapsed_time = int(time.time() - session.get('word_start_time', time.time()))
        time_remaining = max(0, session.get('word_time_remaining', GAME_CONFIG['word_time_limit']) - elapsed_time)
        
        current_index = session.get('current_word_index', 0)
        correct_word = session.get('daily_words', [])[current_index]
        attempt = session.get('attempt_number', 1)
        
        is_correct = guess == correct_word

        is_anagram = is_valid_anagram(guess, correct_word)
        
        result = {
            'is_correct': is_correct,
            'is_anagram': is_anagram,
            'correct_word': correct_word,
            'time_remaining': time_remaining,
            'attempt': attempt,
            'feedback': []
        }
        
        # Generate letter-by-letter feedback for visualization
        for i in range(min(len(guess), len(correct_word))):
            if guess[i] == correct_word[i]:
                result['feedback'].append({'letter': guess[i], 'status': 'correct'})
            else:
                result['feedback'].append({'letter': guess[i], 'status': 'incorrect'})
        
        if is_correct:
            points = calculate_score(time_remaining, attempt, current_index)
            session['score'] = session.get('score', 0) + points
            result['points_earned'] = points
            result['new_score'] = session.get('score')
            
            session['results'].append({
                'word': correct_word,
                'jumbled': session.get('jumbled_words', [])[current_index],
                'solved': True,
                'attempts': attempt,
                'time_taken': GAME_CONFIG['word_time_limit'] - time_remaining,
                'points': points
            })
            
            # Don't increment index here, let next_word handle it
            session['word_start_time'] = time.time()
            session['word_time_remaining'] = GAME_CONFIG['word_time_limit']
            session['attempt_number'] = 1
            session['hint_revealed'] = False

        elif is_anagram:
            # Check if this anagram was already used
            used_anagrams = session.get('used_anagrams', [])
            if guess in used_anagrams:
                result['already_used'] = True
                result['is_anagram'] = False  # Don't treat it as a valid anagram
            else:
                # Add the anagram to used list
                used_anagrams.append(guess)
                session['used_anagrams'] = used_anagrams
                
                # Store the anagram result
                session['results'].append({
                    'word': correct_word,
                    'jumbled': session.get('jumbled_words', [])[current_index],
                    'solved': False,
                    'attempts': attempt,
                    'time_taken': GAME_CONFIG['word_time_limit'] - time_remaining,
                    'points': GAME_CONFIG['anagram_bonus'],
                    'is_anagram': True,
                    'anagram_word': guess  # Store the actual anagram word found
                })
                
                # Add anagram bonus points to the response
                result['points_earned'] = GAME_CONFIG['anagram_bonus']
                result['new_score'] = session.get('score', 0) + GAME_CONFIG['anagram_bonus']
                
                # Don't increment index here, let next_word handle it
                session['word_start_time'] = time.time()
                session['word_time_remaining'] = GAME_CONFIG['word_time_limit'] + GAME_CONFIG['bonus_time']  # Give extra time for anagram
                session['score'] = result['new_score']  # Update the session score
                session['attempt_number'] = attempt # Do not increment attempt
                session['hint_revealed'] = True
            
        else:
            session['attempt_number'] = attempt + 1
            
            # Auto-reveal hint after second attempt
            if session['attempt_number'] >= 3 and not session.get('hint_revealed', False):
                session['hint_revealed'] = True
                result['hint'] = session.get('word_hints', [])[current_index]
                result['show_hint'] = True
            
            if attempt >= 3:
                session['results'].append({
                    'word': correct_word,
                    'jumbled': session.get('jumbled_words', [])[current_index],
                    'solved': False,
                    'attempts': 3,
                    'time_taken': GAME_CONFIG['word_time_limit'] - time_remaining,
                    'points': 0
                })
                
                # Don't increment index here, let next_word handle it
                session['word_start_time'] = time.time()
                session['word_time_remaining'] = GAME_CONFIG['word_time_limit']
                session['attempt_number'] = 1
                session['hint_revealed'] = False
                
                result['out_of_attempts'] = True
            
        return jsonify(result)

@app.route('/reveal_hint', methods=['POST'])
def reveal_hint():
    """Reveal the category hint."""
    current_index = session.get('current_word_index', 0)
    current_hint = session.get('word_hints', [])[current_index]
    session['hint_revealed'] = True
    return jsonify({
        'hint': current_hint,
        'success': True
    })

@app.route('/sync_timer', methods=['POST'])
def sync_timer():
    """Synchronize client timer with server timer."""
    if 'word_start_time' not in session:
        session['word_start_time'] = time.time()
        session['word_time_remaining'] = GAME_CONFIG['word_time_limit']

    elapsed = int(time.time() - session['word_start_time'])
    time_remaining = max(0, session['word_time_remaining'] - elapsed)

    return jsonify({
        'time_remaining': time_remaining,
        'server_time': time.time()
    })

@app.route('/check_timer', methods=['GET'])
def check_timer():
    """Check if the timer has expired."""
    if 'word_start_time' not in session:
        session['word_start_time'] = time.time()
        session['word_time_remaining'] = GAME_CONFIG['word_time_limit']

    elapsed = int(time.time() - session['word_start_time'])
    time_remaining = max(0, session['word_time_remaining'] - elapsed)
    
    # Auto-reveal hint if time is low or attempts are high
    should_show_hint = (
        time_remaining <= 10 or 
        session.get('attempt_number', 1) >= 3
    ) and not session.get('hint_revealed', False)
    
    if should_show_hint:
        session['hint_revealed'] = True
        current_index = session.get('current_word_index', 0)
        current_hint = session.get('word_hints', [])[current_index]
    else:
        current_hint = None
    
    return jsonify({
        'time_remaining': time_remaining,
        'time_up': time_remaining == 0,
        'hint_available': should_show_hint,
        'hint': current_hint
    })

@app.route('/shuffle_word', methods=['POST'])
def shuffle_word():
    """Handle word shuffle requests."""
    if session.get('shuffles_remaining', 0) <= 0:
        return jsonify({
            'success': False,
            'message': 'No shuffles remaining'
        }), 400

    current_index = session.get('current_word_index', 0)
    current_word = session.get('daily_words', [])[current_index]
    current_jumbled = session.get('jumbled_words', [])[current_index]
    
    # Keep shuffling until we get a different arrangement
    new_jumbled = jumble_word(current_word)
    while new_jumbled == current_jumbled:
        new_jumbled = jumble_word(current_word)
    
    # Update session
    jumbled_words = session.get('jumbled_words', [])
    jumbled_words[current_index] = new_jumbled
    session['jumbled_words'] = jumbled_words
    session['shuffles_remaining'] = session.get('shuffles_remaining', 0) - 1

    return jsonify({
        'success': True,
        'shuffled_word': new_jumbled,
        'shuffles_remaining': session.get('shuffles_remaining', 0)
    })

@app.route('/boost_time', methods=['POST'])
def boost_time():
    """Handle time boost requests."""
    if not session.get('time_boost_available', False):
        return jsonify({
            'success': False,
            'message': 'Time boost already used'
        }), 400

    # Add time to current word
    current_time = session.get('word_time_remaining', GAME_CONFIG['word_time_limit'])
    session['word_time_remaining'] = current_time + GAME_CONFIG['time_boost']
    session['time_boost_available'] = False

    return jsonify({
        'success': True,
        'new_time': session['word_time_remaining'],
        'boost_amount': GAME_CONFIG['time_boost']
    })

@app.route('/next_word', methods=['POST'])
def next_word():
    """Move to the next word."""
    current_index = session.get('current_word_index', 0)
    session['current_word_index'] = current_index + 1
    session['word_start_time'] = time.time()  # Reset word timer
    session['word_time_remaining'] = GAME_CONFIG['word_time_limit']
    session['attempt_number'] = 1
    session['hint_revealed'] = False
    session['shuffles_remaining'] = GAME_CONFIG['shuffle_limit']  # Reset shuffles for new word
    
    if session.get('current_word_index', 0) >= len(session.get('daily_words', [])):
        session['game_completed'] = True
        return redirect(url_for('results'))
    
    return redirect(url_for('index'))

@app.route('/results')
def results():
    """Show game results and save stats if logged in."""
    if not session.get('game_completed', False) and 'game_id' in session:
        # If game is in progress but not completed, redirect to game
        if session.get('current_word_index', 0) < len(session.get('daily_words', [])):
            return redirect(url_for('index'))
    
    # Calculate statistics
    results = session.get('results', [])
    words_solved = sum(1 for result in results if result.get('solved', False))
    total_words = len(session.get('daily_words', []))
    total_possible_score = sum(calculate_score(GAME_CONFIG['word_time_limit'], 1, i) for i in range(len(session.get('daily_words', []))))
    
    # Group results by target word
    word_results = {}
    for result in session.get('results', []):
        word = result['word']
        if word not in word_results:
            word_results[word] = {
                'word': word,
                'solved': False,
                'attempts': 0,
                'time_taken': 0,
                'anagrams': []
            }
            
        if result.get('is_anagram'):
            word_results[word]['anagrams'].append(result['anagram_word'])
        else:
            word_results[word].update({
                'solved': result.get('solved', False),
                'attempts': result.get('attempts', 0),
                'time_taken': result.get('time_taken', 0)
            })

    # Convert back to list maintaining word order
    enhanced_results = []
    for word in session.get('daily_words', []):
        if word in word_results:
            enhanced_results.append(word_results[word])
    
    game_data = {
        'score': session.get('score', 0),
        'max_score': total_possible_score,
        'words_solved': words_solved,
        'total_words': total_words,
        'theme': session.get('daily_theme', ''),
        'theme_reflection': session.get('theme_reflection', ''),
        'results': enhanced_results,
        'share_id': session.get('share_id', ''),
        'date': datetime.now().strftime('%B %d, %Y'),
        'is_logged_in': session.get('is_logged_in', False),
        'time_limit': GAME_CONFIG['word_time_limit'],
        'total_anagrams': sum(len(result.get('anagrams', [])) for result in enhanced_results)
    }

    if current_user.is_authenticated:
        # Only create game result if it hasn't been created yet
        existing_result = GameResult.query.filter_by(share_id=session.get('share_id')).first()
        if not existing_result:
            # Calculate game stats
            total_time = int(time.time() - session.get('game_start_time', time.time()))
            anagrams_found = sum(len(result.get('anagrams', [])) for result in enhanced_results)
            
            # Create game result
            game_result = GameResult(
                user_id=current_user.id,
                score=session.get('score', 0),
                words_solved=words_solved,
                total_words=total_words,
                theme=session.get('daily_theme', ''),
                share_id=session.get('share_id', ''),
                time_taken=total_time,
                anagrams_found=anagrams_found
            )
            db.session.add(game_result)
            
            # Get or create user stats
            stats = UserStats.query.filter_by(user_id=current_user.id).first()
            if not stats:
                stats = UserStats(
                    user_id=current_user.id,
                    games_played=0,
                    total_score=0,
                    total_words_solved=0,
                    best_score=0,
                    avg_score=0,
                    total_anagrams_found=0,
                    streak=0,
                    last_played=None
                )
                db.session.add(stats)
                db.session.flush()  # Ensure stats object is created in db
            
            # Update stats
            new_total_score = stats.total_score + session.get('score', 0)
            new_games_played = stats.games_played + 1
            
            stats.games_played = new_games_played
            stats.total_score = new_total_score
            stats.total_words_solved += words_solved
            stats.best_score = max(stats.best_score, session.get('score', 0))
            stats.avg_score = new_total_score / new_games_played
            stats.total_anagrams_found += anagrams_found
            stats.last_played = datetime.utcnow()
            
            # Update streak
            last_game = GameResult.query.filter_by(user_id=current_user.id)\
                .order_by(GameResult.game_date.desc())\
                .first()
                
            if last_game and last_game.game_date:
                days_diff = (datetime.utcnow() - last_game.game_date).days
                if days_diff <= 1:
                    stats.streak += 1
                else:
                    stats.streak = 1
            else:
                stats.streak = 1
                
            db.session.commit()

    return render_template('results.html', game=game_data)

@app.route('/help')
def help_page():
    """Help page with game instructions."""
    return render_template('help.html')

@app.route('/stats')
def stats():
    """Show real player statistics."""
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=url_for('stats')))
        
    stats = UserStats.query.filter_by(user_id=current_user.id).first()
    recent_games = GameResult.query.filter_by(user_id=current_user.id)\
        .order_by(GameResult.game_date.desc())\
        .limit(5)\
        .all()
    
    stats_data = {
        'games_played': stats.games_played if stats else 0,
        'avg_score': round(stats.avg_score if stats else 0),
        'best_score': stats.best_score if stats else 0,
        'streak': stats.streak if stats else 0,
        'total_anagrams': stats.total_anagrams_found if stats else 0,
        'best_performances': [{
            'date': game.game_date.strftime('%B %d, %Y'),
            'score': game.score,
            'words_solved': game.words_solved,
            'theme': game.theme,
            'anagrams': game.anagrams_found
        } for game in recent_games]
    }
    
    return render_template('stats.html', stats=stats_data)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handle user settings."""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'screen_name' in request.form:
            new_name = request.form['screen_name'].strip()
            is_valid, error_message = validate_screen_name(new_name)
            
            if is_valid:
                try:
                    current_user.name = new_name
                    db.session.commit()
                    flash('Screen name updated successfully!', 'success')
                except Exception as e:
                    flash('An error occurred while updating your screen name.', 'error')
            else:
                flash(error_message, 'error')

    return render_template('settings.html')

@app.route('/reset_game', methods=['POST'])
def reset_game():
    """Reset the game (for testing)."""
    session.clear()
    return redirect(url_for('index'))

@app.route('/share/<share_id>')
def shared_game(share_id):
    """View shared game results."""
    # In a real app, you'd retrieve the shared game from a database
    # For demo purposes, we'll just show a placeholder
    return render_template('shared.html', share_id=share_id)

@app.route('/leaderboard')
def leaderboard():
    """Show global leaderboard with user's position."""
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=url_for('leaderboard')))
    
    # Get all users' stats with country information
    all_stats = UserStats.query.join(User)\
        .outerjoin(UserDevice)\
        .with_entities(
            User.name,
            User.id,
            UserStats.best_score,
            UserStats.total_anagrams_found,
            UserStats.games_played,
            UserDevice.country
        )\
        .group_by(User.id)\
        .order_by(UserStats.best_score.desc())\
        .all()
    
    # Find current user's rank and prepare player lists
    user_rank = None
    top_players = []
    user_data = None
    
    # Process all players
    for i, stats in enumerate(all_stats, 1):
        # Add to top players if in top 5
        if i <= 5:
            top_players.append({
                'rank': i,
                'name': stats.name,
                'score': stats.best_score,
                'anagrams': stats.total_anagrams_found,
                'games': stats.games_played,
                'is_current_user': stats.id == current_user.id,
                'country_flag': get_country_flag(stats.country)
            })
        
        # Store current user's data
        if stats.id == current_user.id:
            user_rank = i
            user_data = {
                'rank': i,
                'name': stats.name,
                'score': stats.best_score,
                'anagrams': stats.total_anagrams_found,
                'games': stats.games_played,
                'is_current_user': True,
                'country_flag': get_country_flag(stats.country)
            }
    
    return render_template('leaderboard.html',
                         top_players=top_players,
                         user_data=user_data,
                         user_rank=user_rank,
                         total_players=len(all_stats),
                         today=datetime.now().strftime('%B %d, %Y'))

if __name__ == '__main__':
    app.run(debug=True)
