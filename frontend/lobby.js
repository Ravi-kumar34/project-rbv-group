// 1. Get the UID we saved during login
const myUid = localStorage.getItem("user_uid");

// Security check
if (!myUid) {
    window.location.href = "index.html";
}
// --- 1. FETCH AND LOAD TOP BAR PROFILE ---
async function loadTopBarProfile() {
    if (!myUid) return;

    try {
        const host = window.location.hostname;
        const response = await fetch(`http://${host}:8000/user/${myUid}`);
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
// 2. Open the WebSocket connection
const host = window.location.hostname;
const ws = new WebSocket(`ws://${host}:8000/ws/${myUid}`);

// 3. Listen for messages from the server
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // Redraw the player list
    if (data.type === "lobby_update") {
        renderLobby(data.users);
    }
    
    // --- THE AUTO-ACCEPT FIX ---
// --- THE REAL POPUP FIX ---
    if (data.type === "incoming_challenge") {
        // Show the custom modal
        const modal = document.getElementById("challenge-modal");
        document.getElementById("challenge-text").innerText = `⚔️ Challenge from ${data.from_name}!`;
        modal.style.display = "block";

        // If they click Accept
        document.getElementById("accept-btn").onclick = function() {
            modal.style.display = "none";
            ws.send(JSON.stringify({
                type: "challenge_response",
                target_uid: data.from_uid, 
                from_uid: myUid,
                accepted: true
            }));
        };

        // If they click Decline
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

    // Handle Match Start
    if (data.type === "match_start") {
        localStorage.setItem("current_game_id", data.game_id);
        window.location.href = "arena.html"; 
    }

    // Handle Rejection
    if (data.type === "challenge_rejected") {
        alert(data.message);
        // Reset the UI so they can try again
        ws.send(JSON.stringify({ type: "fetch_lobby" })); 
        window.location.reload();
    }
};

ws.onclose = function() {
    console.log("Leaving the lobby to enter the arena...");
};

// 4. Function to draw the players on the screen
function renderLobby(users) {
    const playersListDiv = document.getElementById("players-list");
    playersListDiv.innerHTML = ""; 

    let activeOpponents = 0;

    users.forEach(user => {
        if (user.uid === myUid) return;

        activeOpponents++;

        const playerCard = document.createElement("div");
        playerCard.className = "player-card";
        
        playerCard.innerHTML = `
            <div>
                <strong>${user.name}</strong><br>
                <small>Elo Rating: ${user.elo}</small>
            </div>
            <button class="challenge-btn" onclick="sendChallenge('${user.uid}', '${user.name}')">Challenge</button>
        `;
        
        playersListDiv.appendChild(playerCard);
    });

    if (activeOpponents === 0) {
        playersListDiv.innerHTML = "<p>No other players are currently online. Waiting for opponents...</p>";
    }
}

// 5. Send the challenge
function sendChallenge(targetUid, targetName) {
    console.log(`Sending challenge to ${targetName} (${targetUid})`);
    
    const challengeMessage = {
        type: "challenge",
        target_uid: targetUid,
        from_uid: myUid
    };
    
    ws.send(JSON.stringify(challengeMessage));
    
    // Show loading text
    document.getElementById("players-list").innerHTML = "<p>Challenge sent! Teleporting to Arena...</p>";
}