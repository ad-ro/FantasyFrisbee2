// Store players globally so the filters and week selector can access them
let globalPlayersData = [];

// Helper function to convert CSV text to Array of Objects
function parseCSV(text) {
    const lines = text.split('\n').filter(line => line.trim() !== '');
    if (lines.length === 0) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    return lines.slice(1).map(line => {
        const values = line.split(',').map(v => v.trim());
        return headers.reduce((obj, header, i) => {
            obj[header] = values[i];
            return obj;
        }, {});
    });
}

// Main function to load all league data
async function loadLeagueData() {
    try {
        // Fetch the files (assumed to be in the same directory)
        const [cumRes, totalRes, rosterRes] = await Promise.all([
            fetch('cum_score.csv').then(r => r.text()),
            fetch('total_score.csv').then(r => r.text()),
            fetch('rosters.json').then(r => r.json())
        ]);

        const cumData = parseCSV(cumRes);
        const totalData = parseCSV(totalRes);
        
        // Flatten rosters.json into a single array for easier filtering
        globalPlayersData = rosterRes.teams.flatMap(t => 
            t.players.map(p => ({ ...p, owner: t.owner }))
        );

        // Populate the UI
        displayStandings(cumData);
        showAllPlayers(); // Initial display of all players
        displayTeamRosters(rosterRes);
        displayWeeklyBreakdown(totalData);
        setupWeeklyDropdown(totalData);
        
        // Update timestamp if needed (using current date for now)
        displayLastUpdated(new Date());

    } catch (error) {
        console.error('Error loading league data:', error);
        const container = document.getElementById('standings-table');
        if (container) container.innerHTML = '<p style="color: red;">Error loading CSV/JSON data. Ensure you are running a local server.</p>';
    }
}

