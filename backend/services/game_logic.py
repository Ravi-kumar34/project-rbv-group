def check_winner(board):
    """
    Evaluates the 3x3 board matrix to check for a victory or a draw.
    Returns 'X', 'O', 'Draw', or None.
    """
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
        [0, 4, 8], [2, 4, 6]              # Diagonals
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
            
    if None not in board:
        return "Draw"
        
    return None