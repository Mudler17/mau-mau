import random
import streamlit as st

# --- Kompatibler Rerun-Wrapper (neu/alt Streamlit) ---
def RERUN():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# -------------- Game Config (Mau-Mau, 32-Karten Skatdeck) -----------------
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]
PLAYERS = ["Du", "Bot 1", "Bot 2"]
START_CARDS = 5

# Mau-Mau-Regeln (häufige Variante):
# - Nach Farbe ODER Rang legen
# - 7 = +2 ziehen (stapelbar)
# - 8 = Aussetzen
# - J = Bube → Wunschfarbe
# - Stapel leer → Nachziehstapel wird aus Ablagestapel neu gemischt


# -------------- Hilfsfunktionen -------------------------------------------

def new_deck():
    return [(r, s) for s in SUITS for r in RANKS]

def card_str(card):
    r, s = card
    return f"{r}{s}"

def can_play(card, top_card, wished_suit):
    r, s = card
    if wished_suit:
        return r == "J" or s == wished_suit
    return r == "J" or r == top_card[0] or s == top_card[1]

def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        if len(state["discards"]) <= 1:
            return
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
    return (i + 1) % len(PLAYERS)

def start_game(state):
    deck = new_deck()
    random.shuffle(deck)

    hands = {p: [] for p in PLAYERS}
    for _ in range(START_CARDS):
        for p in PLAYERS:
            hands[p].append(deck.pop())

    top = deck.pop()
    while top[0] == "J":  # nicht mit Bube starten
        deck.insert(0, top)
        random.shuffle(deck)
        top = deck.pop()

    state.update(dict(
        hands=hands,
        draw_pile=deck,
        discards=[top],
        current=0,
        wished_suit=None,
        pending_draw=0,
        skip_next=False,
        winner=None,
        game_over=False,
        log=[f"🃏 Startkarte: {card_str(top)}"],
        awaiting_wish=False,
    ))

def play_card(state, player, card):
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["log"].append(f"▶️ {player} spielt {card_str(card)}")
    state["wished_suit"] = None

    rank = card[0]
    if rank == "7":
        state["pending_draw"] += 2
    elif rank == "8":
        state["skip_next"] = True
    elif rank == "J":
        pass

    if len(state["hands"][player]) == 0:
        state["winner"] = player
        state["game_over"] = True

def enforce_pending_draw(state):
    cur = PLAYERS[state["current"]]
    if state["pending_draw"] > 0:
        top = state["discards"][-1]
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"])
                        for c in state["hands"][cur])
        if not can_stack:
            draw_cards(state, cur, state["pending_draw"])
            state["log"].append(f"😬 {cur} zieht {state['pending_draw']} Karten.")
            state["pending_draw"] = 0
            return True
    return False

def advance_turn(state):
    state["current"] = next_player_index(state["current"])

def bot_choose_wish(hand):
    suit_counts = {s: 0 for s in SUITS}
    for r, s in hand:
        suit_counts[s] += 1
    return max(suit_counts.items(), key=lambda x: (x[1], random.random()))[0]

def bot_turn(state, player):
    if state["game_over"]:
        return
    if enforce_pending_draw(state):
        advance_turn(state)
        return

    hand = state["hands"][player]
    top = state["discards"][-1]
    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]

    if not playable:
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn = state["draw_pile"].pop()
            hand.append(drawn)
            state["log"].append(f"🂠 {player} zieht 1 Karte.")
            if can_play(drawn, top, state["wished_suit"]):
                play_card(state, player, drawn)
                if drawn[0] == "J" and not state["game_over"]:
                    wish = bot_choose_wish(hand)
                    state["wished_suit"] = wish
                    state["log"].append(f"🎯 {player} wünscht {wish}")
    else:
        def score(c):
            if c[0] == "7": return 0
            if c[0] == "8": return 1
            if c[0] == "J": return 3
            return 2
        playable.sort(key=score)
        chosen = playable[0]
        play_card(state, player, chosen)
        if chosen[0] == "J" and not state["game_over"]:
            wish = bot_choose_wish(hand)
            state["wished_suit"] = wish
            state["log"].append(f"🎯 {player} wünscht {wish}")

    if state["skip_next"] and not state["game_over"]:
        nxt = PLAYERS[next_player_index(state["current"])]
        state["log"].append(f"⏭️ {nxt} wird übersprungen.")
        advance_turn(state)
        state["skip_next"] = False

    if not state["game_over"]:
        advance_turn(state)


