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
PLAYERS = ["Du", "Spieler 1", "Spieler 2"]   # <- Umbenannt
START_CARDS = 5

# -------------- Hilfsfunktionen -------------------------------------------

def emoji_suit(s):
    return {"♥": "♥️", "♦": "♦️", "♠": "♠", "♣": "♣"}[s]

def card_str(card):
    r, s = card
    return f"{r}{s}"

def card_html(card):
    r, s = card
    suit = emoji_suit(s)
    color = "#d00" if s in ("♥", "♦") else "#111"
    border = f"2px solid {color}"
    return f"""
    <div style="
        display:inline-block;
        padding:6px 10px;
        margin:4px;
        border:{border};
        border-radius:10px;
        font-weight:700;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        color:{color};
        background:#fff;
        box-shadow: 0 1px 2px rgba(0,0,0,.06);
        user-select:none;
        ">
        {r}{suit}
    </div>
    """

def can_play(card, top_card, wished_suit):
    r, s = card
    if wished_suit:
        return r == "J" or s == wished_suit
    return r == "J" or r == top_card[0] or s == top_card[1]

def new_deck():
    return [(r, s) for s in SUITS for r in RANKS]

def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        if len(state["discards"]) <= 1:
            return
        top = state["discards"][-1]
        pool = state["discards"][:-1]
        random.shuffle(pool)
        state["draw_pile"] = pool
        state["discards"] = [top]
        state["log"].append(("System", "🔄 Ziehstapel neu gemischt.", None))

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
        log=[("System", f"🃏 Startkarte: {card_str(top)}", top)],
        awaiting_wish=False,
    ))

def say(state, player, line):
    state["log"].append((player, line, None))

def quip_after_action(state, player, action, card=None):
    jokes_play = [
        "Dezent wie ein Presslufthammer 😎",
        "Ich nenne das: taktische Eleganz.",
        "Nichts Persönliches. Nur Statistik.",
        "Das war kalkuliert. Irgendwie.",
        "Farbe bekennen, Karten verschenken.",
    ]
    jokes_draw = [
        "Zieh ich halt. Sammelkartenmodus aktiviert.",
        "Ich liebe Überraschungen 🎁",
        "Deck, enttäusch mich nicht!",
        "Nur eine. Was soll schon passieren?",
    ]
    jokes_skip = [
        "Ups, da fliegt jemand kurz raus!",
        "Ich schwöre, das war kein Timing.",
    ]
    jokes_wish = [
        "Und ich wünsche mir… genau diese Farbe.",
        "Wunsch frei, Realität folgt.",
    ]
    if action == "play":
        say(state, player, random.choice(jokes_play))
    elif action == "draw":
        say(state, player, random.choice(jokes_draw))
    elif action == "skip":
        say(state, player, random.choice(jokes_skip))
    elif action == "wish":
        say(state, player, random.choice(jokes_wish))

def play_card(state, player, card):
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["log"].append((player, f"▶️ spielt {card_str(card)}", card))
    state["wished_suit"] = None

    rank = card[0]
    if rank == "7":
        state["pending_draw"] += 2
    elif rank == "8":
        state["skip_next"] = True
    # J: Wunsch folgt separat

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
            state["log"].append((cur, f"😬 zieht {state['pending_draw']} Karten.", None))
            quip_after_action(state, cur, "draw")
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
            state["log"].append((player, "🂠 zieht 1 Karte.", None))
            quip_after_action(state, player, "draw")
            if can_play(drawn, top, state["wished_suit"]):
                play_card(state, player, drawn)
                quip_after_action(state, player, "play", drawn)
                if drawn[0] == "J" and not state["game_over"]:
                    wish = bot_choose_wish(hand)
                    state["wished_suit"] = wish
                    state["log"].append((player, f"🎯 wünscht {wish}", None))
                    quip_after_action(state, player, "wish")
        else:
            state["log"].append((player, "🂠 kann nicht ziehen (leer).", None))
    else:
        def score(c):
            if c[0] == "7": return 0
            if c[0] == "8": return 1
            if c[0] == "J": return 3
            return 2
        playable.sort(key=score)
        chosen = playable[0]
        play_card(state, player, chosen)
        quip_after_action(state, player, "play", chosen)
        if chosen[0] == "J" and not state["game_over"]:
            wish = bot_choose_wish(hand)
            state["wished_suit"] = wish
            state["log"].append((player, f"🎯 wünscht {wish}", None))
            quip_after_action(state, player, "wish")

    if state["skip_next"] and not state["game_over"]:
        nxt = PLAYERS[next_player_index(state["current"])]
        state["log"].append(("System", f"⏭️ {nxt} wird übersprungen.", None))
        quip_after_action(state, player, "skip")
        advance_turn(state)
        state["skip_next"] = False

    if not state["game_over"]:
        advance_turn(state)

# -------------- Streamlit UI ----------------------------------------------

st.set_page_config(page_title="Mau-Mau (32 Karten)", page_icon="🃏", layout="wide")
st.title("🃏 Mau-Mau · 32 Karten (Skat) — 2 Spieler + Du")

# Session init
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.state = {}
    start_game(st.session_state.state)
state = st.session_state.state

# Layout: links Spiel, rechts Verlauf (neueste oben)
left, right = st.columns([2, 1], gap="large")

