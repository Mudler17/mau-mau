
import random
import streamlit as st

# -------------- Game Config (Mau-Mau, 32-card Skat deck) -----------------
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]
PLAYERS = ["Du", "Bot 1", "Bot 2"]
START_CARDS = 5

# Mau-Mau rules used here (common variant):
# - Match by suit OR rank.
# - 7 (Sieben) => next player draws 2; can be stacked (7 on 7 adds +2).
# - 8 (Acht) => skip next player.
# - J (Bube) => wild: player declares a suit (Wunschfarbe).
# - Other ranks have no special effect.
#
# Notes:
# - If a suit is wished (after J), only suit-matching or another J can be played.
# - Draw pile is refilled by reshuffling all but the top discard when needed.

# -------------- Utility ---------------------------------------------------

def new_deck():
    return [(r, s) for s in SUITS for r in RANKS]

def card_str(card):
    r, s = card
    return f"{r}{s}"

def can_play(card, top_card, wished_suit):
    """Return True if 'card' can be played on 'top_card' given optional wished suit."""
    r, s = card
    if wished_suit:
        # When a suit is wished, only that suit or any J can be played
        return r == "J" or s == wished_suit
    # Normal rule: same rank or same suit, Jack always playable
    return r == "J" or r == top_card[0] or s == top_card[1]

def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        # Refill from discards, leaving the top card
        if len(state["discards"]) <= 1:
            return  # nothing to reshuffle
        top = state["discards"][-1]
        pool = state["discards"][:-1]
        random.shuffle(pool)
        state["draw_pile"] = pool
        state["discards"] = [top]
        state["log"].append("🔄 Ziehstapel neu gemischt.")

def draw_cards(state, player, n):
    for _ in range(n):
        reshuffle_if_needed(state)
        if not state["draw_pile"]:
            break
        state["hands"][player].append(state["draw_pile"].pop())

def next_player_index(i):
    # Clockwise, 3 players
    return (i + 1) % len(PLAYERS)

def start_game(state):
    deck = new_deck()
    random.shuffle(deck)

    hands = {p: [] for p in PLAYERS}
    for _ in range(START_CARDS):
        for p in PLAYERS:
            hands[p].append(deck.pop())

    # Flip first top card (avoid starting with J to skip wish at start)
    top = deck.pop()
    while top[0] == "J":
        deck.insert(0, top)
        random.shuffle(deck)
        top = deck.pop()

    state.update(dict(
        hands=hands,
        draw_pile=deck,
        discards=[top],
        current=0,  # "Du" begins
        wished_suit=None,
        pending_draw=0,   # accumulated draw from 7s
        skip_next=False,  # due to 8
        winner=None,
        game_over=False,
        log=[f"🃏 Startkarte: {card_str(top)}"],
    ))

def play_card(state, player, card):
    # Remove card from hand and place on discard
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["log"].append(f"▶️ {player} spielt {card_str(card)}")

    # Clear suit wish unless a new J is played and sets a new wish later
    # (We handle wish assignment outside for human; in bots we set directly here)
    state["wished_suit"] = None

    # Apply card effects
    rank = card[0]
    if rank == "7":
        # +2 draw for next player (stackable)
        state["pending_draw"] += 2
    elif rank == "8":
        # skip next player
        state["skip_next"] = True
    elif rank == "J":
        # suit wish will be set by caller (human) or AI function
        pass

    # Win check
    if len(state["hands"][player]) == 0:
        state["winner"] = player
        state["game_over"] = True

def enforce_pending_draw(state):
    """Apply pending draw to the current player if they cannot stack a 7."""
    cur = PLAYERS[state["current"]]
    if state["pending_draw"] > 0:
        # Check if current player has a 7 they can play (stacking allowed if rules permit)
        top = state["discards"][-1]
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in state["hands"][cur])
        if not can_stack:
            draw_cards(state, cur, state["pending_draw"])
            state["log"].append(f"😬 {cur} zieht {state['pending_draw']} Karten.")
            state["pending_draw"] = 0
            return True  # drew instead of playing
    return False

