const myUid = localStorage.getItem("user_uid");

// --- DYNAMIC URL ROUTING ---
const isSecure = window.location.protocol === "https:";
const currentHost = window.location.host; 
const apiBase = `${isSecure ? 'https' : 'http'}://${currentHost}`;
const wsBase = `${isSecure ? 'wss' : 'ws'}://${currentHost}/ws`;

if (!myUid) {
    window.location.href = "index.html";
} else {
    // 2. Open the WebSocket to stay online!
    connectWebSocket(); 
}

// --- 1. FETCH AND LOAD TOP BAR PROFILE ---
async function loadTopBarProfile() {
    if (!myUid) return;

    try {
        // Updated to use dynamic apiBase and added ngrok bypass header
        const response = await fetch(`${apiBase}/user/${myUid}`, {
            headers: {
                "ngrok-skip-browser-warning": "true"
            }
        });
        const data = await response.json();

        if (!data.error) {
            const nameEl = document.getElementById("topbar-name");
            const eloEl = document.getElementById("topbar-elo");
            
            if (nameEl) nameEl.innerText = data.name;
            if (eloEl) eloEl.innerText = data.elo_rating;
        }
    } catch (error) {
        console.error("Error fetching top bar profile:", error);
    }
}

// Call the function immediately so the top bar loads
loadTopBarProfile();

async function loadLeaderboard() {
    try {
        // Updated to use dynamic apiBase and added ngrok bypass header
        const response = await fetch(`${apiBase}/leaderboard`, {
            headers: {
                "ngrok-skip-browser-warning": "true"
            }
        });
        
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

function connectWebSocket() {
    // Updated to use dynamic wsBase
    const ws = new WebSocket(`${wsBase}/${myUid}`);

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