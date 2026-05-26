const myUid = localStorage.getItem("user_uid");
const gameId = localStorage.getItem("current_game_id");

if (!myUid || !gameId) {
    window.location.href = "index.html";
}

const ws = new WebSocket(`ws://10.221.28.246:8000/ws/${myUid}`);
// Ask the server for the initial board state as soon as we connect
ws.onopen = function() {
    ws.send(JSON.stringify({
        type: "fetch_state",
        game_id: gameId
    }));
};
const statusText = document.getElementById("status-text");
const boardDiv = document.getElementById("board");

let cells = [];

// Create the 9 squares
for(let i = 0; i < 9; i++) {
    let cell = document.createElement("div");
    cell.className = "cell";
    cell.onclick = () => makeMove(i);
    boardDiv.appendChild(cell);
    cells.push(cell);
}

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // Update the board when the server sends the authoritative state
    if (data.type === "game_state") {
        data.board.forEach((mark, index) => {
            cells[index].innerText = mark ? mark : "";
        });

        if (data.turn === myUid) {
            statusText.innerText = "It's your turn!";
            statusText.style.color = "#28a745"; // Green
        } else {
            statusText.innerText = "Waiting for opponent...";
            statusText.style.color = "#d9534f"; // Red
        }
    }
    // --- NEW: Handle Game Over ---
    if (data.type === "game_over") {
        // Draw the final board state
        data.board.forEach((mark, index) => {
            cells[index].innerText = mark ? mark : "";
        });

        // Determine the message
        setTimeout(() => {
            if (data.winner === "Draw") {
                alert("It's a Draw! Well played.");
            } else if (data.winner === myUid) {
                alert("🏆 YOU WIN! 🏆");
            } else {
                alert("💀 YOU LOSE! 💀");
            }
            
            // Send them back to the lobby
            localStorage.removeItem("current_game_id");
            window.location.href = "lobby.html";
        }, 500); // Tiny delay so they can see the winning move
    }
};

function makeMove(index) {
    // Send the move to the server for validation
    ws.send(JSON.stringify({
        type: "move",
        game_id: gameId,
        cell_index: index
    }));
}