with left:
    with st.sidebar:
        st.header("Spielkontrolle")
        if st.button("🔁 Neues Spiel", use_container_width=True):
            start_game(state)
            RERUN()
        st.caption("Regeln: 7=+2, 8=Aussetzen, J=Bube wünscht Farbe. "
                   "Passend nach Farbe oder Rang; bei Wunschfarbe nur diese Farbe oder J.")

    # Statuszeile
    cols = st.columns(4)
    cols[0].markdown(f"**Aktueller Spieler:** {PLAYERS[state['current']]}")
    cols[1].markdown(f"**Ablage oben:** {card_str(state['discards'][-1])}")
    cols[2].markdown(f"**Wunschfarbe:** {state['wished_suit'] or '—'}")
    cols[3].markdown(f"**Zugstapel:** {len(state['draw_pile'])} Karten")

    # Gegner-Infos
    oc1, oc2 = st.columns(2)
    oc1.subheader("🧑‍💻 Spieler 1")
    oc1.markdown(f"Karten: **{len(state['hands']['Spieler 1'])}**")
    oc2.subheader("🧑‍💻 Spieler 2")
    oc2.markdown(f"Karten: **{len(state['hands']['Spieler 2'])}**")

    st.divider()

    def run_bots_until_human(state):
        safety = 0
        while not state["game_over"] and PLAYERS[state["current"]] != "Du" and safety < 200:
            bot_turn(state, PLAYERS[state["current"]])
            safety += 1

    # Wunsch-Auswahl nach deinem Buben
    if state.get("awaiting_wish"):
        st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
        wish_cols = st.columns(4)
        for i, s in enumerate(SUITS):
            label = emoji_suit(s)
            if wish_cols[i].button(label, key=f"wish_{s}"):
                state["wished_suit"] = s
                state["log"].append(("Du", f"🎯 wünscht {s}", None))
                quip_after_action(state, "Du", "wish")
                state["awaiting_wish"] = False
                advance_turn(state)
                run_bots_until_human(state)
                RERUN()
        st.stop()

    run_bots_until_human(state)

    # Deine Karten
    st.subheader("🧑 Deine Karten")
    hand = state["hands"]["Du"]
    top = state["discards"][-1]

    # Draw-Pflicht nach 7 (wenn nicht stapelbar)
    if PLAYERS[state["current"]] == "Du" and state["pending_draw"] > 0:
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in hand)
        if not can_stack:
            if st.button(f"😬 {state['pending_draw']} Karten ziehen", type="primary", key="btn_force_draw"):
                draw_cards(state, "Du", state["pending_draw"])
                state["log"].append(("Du", f"😬 zieht {state['pending_draw']} Karten.", None))
                quip_after_action(state, "Du", "draw")
                state["pending_draw"] = 0
                advance_turn(state)
                run_bots_until_human(state)
                RERUN()

    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]
    unplayable = [c for c in hand if c not in playable]

    # Kartengitter mit stabilen Keys (ohne random())
    grid = st.columns(8)
    for idx, c in enumerate(playable):
        with grid[idx % 8]:
            st.markdown(card_html(c), unsafe_allow_html=True)
            if st.button(f"legen · {card_str(c)}", key=f"play_{c[0]}_{c[1]}_{idx}"):
                play_card(state, "Du", c)
                quip_after_action(state, "Du", "play", c)
                if c[0] == "J" and not state["game_over"]:
                    state["awaiting_wish"] = True
                    RERUN()
                if state["skip_next"] and not state["game_over"]:
                    nxt = PLAYERS[next_player_index(state["current"])]
                    state["log"].append(("System", f"⏭️ {nxt} wird übersprungen.", None))
                    quip_after_action(state, "Du", "skip")
                    advance_turn(state)
                    state["skip_next"] = False
                if not state["game_over"]:
                    advance_turn(state)
                    run_bots_until_human(state)
                RERUN()

    if unplayable:
        st.caption("Nicht spielbar:")
        ugrid = st.columns(8)
        for idx, c in enumerate(unplayable):
            with ugrid[idx % 8]:
                st.markdown(card_html(c), unsafe_allow_html=True)

    draw_disabled = state["pending_draw"] > 0 and PLAYERS[state["current"]] == "Du"
    if st.button("🂠 1 Karte ziehen", disabled=draw_disabled, key="btn_draw_one"):
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn = state["draw_pile"].pop()
            state["hands"]["Du"].append(drawn)
            state["log"].append(("Du", "🂠 zieht 1 Karte.", None))
            quip_after_action(state, "Du", "draw")
        else:
            state["log"].append(("System", "🂠 Ziehstapel leer.", None))
        advance_turn(state)
        run_bots_until_human(state)
        RERUN()

with right:
    st.subheader("🗒️ Spielverlauf (neueste oben)")
    for speaker, line, c in reversed(state["log"][-160:]):
        bubble_bg = "#f6f6f6" if speaker in ("System",) else "#fff"
        speaker_tag = f"<strong>{speaker}:</strong> " if speaker not in ("System",) else ""
        st.markdown(
            f"""
            <div style="
                border:1px solid #e6e6e6;
                border-radius:12px;
                padding:8px 10px;
                margin-bottom:8px;
                background:{bubble_bg};
                ">
                {speaker_tag}{line}
            </div>
            """,
            unsafe_allow_html=True
        )
        if c:
            st.markdown(card_html(c), unsafe_allow_html=True)

    if state["game_over"]:
        st.success(f"🏁 Spielende! **{state['winner']}** hat gewonnen.")
        st.stop()