// 1. STANDINGS LOGIC (from cum_score.csv)
function displayStandings(cumData) {
    const container = document.getElementById('standings-table');
    if (!container || cumData.length === 0) return;

    const latest = cumData[cumData.length - 1]; // Get the most recent week
    // Sort owners by score (lowest score = Rank 1)
    const owners = ['Adam', 'Greg'].sort((a, b) => parseFloat(latest[a]) - parseFloat(latest[b]));

    let html = '<table><thead><tr><th>Rank</th><th>Owner</th><th>Total Score</th></tr></thead><tbody>';
    owners.forEach((owner, index) => {
        html += `<tr>
            <td>${index + 1}</td>
            <td>${owner}</td>
            <td class="score-cell">${latest[owner]}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 2. PLAYER LEADERBOARD LOGIC (Filtering & Buttons)
function displayPlayerStats(players, targetElementId) {
    const container = document.getElementById(targetElementId);
    if (!container) return;

    let html = '<table><thead><tr><th>Player</th><th>Owner</th><th>Played</th><th>Counted</th><th>Season Total</th></tr></thead><tbody>';
    players.forEach(p => {
        html += `<tr>
            <td>${p.name} ${p.is_underdog ? '<span class="underdog-badge">★</span>' : ''}</td>
            <td>${p.owner}</td>
            <td>${p.tournaments_played}</td>
            <td>${p.times_counted}</td>
            <td>${p.season_total}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function showAllPlayers() {
    updateBtnState('btn-all');
    displayPlayerStats(globalPlayersData, 'player-stats-table');
}

function showCountedOnly() {
    updateBtnState('btn-counted');
    const counted = globalPlayersData.filter(p => p.times_counted > 0);
    // Sort by most times counted
    counted.sort((a, b) => b.times_counted - a.times_counted);
    displayPlayerStats(counted, 'player-stats-table');
}

function showUnderdogs() {
    updateBtnState('btn-underdogs');
    const underdogs = globalPlayersData.filter(p => p.is_underdog === true);
    displayPlayerStats(underdogs, 'player-stats-table');
}

function updateBtnState(activeId) {
    document.querySelectorAll('.stats-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(activeId);
    if (activeBtn) activeBtn.classList.add('active');
}

// 3. WEEKLY DROPDOWN & INDIVIDUAL RESULTS
function setupWeeklyDropdown(totalData) {
    const selector = document.getElementById('week-selector');
    if (!selector) return;

    const maxWeeks = totalData.length;
    selector.innerHTML = '';
    
    if (maxWeeks === 0) {
        selector.innerHTML = '<option>No weeks available</option>';
        return;
    }

    for (let i = 1; i <= maxWeeks; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `Week ${i}`;
        selector.appendChild(option);
    }

    selector.value = maxWeeks; // Default to latest week
    updateWeeklyView();
}

function updateWeeklyView() {
    const selector = document.getElementById('week-selector');
    const container = document.getElementById('weekly-view-table');
    if (!selector || !container || !selector.value) return;

    const weekIndex = parseInt(selector.value, 10) - 1;

    // 1. Separate players who played from those who didn't
    const participants = globalPlayersData.filter(p => 
        p.weekly_scores && p.weekly_scores[weekIndex] !== "x" && p.weekly_scores[weekIndex] !== undefined
    );
    
    const nonParticipants = globalPlayersData.filter(p => 
        !p.weekly_scores || p.weekly_scores[weekIndex] === "x" || p.weekly_scores[weekIndex] === undefined
    );

    // 2. Sort participants by placement (lowest is best)
    participants.sort((a, b) => parseFloat(a.weekly_scores[weekIndex]) - parseFloat(b.weekly_scores[weekIndex]));

    // 3. Combine lists (Participants first, then Non-participants)
    const combinedList = [...participants, ...nonParticipants];

    if (combinedList.length === 0) {
        container.innerHTML = '<p>No player data found.</p>';
        return;
    }

    let html = '<table><thead><tr><th>Player</th><th>Owner</th><th>Placement</th></tr></thead><tbody>';
    
    combinedList.forEach(p => {
        const score = (p.weekly_scores && p.weekly_scores[weekIndex] !== undefined) ? p.weekly_scores[weekIndex] : "x";
        
        // Add a faded style for players who didn't play to make the table easier to read
        const rowStyle = score === "x" ? 'style="color: #999; background-color: #fafafa;"' : '';
        
        html += `<tr ${rowStyle}>
            <td>${p.name} ${p.is_underdog ? '<span class="underdog-badge">★</span>' : ''}</td>
            <td>${p.owner}</td>
            <td class="score-cell">${score}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 4. TEAM ROSTERS & BREAKDOWN
function displayTeamRosters(data) {
    const container = document.getElementById('team-rosters');
    if (!container) return;

    let html = '<div class="teams-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">';
    data.teams.forEach(team => {
        html += `<div class="team-card" style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3 style="border-bottom: 2px solid var(--primary-color); margin-bottom: 10px;">${team.team_name}</h3>
            <ul style="list-style: none;">
                ${team.players.map(p => `<li>${p.name} <small style="color: #666;">#${p.pdga_number}</small></li>`).join('')}
            </ul>
        </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

function displayWeeklyBreakdown(totalData) {
    const container = document.getElementById('weekly-breakdown');
    if (!container) return;

    let html = '<table><thead><tr><th>Event</th><th>Multiplier</th><th>Adam</th><th>Greg</th></tr></thead><tbody>';
    totalData.forEach(row => {
        html += `<tr>
            <td>${row['Event Name']}</td>
            <td>${row['Event Multiplier']}x</td>
            <td>${row['Adam']}</td>
            <td>${row['Greg']}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// 5. UTILS & MODAL
function displayLastUpdated(date) {
    const container = document.getElementById('last-updated');
    if (container) {
        container.textContent = `Last updated: ${date.toLocaleDateString()} at ${date.toLocaleTimeString()}`;
    }
}

function toggleRules() {
    const modal = document.getElementById('rules-modal');
    if (modal) {
        modal.style.display = (modal.style.display === 'block') ? 'none' : 'block';
    }
}

// Initialize the app
loadLeagueData();