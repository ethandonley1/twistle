// js/main.js
const TwistleGame = (() => {
  let gamesData, theme, words, currentIdx, correctCount, timerId, timeLeft;
  async function loadGames() {
    const resp = await fetch('data/games.json');
    gamesData = await resp.json();
  }
  function pickTodayGame() {
    const day = new Date().getDate();
    theme = gamesData[(day - 1) % gamesData.length];
    words = Object.entries(theme.daily_words).map(([w, hint]) => ({ word: w, hint }));
  }
  function startRound() {
    if (currentIdx >= words.length) return endGame();
    const { word, hint } = words[currentIdx];
    document.getElementById('theme-name').textContent = theme.daily_theme;
    const scrambled = scramble(word);
    document.getElementById('scrambled').textContent = scrambled;
    document.getElementById('feedback').textContent = '';
    document.getElementById('hint-btn').onclick = () => alert(hint);
    startTimer();
  }
  function scramble(str) {
    return str.split('').sort(() => Math.random() - 0.5).join('');
  }
  function startTimer() {
    clearInterval(timerId);
    timeLeft = 30;
    updateTimer();
    timerId = setInterval(() => {
      timeLeft--;
      if (timeLeft <= 0) {
        clearInterval(timerId);
        nextWord();
      }
      updateTimer();
    }, 1000);
  }
  function updateTimer() {
    document.getElementById('timer').textContent = `Time: ${timeLeft}s`;
  }
  function handleGuess(e) {
    e.preventDefault();
    const guess = document.getElementById('guess-input').value.trim().toLowerCase();
    const correct = words[currentIdx].word.toLowerCase();
    if (guess === correct) {
      correctCount++;
      nextWord();
    } else {
      document.getElementById('feedback').textContent = 'Try again!';
    }
  }
  function nextWord() {
    currentIdx++;
    startRound();
  }
  function endGame() {
    clearInterval(timerId);
    localStorage.setItem('twistle_last_score', correctCount);
    location.href = 'results.html';
  }
  function showResults() {
    document.getElementById('correct-count').textContent = localStorage.getItem('twistle_last_score') || 0;
  }
  function showLeaderboard() {
    const list = document.getElementById('leaderboard-list');
    list.innerHTML = '<li>No leaderboard data yet.</li>';
  }
  function showStats() {
    document.body.insertAdjacentHTML('beforeend', '<p>Stats coming soon!</p>');
  }
  function showSettings() {
    document.body.insertAdjacentHTML('beforeend', '<p>Settings coming soon!</p>');
  }
  function showHelp() {
    document.body.insertAdjacentHTML('beforeend', '<p>Help content coming soon!</p>');
  }

  return {
    init: async () => {
      await loadGames();
      pickTodayGame();
      currentIdx = 0;
      correctCount = 0;
      document.getElementById('guess-form').addEventListener('submit', handleGuess);
      document.getElementById('retry-btn').addEventListener('click', () => startRound());
      startRound();
    },
    showResults,
    showLeaderboard,
    showStats,
    showSettings,
    showHelp
  };
})();