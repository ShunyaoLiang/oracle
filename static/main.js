// The application state.
const state = {
  authPlayerId: null,
  players: null,
  currentTurn: null,
  selection: {
    cardName: null,
    targetPlayerId: null,
    targetBuildingName: null,
  }
};

const socket = new WebSocket(`ws://${window.location.host}/game`);

async function joinGame() {
  // Store the authenticated player id.
  const input = document.getElementById('auth-player-id-field').value;
  if (input !== '') {
    // The user is a resuming player.
    state.authPlayerId = parseInt(input);
  } else {
    const response = await sendRequest('POST', '/game/join', {});
    if (response.status === 201) {
      const json = await response.json();
      state.authPlayerId = json.auth_player_id;
    }
  }
  // Now that we have joined, let's find out what's going on.
  await getGameState();
  // Render!
  render();
  // We violate the architecture here for simplicity. By default, the join
  // menu is rendered. It will never be rendered again..
  const joinForm = document.getElementById('join-form');
  joinForm.remove();
}

function selectCardInHand(cardName) {
  return () => {
    state.selection.cardName = cardName;
    render();
  };
}

function selectTargetBuilding(targetBuildingName) {
  return () => {
    state.selection.targetBuildingName = targetBuildingName;
    render();
  };
}

function selectTargetPlayer(targetPlayerId) {
  return () => {
    state.selection.targetPlayerId = targetPlayerId;
    render();
  };
}

function render() {
  // Render the players.
  const playersElement = document.getElementById('game-players');
  playersElement.replaceChildren(...state.players.map(createPlayerElement));
  if (state.currentTurn) {
    // Render the Stack.
    const stackElement = document.getElementById('game-stack');
    stackElement.replaceChildren();
    const stackLabel = document.createElement('p');
    stackLabel.textContent = 'The Stack';
    stackElement.appendChild(stackLabel);
    state.currentTurn.stack.forEach(cardName => {
      stackElement.appendChild(createCardElement(cardName));
    });
    // Mark the player whose turn it is.
    playersElement.children[state.currentTurn.player_id].classList.add('turn');
  }
  // Render the authenticated player's hand.
  const handElement = document.getElementById('game-hand');
  handElement.replaceChildren();
  const handLabel = document.createElement('p');
  handLabel.textContent = 'Your Hand';
  handElement.appendChild(handLabel);
  for (const cardName of state.players[state.authPlayerId].hand) {
    const cardElement = createCardElement(cardName);
    cardElement.addEventListener('click', selectCardInHand(cardName));
    handElement.appendChild(cardElement);
  }
  // Render controls.
  const controlsElement = document.getElementById('controls');
  const controls = [];
  // Either the start button or the pass button exists at one time.
  if (state.currentTurn) {
    const passButton = document.createElement('button');
    passButton.textContent = 'Pass';
    passButton.addEventListener('click', passPriority);
    controls.push(passButton);
  } else {
    const startButton = document.createElement('button');
    startButton.textContent = 'Start the Game';
    startButton.addEventListener('click', startGame);
    controls.push(startButton);
  }
  // If a card is selected, draw the play button.
  if (state.selection.cardName) {
    const playButton = document.createElement('button');
    playButton.textContent = 'Play';
    playButton.addEventListener('click', playCard);
    controls.push(playButton);
  }
  controlsElement.replaceChildren(...controls);
}