def advance_turn(state):
    state["current"] = next_player_index(state["current"])

def bot_choose_wish(hand):
    # Choose suit with the most cards remaining; fallback random
    suit_counts = {s: 0 for s in SUITS}
    for r, s in hand:
        suit_counts[s] += 1
    # Break ties randomly but consistently
    best = max(suit_counts.items(), key=lambda x: (x[1], random.random()))[0]
    return best

def bot_turn(state, player):
    if state["game_over"]:
        return

    # Handle pending draw logic for 7s
    if enforce_pending_draw(state):
        # drew due to pending draw; end turn
        advance_turn(state)
        return

    hand = state["hands"][player]
    top = state["discards"][-1]

    # Find playable cards
    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]

    if not playable:
        # draw one and try once more
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn = state["draw_pile"].pop()
            hand.append(drawn)
            state["log"].append(f"🂠 {player} zieht 1 Karte.")
            if can_play(drawn, top, state["wished_suit"]):
                # play the drawn card
                play_card(state, player, drawn)
                if drawn[0] == "J":
                    wish = bot_choose_wish(hand)
                    state["wished_suit"] = wish
                    state["log"].append(f"🎯 {player} wünscht {wish}")
        else:
            state["log"].append(f"🂠 {player} kann nicht ziehen (leer).")
    else:
        # Simple heuristic: prefer to play non-J first, then 7/8 for effects
        # Sort: prioritize 7/8 > normal > J as fallback
        def score(c):
            if c[0] == "7":
                return 0
            if c[0] == "8":
                return 1
            if c[0] == "J":
                return 3
            return 2
        playable.sort(key=score)
        chosen = playable[0]
        play_card(state, player, chosen)
        if chosen[0] == "J":
            wish = bot_choose_wish(hand)  # after removing chosen J, hand is updated
            state["wished_suit"] = wish
            state["log"].append(f"🎯 {player} wünscht {wish}")

    # If an 8 was played, skip next player
    if state["skip_next"] and not state["game_over"]:
        nxt = PLAYERS[next_player_index(state["current"])]
        state["log"].append(f"⏭️ {nxt} wird übersprungen.")
        advance_turn(state)  # skip
        state["skip_next"] = False

    # Advance to next turn if game not over
    if not state["game_over"]:
        advance_turn(state)

# -------------- Streamlit UI ---------------------------------------------

st.set_page_config(page_title="Mau-Mau (32 Karten) · 2 Bots + Du", page_icon="🃏", layout="wide")
st.title("🃏 Mau‑Mau · 32 Karten (Skat) — 2 Bots + Du")

if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.state = {}
    start_game(st.session_state.state)

state = st.session_state.state

# Sidebar: New game & settings
with st.sidebar:
    st.header("Spielkontrolle")
    if st.button("🔁 Neues Spiel", use_container_width=True):
        start_game(state)
        st.experimental_rerun()
    st.caption("Regeln: 7=+2 (stapelbar), 8=Aussetzen, J=Bube wünscht Farbe. "
               "Passend nach Farbe oder Rang; bei Wunschfarbe nur diese Farbe oder J.")

# Top status row
cols = st.columns(4)
with cols[0]:
    st.markdown(f"**Aktueller Spieler:** {PLAYERS[state['current']]}")
with cols[1]:
    st.markdown(f"**Ablagestapel oben:** {card_str(state['discards'][-1])}")
with cols[2]:
    st.markdown(f"**Wunschfarbe:** {state['wished_suit'] or '—'}")
with cols[3]:
    st.markdown(f"**Zugstapel:** {len(state['draw_pile'])} Karten")

# Opponents info
opp_col1, opp_col2 = st.columns(2)
with opp_col1:
    st.subheader("🤖 Bot 1")
    st.markdown(f"Karten auf der Hand: **{len(state['hands']['Bot 1'])}**")
with opp_col2:
    st.subheader("🤖 Bot 2")
    st.markdown(f"Karten auf der Hand: **{len(state['hands']['Bot 2'])}**")

