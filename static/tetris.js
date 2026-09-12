// A small, self-contained Tetris implementation. Exposes window.TetrisGame
// with start()/stop() so script.js can lazily start it only when the
// Games tab is actually opened.
(function () {
  const COLS = 8;
  const ROWS = 16;
  const BLOCK = 30; // canvas is 240x480... but canvas height is 440, ROWS*BLOCK must match; adjust below

  const CANVAS_ID = "tetrisCanvas";
  const SCORE_ID = "tetrisScore";
  const LINES_ID = "tetrisLines";
  const MSG_ID = "tetrisMsg";

  // Piece colors pulled from the app's own palette instead of generic neon Tetris colors
  const COLORS = ["#2a6f6f", "#3f6b35", "#b5502d", "#6b4e9e", "#e8a93b", "#8a7a5c", "#c0392b"];

  const SHAPES = [
    [[1, 1, 1, 1]],                 // I
    [[1, 1], [1, 1]],               // O
    [[0, 1, 0], [1, 1, 1]],         // T
    [[1, 0], [1, 0], [1, 1]],       // J
    [[0, 1], [0, 1], [1, 1]],       // L
    [[1, 1, 0], [0, 1, 1]],         // S
    [[0, 1, 1], [1, 1, 0]],         // Z
  ];

  let canvas, ctx;
  let cellSize = 27;
  let board, current, currentColor, currentX, currentY;
  let score = 0, lines = 0;
  let dropInterval = 700;
  let dropTimer = null;
  let running = false;
  let gameOver = false;

  function emptyBoard() {
    return Array.from({ length: ROWS }, () => Array(COLS).fill(null));
  }

  function randomPiece() {
    const idx = Math.floor(Math.random() * SHAPES.length);
    return { shape: SHAPES[idx].map((r) => r.slice()), color: COLORS[idx] };
  }

  function rotate(shape) {
    const rows = shape.length, cols = shape[0].length;
    const result = Array.from({ length: cols }, () => Array(rows).fill(0));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        result[c][rows - 1 - r] = shape[r][c];
      }
    }
    return result;
  }

  function collides(shape, offX, offY) {
    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (!shape[r][c]) continue;
        const x = offX + c, y = offY + r;
        if (x < 0 || x >= COLS || y >= ROWS) return true;
        if (y >= 0 && board[y][x]) return true;
      }
    }
    return false;
  }

  function merge() {
    current.forEach((row, r) => {
      row.forEach((val, c) => {
        if (val) {
          const y = currentY + r, x = currentX + c;
          if (y >= 0) board[y][x] = currentColor;
        }
      });
    });
  }

  function clearLines() {
    let cleared = 0;
    for (let r = ROWS - 1; r >= 0; r--) {
      if (board[r].every((cell) => cell)) {
        board.splice(r, 1);
        board.unshift(Array(COLS).fill(null));
        cleared++;
        r++; // re-check same index after shift
      }
    }
    if (cleared) {
      const points = [0, 100, 300, 500, 800][cleared] || cleared * 200;
      score += points;
      lines += cleared;
      document.getElementById(SCORE_ID).textContent = score;
      document.getElementById(LINES_ID).textContent = lines;
      dropInterval = Math.max(150, 700 - lines * 20);
    }
  }

  function spawn() {
    const p = randomPiece();
    current = p.shape;
    currentColor = p.color;
    currentX = Math.floor((COLS - current[0].length) / 2);
    currentY = -1;
    if (collides(current, currentX, currentY + 1)) {
      endGame();
    }
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // board
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        if (board[r][c]) {
          drawCell(c, r, board[r][c]);
        }
      }
    }
    // current piece
    if (current) {
      current.forEach((row, r) => {
        row.forEach((val, c) => {
          if (val && currentY + r >= 0) drawCell(currentX + c, currentY + r, currentColor);
        });
      });
    }
    // grid lines
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    for (let x = 0; x <= COLS; x++) {
      ctx.beginPath();
      ctx.moveTo(x * cellSize, 0);
      ctx.lineTo(x * cellSize, ROWS * cellSize);
      ctx.stroke();
    }
    for (let y = 0; y <= ROWS; y++) {
      ctx.beginPath();
      ctx.moveTo(0, y * cellSize);
      ctx.lineTo(COLS * cellSize, y * cellSize);
      ctx.stroke();
    }
  }

  function drawCell(x, y, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x * cellSize + 1, y * cellSize + 1, cellSize - 2, cellSize - 2);
  }

  function tick() {
    if (!running) return;
    if (!collides(current, currentX, currentY + 1)) {
      currentY++;
    } else {
      merge();
      clearLines();
      spawn();
    }
    draw();
  }

  function loop() {
    if (!running) return;
    tick();
    dropTimer = setTimeout(loop, dropInterval);
  }

  function move(dx) {
    if (!running || !current) return;
    if (!collides(current, currentX + dx, currentY)) {
      currentX += dx;
      draw();
    }
  }

  function softDrop() {
    if (!running || !current) return;
    if (!collides(current, currentX, currentY + 1)) {
      currentY++;
      draw();
    }
  }

  function hardDrop() {
    if (!running || !current) return;
    while (!collides(current, currentX, currentY + 1)) {
      currentY++;
    }
    tick();
  }

  function doRotate() {
    if (!running || !current) return;
    const rotated = rotate(current);
    if (!collides(rotated, currentX, currentY)) {
      current = rotated;
    } else if (!collides(rotated, currentX - 1, currentY)) {
      current = rotated;
      currentX -= 1;
    } else if (!collides(rotated, currentX + 1, currentY)) {
      current = rotated;
      currentX += 1;
    }
    draw();
  }

  function endGame() {
    running = false;
    gameOver = true;
    clearTimeout(dropTimer);
    const msg = document.getElementById(MSG_ID);
    if (msg) {
      msg.textContent = `Game over — score ${score}.`;
      msg.hidden = false;
    }
    const btn = document.getElementById("tetrisStartBtn");
    if (btn) btn.textContent = "Play again";
  }

  function keyHandler(e) {
    if (!running) return;
    switch (e.key) {
      case "ArrowLeft": move(-1); e.preventDefault(); break;
      case "ArrowRight": move(1); e.preventDefault(); break;
      case "ArrowDown": softDrop(); e.preventDefault(); break;
      case "ArrowUp": doRotate(); e.preventDefault(); break;
      case " ": hardDrop(); e.preventDefault(); break;
    }
  }

  function start() {
    canvas = document.getElementById(CANVAS_ID);
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    cellSize = canvas.width / COLS;

    board = emptyBoard();
    score = 0;
    lines = 0;
    dropInterval = 700;
    gameOver = false;
    document.getElementById(SCORE_ID).textContent = "0";
    document.getElementById(LINES_ID).textContent = "0";
    const msg = document.getElementById(MSG_ID);
    if (msg) msg.hidden = true;

    clearTimeout(dropTimer);
    running = true;
    spawn();
    draw();
    document.addEventListener("keydown", keyHandler);
    loop();
  }

  function stop() {
    running = false;
    clearTimeout(dropTimer);
    document.removeEventListener("keydown", keyHandler);
  }

  window.TetrisGame = { start, stop };
})();
