const myUid = localStorage.getItem("user_uid");

if (!myUid) {
    window.location.href = "index.html";
} else {
    
    // 2. Open the WebSocket to stay online!
    connectWebSocket(); 
}

async function loadLeaderboard() {
    try {
        const host = window.location.hostname;
        const response = await fetch(`http://${host}:8000/leaderboard`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            document.getElementById("loading-msg").innerText = data.error || "Failed to load leaderboard.";
            return;
        }

        const players = data.leaderboard;
        const tbody = document.getElementById("leaderboard-body");
        
        let rowsHtml = "";

        players.forEach((player, index) => {
            const rank = index + 1;
            const statusDot = player.is_online
                ? `<span class="online-dot"></span>Online`
                : `<span class="offline-dot"></span>Offline`;

            const highlight = player.uid === myUid ? 'style="background:#e8f0fe; font-weight:bold;"' : '';
            const safeName = player.name ? player.name.replace(/</g, "&lt;").replace(/>/g, "&gt;") : "Unknown Player";

            rowsHtml += `
                <tr ${highlight}>
                    <td class="rank">${getRankLabel(rank)}</td>
                    <td>${safeName}</td>
                    <td style="font-size:12px; color:#888;">${player.uid}</td>
                    <td><strong>${player.elo_rating}</strong></td>
                    <td>${statusDot}</td>
                </tr>
            `;
        });

        tbody.innerHTML = rowsHtml;
        document.getElementById("loading-msg").style.display = "none";
        document.getElementById("leaderboard-table").style.display = "table";

    } catch (err) {
        console.error("Leaderboard fetch error:", err);
        document.getElementById("loading-msg").innerText = "Server error. Make sure the backend is running and CORS is allowed.";
    }
}

function getRankLabel(rank) {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return rank;
}

// --- NEW: WebSocket Connection for the Leaderboard ---
function connectWebSocket() {
    const host = window.location.hostname;
    const ws = new WebSocket(`ws://${host}:8000/ws/${myUid}`);

    // --- THE FIX: Wait for the socket to open before fetching the leaderboard ---
    ws.onopen = function() {
        loadLeaderboard();
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);

        // If someone challenges you while you are viewing the leaderboard
        if (data.type === "incoming_challenge") {
            const modal = document.getElementById("challenge-modal");
            if (modal) {
                document.getElementById("challenge-text").innerText = `⚔️ Challenge from ${data.from_name}!`;
                modal.style.display = "block";

                // Accept Challenge
                document.getElementById("accept-btn").onclick = function() {
                    modal.style.display = "none";
                    ws.send(JSON.stringify({
                        type: "challenge_response",
                        target_uid: data.from_uid, 
                        from_uid: myUid,
                        accepted: true
                    }));
                };

                // Decline Challenge
                document.getElementById("decline-btn").onclick = function() {
                    modal.style.display = "none";
                    ws.send(JSON.stringify({
                        type: "challenge_response",
                        target_uid: data.from_uid, 
                        from_uid: myUid,
                        accepted: false
                    }));
                };
            }
        }

        // If the match starts, jump to the arena
        if (data.type === "match_start") {
            localStorage.setItem("current_game_id", data.game_id);
            window.location.href = "arena.html"; 
        }
    };
}