st.divider()

# Process automatic bot turns until it's the human's turn (or game over)
def run_bots_until_human(state):
    safety = 0
    while not state["game_over"] and PLAYERS[state["current"]] != "Du" and safety < 200:
        player = PLAYERS[state["current"]]
        bot_turn(state, player)
        safety += 1

run_bots_until_human(state)

# Human turn area
st.subheader("🧑 Deine Karten")
hand = state["hands"]["Du"]
top = state["discards"][-1]

# Pending draw enforcement (7s): if you cannot stack a 7, you auto-draw when your turn begins.
if PLAYERS[state["current"]] == "Du" and state["pending_draw"] > 0:
    # Check if you can stack a 7
    can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in hand)
    if not can_stack:
        if st.button(f"😬 {state['pending_draw']} Karten ziehen (wegen 7)", type="primary"):
            draw_cards(state, "Du", state["pending_draw"])
            state["pending_draw"] = 0
            advance_turn(state)
            run_bots_until_human(state)
            st.experimental_rerun()

# Show playable hand as buttons
playable = [c for c in hand if can_play(c, top, state["wished_suit"])]
unplayable = [c for c in hand if c not in playable]

def render_card_button(card, key_prefix="play"):
    label = card_str(card)
    return st.button(label, key=f"{key_prefix}_{label}_{random.random()}")

# Playable first
card_cols = st.columns(8)
idx = 0
for c in playable:
    with card_cols[idx % 8]:
        if render_card_button(c, "play"):
            play_card(state, "Du", c)
            # If J, ask for wish
            if c[0] == "J" and not state["game_over"]:
                st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
                wish_cols = st.columns(4)
                chosen = None
                for i, s in enumerate(SUITS):
                    with wish_cols[i]:
                        if st.button(f"{s}", key=f"wish_{s}"):
                            chosen = s
                if chosen is None:
                    # default to most common suit if not chosen (e.g., on rerun)
                    counts = {s: 0 for s in SUITS}
                    for r, s in state["hands"]["Du"]:
                        counts[s] += 1
                    chosen = max(counts.items(), key=lambda x: (x[1], random.random()))[0]
                state["wished_suit"] = chosen
                state["log"].append(f"🎯 Du wünschst {chosen}")
            # Handle skip due to 8
            if state["skip_next"] and not state["game_over"]:
                nxt = PLAYERS[next_player_index(state["current"])]
                state["log"].append(f"⏭️ {nxt} wird übersprungen.")
                advance_turn(state)
                state["skip_next"] = False
            # Advance and let bots play
            if not state["game_over"]:
                advance_turn(state)
                run_bots_until_human(state)
            st.experimental_rerun()
    idx += 1

# Unplayable (disabled look via small text)
if unplayable:
    st.caption("Nicht spielbar: " + ", ".join(card_str(c) for c in unplayable))

# Draw button (normal draw 1 when you cannot/won't play)
draw_disabled = state["pending_draw"] > 0 and PLAYERS[state["current"]] == "Du"
draw_btn = st.button("🂠 1 Karte ziehen", disabled=draw_disabled)
if draw_btn and PLAYERS[state["current"]] == "Du" and not state["game_over"]:
    reshuffle_if_needed(state)
    if state["draw_pile"]:
        drawn = state["draw_pile"].pop()
        state["hands"]["Du"].append(drawn)
        state["log"].append("🂠 Du ziehst 1 Karte.")
        # Optionally auto-play if the drawn card is playable (house rule off by default)
        # if can_play(drawn, top, state["wished_suit"]):
        #     play_card(state, "Du", drawn)
    else:
        state["log"].append("🂠 Ziehstapel ist leer.")
    # End turn after drawing
    advance_turn(state)
    run_bots_until_human(state)
    st.experimental_rerun()

st.divider()

# Log + end of game
st.subheader("📜 Spielverlauf")
for line in state["log"][-40:]:
    st.write(line)

if state["game_over"]:
    st.success(f"🏁 Spielende! **{state['winner']}** hat gewonnen.")
    st.stop()