function createPlayerElement(player, playerId) {
  const playerElement = document.createElement('div');
  playerElement.classList.add('game-player');

  const playerTitleLine = document.createElement('p');
  playerTitleLine.appendChild(document.createTextNode(`Player ${playerId}`));
  if (playerId === state.authPlayerId) {
    const youTagElement = document.createElement('span');
    youTagElement.textContent = '(You)';
    playerTitleLine.appendChild(youTagElement);
  }
  const targetButton = document.createElement('button');
  targetButton.textContent = 'Target';
  targetButton.addEventListener('click', selectTargetPlayer(playerId));
  playerTitleLine.appendChild(targetButton);
  playerElement.appendChild(playerTitleLine);

  const playerStatusLine = document.createElement('p');

  if (player.role) {
    playerStatusLine.appendChild(createCardElement(player.role));
  }

  const playerHealthBar = document.createElement('span');
  playerHealthBar.textContent = `${player.health}/5`;
  playerStatusLine.appendChild(playerHealthBar);

  playerElement.appendChild(playerStatusLine);

  const playerHandCountElement = document.createElement('p');
  playerHandCountElement.textContent = `I have ${player.hand_count} cards in hand.`;
  playerElement.appendChild(playerHandCountElement);

  const playerBuildingsElement = document.createElement('p');
  for (const buildingName of player.buildings) {
    const buildingElement = createCardElement(buildingName);
    buildingElement.addEventListener('click', selectTargetBuilding(buildingName));
    playerBuildingsElement.appendChild(buildingElement);
    // Fort discarding.
    if (playerId === state.authPlayerId && buildingName === 'FORT') {
      buildingElement.addEventListener('click', discardFort);
    }
  }
  playerElement.appendChild(playerBuildingsElement);

  return playerElement;
}

function createCardElement(cardName) {
  const cardElement = document.createElement('img');
  const cardNamePath = cardName.toLowerCase().replaceAll('_', '-');
  cardElement.src = `https://oraclecardgame.com/wp-content/uploads/${cardNamePath}.jpg`;
  cardElement.className = 'card';
  return cardElement;
}

function renderSpyHand(spyHand) {
  const spyHandElement = document.getElementById('game-spy-hand');
  const spyHandLabel = document.createElement('p');
  spyHandLabel.textContent = 'Spy Hand';
  spyHandElement.appendChild(spyHandLabel);
  for (const cardName of spyHand) {
    spyHandElement.appendChild(createCardElement(cardName));
  }
}

document.addEventListener('DOMContentLoaded', _ => {
  const joinButton = document.getElementById('join-button');
  joinButton.addEventListener('click', joinGame);
  socket.addEventListener('message', async socketEvent => {
    const gameEvent = JSON.parse(socketEvent.data);
    console.log(gameEvent);
    if (gameEvent.name === 'STATE_UPDATE') {
      await getGameState();
      render();
    }
  });
});

async function getGameState() {
  const response = await sendRequest('GET', '/game', {});
  if (response.status === 200) {
    const json = await response.json();
    state.players = json.players;
    state.currentTurn = json.current_turn;
  } else {
    throw new Error();
  }
}

function toTitleCase(words) {
  return words
    .split('_')
    .map(word => word[0].toUpperCase() + word.substring(1).toLowerCase())
    .join(' ');
}

function passPriority() {
  sendRequest('POST', '/game/pass', {});
}

function startGame() {
  sendRequest('POST', '/game/start', {});
}

async function playCard() {
  const body = {};
  if (state.selection.cardName !== null) {
    body.card_name = state.selection.cardName;
  }
  if (state.selection.targetPlayerId !== null) {
    body.target_player_id = state.selection.targetPlayerId;
  }
  if (state.selection.targetBuildingName !== null) {
    body.target_building_name = state.selection.targetBuildingName;
  }
  state.selection = {
    cardName: null,
    targetPlayerId: null,
    targetBuildingName: null
  };
  await sendRequest('POST', '/game/play', body);

  // Spy things!
  if (selection.cardName === 'SPY') {
    const { spy_hand: spyHand } = await sendRequest('GET', '/game/spy_hand', {})
      .then(response => response.json());
    renderSpyHand(spyHand);
  }
}

function discardFort() {
  sendRequest('POST', '/game/discard_fort', {});
}

async function sendRequest(method, resource, body) {
  const headers = {
    'auth-player-id': state.authPlayerId,
    'Content-Type': 'application/json'
  };
  const options = {
    headers: headers,
    method: method,
  };
  if (method !== 'GET') {
    options.body = JSON.stringify(body);
  };
  const response = await fetch(resource, options);
  if (response.status === 400) {
    const errorMessageElement = document.getElementById('error-message');
    errorMessageElement.textContent = await response.text();
  }
  return response;
}