# -------------- Streamlit UI ----------------------------------------------

st.set_page_config(page_title="Mau-Mau (32 Karten)", page_icon="🃏", layout="wide")
st.title("🃏 Mau-Mau · 32 Karten (Skat) — 2 Bots + Du")

if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.state = {}
    start_game(st.session_state.state)

state = st.session_state.state

with st.sidebar:
    st.header("Spielkontrolle")
    if st.button("🔁 Neues Spiel", use_container_width=True):
        start_game(state)
        RERUN()
    st.caption("Regeln: 7=+2, 8=Aussetzen, J=Bube wünscht Farbe. "
               "Passend nach Farbe oder Rang; bei Wunschfarbe nur diese Farbe oder J.")

cols = st.columns(4)
cols[0].markdown(f"**Aktueller Spieler:** {PLAYERS[state['current']]}")
cols[1].markdown(f"**Ablagestapel oben:** {card_str(state['discards'][-1])}")
cols[2].markdown(f"**Wunschfarbe:** {state['wished_suit'] or '—'}")
cols[3].markdown(f"**Zugstapel:** {len(state['draw_pile'])} Karten")

opp_col1, opp_col2 = st.columns(2)
opp_col1.subheader("🤖 Bot 1")
opp_col1.markdown(f"Karten: **{len(state['hands']['Bot 1'])}**")
opp_col2.subheader("🤖 Bot 2")
opp_col2.markdown(f"Karten: **{len(state['hands']['Bot 2'])}**")

st.divider()

def run_bots_until_human(state):
    safety = 0
    while not state["game_over"] and PLAYERS[state["current"]] != "Du" and safety < 200:
        bot_turn(state, PLAYERS[state["current"]])
        safety += 1

if state.get("awaiting_wish"):
    st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
    wish_cols = st.columns(4)
    for i, s in enumerate(SUITS):
        if wish_cols[i].button(s, key=f"wish_{s}"):
            state["wished_suit"] = s
            state["log"].append(f"🎯 Du wünschst {s}")
            state["awaiting_wish"] = False
            advance_turn(state)
            run_bots_until_human(state)
            RERUN()
    st.stop()

run_bots_until_human(state)

st.subheader("🧑 Deine Karten")
hand = state["hands"]["Du"]
top = state["discards"][-1]

if PLAYERS[state["current"]] == "Du" and state["pending_draw"] > 0:
    can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in hand)
    if not can_stack:
        if st.button(f"😬 {state['pending_draw']} Karten ziehen", type="primary"):
            draw_cards(state, "Du", state["pending_draw"])
            state["pending_draw"] = 0
            advance_turn(state)
            run_bots_until_human(state)
            RERUN()

playable = [c for c in hand if can_play(c, top, state["wished_suit"])]
unplayable = [c for c in hand if c not in playable]

def render_card_button(card):
    return st.button(card_str(card), key=f"play_{card_str(card)}_{random.random()}")

card_cols = st.columns(8)
for idx, c in enumerate(playable):
    if card_cols[idx % 8].button(card_str(c)):
        play_card(state, "Du", c)
        if c[0] == "J" and not state["game_over"]:
            state["awaiting_wish"] = True
            RERUN()
        if state["skip_next"] and not state["game_over"]:
            nxt = PLAYERS[next_player_index(state["current"])]
            state["log"].append(f"⏭️ {nxt} wird übersprungen.")
            advance_turn(state)
            state["skip_next"] = False
        if not state["game_over"]:
            advance_turn(state)
            run_bots_until_human(state)
        RERUN()

if unplayable:
    st.caption("Nicht spielbar: " + ", ".join(card_str(c) for c in unplayable))

draw_disabled = state["pending_draw"] > 0 and PLAYERS[state["current"]] == "Du"
if st.button("🂠 1 Karte ziehen", disabled=draw_disabled):
    reshuffle_if_needed(state)
    if state["draw_pile"]:
        state["hands"]["Du"].append(state["draw_pile"].pop())
        state["log"].append("🂠 Du ziehst 1 Karte.")
    else:
        state["log"].append("🂠 Ziehstapel leer.")
    advance_turn(state)
    run_bots_until_human(state)
    RERUN()

st.divider()
st.subheader("📜 Spielverlauf")
for line in state["log"][-40:]:
    st.write(line)

if state["game_over"]:
    st.success(f"🏁 Spielende! **{state['winner']}** hat gewonnen.")
    st.stop()
