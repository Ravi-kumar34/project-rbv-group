// 1. Wrap the initialization to prevent code execution if not logged in
const myUid = localStorage.getItem("user_uid");

if (!myUid) {
    window.location.href = "index.html";
} else {
    // Only load the leaderboard if the user is authenticated
    loadLeaderboard();
}

async function loadLeaderboard() {
    try {
        const host = window.location.hostname;
        const response = await fetch(`http://${host}:8000/leaderboard`);
        
        // Check if the HTTP request itself failed (e.g., 404 or 500 errors)
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
        
        // 2. Create a variable to hold the HTML string
        let rowsHtml = "";

        players.forEach((player, index) => {
            const rank = index + 1;
            const statusDot = player.is_online
                ? `<span class="online-dot"></span>Online`
                : `<span class="offline-dot"></span>Offline`;

            const highlight = player.uid === myUid ? 'style="background:#e8f0fe; font-weight:bold;"' : '';

            // 3. Simple XSS protection: escape < and > characters in the player name
            const safeName = player.name ? player.name.replace(/</g, "&lt;").replace(/>/g, "&gt;") : "Unknown Player";

            // Append to our string, not the DOM
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

        // Inject the completed HTML string once
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