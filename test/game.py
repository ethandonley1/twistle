import random
import time

def jumble_word(word):
    """Jumbles the letters of a word."""
    shuffled_word = list(word)
    random.shuffle(shuffled_word)
    return "".join(shuffled_word)

def color_feedback(index, guess, correct_word):
    """Provides colored feedback for each letter in the guess."""
    feedback = ""
    feedback_score = f"{index+1}. "
    for i in range(len(correct_word)):
        if i < len(guess) and guess[i] == correct_word[i]:
            feedback += f"\033[1;32m{guess[i]}\033[0m"  # Green and bold
            feedback_score += "🟩"
        elif i < len(guess):
            feedback += f"\033[1;31m{guess[i]}\033[0m"  # Red and bold
            feedback_score += "🟥"
        else:
            feedback += "_" # Indicate missing letters in shorter guesses
            feedback_score += "⬜️"
    return feedback, feedback_score

def play_game(
    content = {
        'daily_words':["cat", "train", "planet"],
        'daily_theme':"Travel and Exploration",
        'theme_reflection':"Exploring new places and ideas broadens our horizons and enriches our lives."
    }
):
    """Runs the word puzzle game with limited attempts and colored feedback."""
    daily_words = ["cat", "train", "planet"] #, "holiday", "mountain", "adventure", "celebration", "imagination", "photography", "communication"]
    daily_theme = "Travel and Exploration"
    theme_reflection = "Exploring new places and ideas broadens our horizons and enriches our lives."

    # word_lengths = [3, 5, 7, 8, 8, 10, 11, 12, 12, 14]
    # if [len(word) for word in daily_words] != word_lengths:
    #     raise ValueError("The lengths of the hardcoded words do not match the required progression.")

    jumbled_words = [jumble_word(word) for word in content['daily_words']]
    score = 0
    category_hint = "Related to going places and discovering new things."
    hint_available = False
    hint_revealed = False
    attempts_per_word = 3
    points_per_attempt = 10
    time_limit = 30
    feedback_scores = []

    print("Welcome to the Daily Word Puzzle!")
    print(f"You have {attempts_per_word} attempts per word. The category hint will appear after 10 seconds.")

    for i in range(len(content['daily_words'])):
        print(f"\nUnscramble this {len(content['daily_words'][i])}-letter word: {jumbled_words[i]}")
        attempts_left = attempts_per_word
        start_time = time.time()
        hint_available = False
        hint_revealed = False

        while attempts_left > 0 and time.time() - start_time < time_limit:
            elapsed_time = int(time.time() - start_time)
            if elapsed_time >= 10 and not hint_available:
                print("\nType 'hint' to see a category clue.")
                hint_available = True

            guess = input(f"Attempt {attempts_per_word - attempts_left + 1}/{attempts_per_word}: ").strip().lower()

            if guess == "hint" and hint_available and not hint_revealed:
                print(f"Category hint: {category_hint}")
                hint_revealed = True
            elif guess == content['daily_words'][i]:
                print(f"\033[1;32mCorrect!\033[0m The word was: \033[1;32m{content['daily_words'][i]}\033[0m")
                score += 10 * attempts_left + (time_limit - elapsed_time)
                print(f"Your current score: {score}")
                print(f"Time remaining: {time_limit - elapsed_time} seconds")
                feedback, feedback_score = color_feedback(i, guess, content['daily_words'][i])
                feedback_scores.append(feedback_score)
                break
            else:
                attempts_left -= 1
                feedback, feedback_score = color_feedback(i, guess, content['daily_words'][i])
                feedback_scores.append(feedback_score)
                print(f"Not quite! Feedback: {feedback} (Attempts left: {attempts_left})")
                print(feedback_score)
                if attempts_left == 0:
                    print(f"Out of attempts! The correct word was: {content['daily_words'][i]}")

        if time.time() - start_time >= time_limit:
            print(f"Time's up! The correct word was: {content['daily_words'][i]}")


    print("\n--- Game Over ---")
    print(f"Your final score: {score} out of {len(content['daily_words'])}")
    print(f"The daily theme was: {content['daily_theme']}")
    print(f"Reflection: {content['theme_reflection']}")
    print(f"\nShare your score! Copy this: \n\nI scored {score}/{(attempts_per_word*points_per_attempt+time_limit)*len(content['daily_words'])} in today's word puzzle!\n")
    print("Feedback scores:")
    for score in feedback_scores:
        print(score)
    print("")
if __name__ == "__main__":
    play_game()