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
PLAYERS = ["Du", "Spieler 1", "Spieler 2"]
START_CARDS = 5

# Farben / Styles für Spieler-Panels & Verlauf
PLAYER_BG = {
    "Du":        "#e7f0ff",
    "Spieler 1": "#e8f7ee",
    "Spieler 2": "#fff7d6",
    "System":    "#f2f2f2",
}
PLAYER_BORDER = {
    "Du":        "#6aa0ff",
    "Spieler 1": "#45c08b",
    "Spieler 2": "#e5c300",
    "System":    "#e0e0e0",
}

# -------------- Darstellungs-Helfer ---------------------------------------

def emoji_suit(s):
    # Darstellung: Herz/Karo rot (Emoji), Pik/Kreuz schwarz
    return {"♥": "♥️", "♦": "♦️", "♠": "♠", "♣": "♣"}[s]

def suit_color(s):
    return "#d00" if s in ("♥", "♦") else "#111"

def suit_badge_html(s):
    """Kleiner farbiger Suit-Badge (für Wunschfarbe im Verlauf)."""
    col = suit_color(s)
    return f"""
    <span style="
      display:inline-block;
      border:1px solid {col};
      color:{col};
      padding:1px 6px;
      border-radius:8px;
      font-weight:700;
      margin-left:6px;
      background:#fff;
      user-select:none;
    ">{emoji_suit(s)}</span>
    """

def card_str(card):
    r, s = card
    return f"{r}{s}"

def card_html(card):
    """Gerahmte Card-UI mit Farbe (♥/♦ rot, ♣/♠ schwarz)."""
    r, s = card
    col = suit_color(s)
    return f"""
    <div style="
        display:inline-block;
        padding:6px 10px;
        margin:4px 4px 6px 0;
        border:2px solid {col};
        border-radius:10px;
        font-weight:700;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        color:{col};
        background:#fff;
        box-shadow: 0 1px 2px rgba(0,0,0,.06);
        user-select:none;
        ">
        {r}{emoji_suit(s)}
    </div>
    """

def can_play(card, top_card, wished_suit):
    r, s = card
    if wished_suit:
        return r == "J" or s == wished_suit
    return r == "J" or r == top_card[0] or s == top_card[1]

def new_deck():
    return [(r, s) for s in SUITS for r in RANKS]

# -------------- Kern-Logik ------------------------------------------------

def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        if len(state["discards"]) <= 1:
            return
        top = state["discards"][-1]
        pool = state["discards"][:-1]
        random.shuffle(pool)
        state["draw_pile"] = pool
        state["discards"] = [top]
        state["log"].append(("System", "🔄 Ziehstapel neu gemischt.", None, None))

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
        # Log-Eintrag (speaker, text, card, wished_suit_for_display)
        log=[("System", f"🃏 Startkarte: {card_str(top)}", top, None)],
        awaiting_wish=False,
    ))

def say(state, player, line):
    state["log"].append((player, line, None, None))

def quip_after_action(state, player, action):
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

def end_if_winner(state, player):
    """Sofort beenden, wenn jemand 0 Karten hat (deine Vorgabe)."""
    if len(state["hands"][player]) == 0:
        state["winner"] = player
        state["game_over"] = True
        return True
    return False

def play_card(state, player, card):
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["wished_suit"] = None
    state["log"].append((player, f"▶️ legt {card_str(card)}", card, None))

    # Effekte
    rank = card[0]
    if rank == "7":
        state["pending_draw"] += 2
    elif rank == "8":
        state["skip_next"] = True
    # J: Wunsch folgt separat

    # Sofortiges Ende, falls Hand leer
    if end_if_winner(state, player):
        return

def enforce_pending_draw(state):
    cur = PLAYERS[state["current"]]
    if state["pending_draw"] > 0:
        top = state["discards"][-1]
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"])
                        for c in state["hands"][cur])
        if not can_stack:
            draw_cards(state, cur, state["pending_draw"])
            state["log"].append((cur, f"😬 zieht {state['pending_draw']} Karten.", None, None))
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
            state["log"].append((player, "🂠 zieht 1 Karte.", None, None))
            quip_after_action(state, player, "draw")
            if can_play(drawn, top, state["wished_suit"]):
                play_card(state, player, drawn)
                if state["game_over"]:
                    return
                quip_after_action(state, player, "play")
                if drawn[0] == "J" and not state["game_over"]:
                    wish = bot_choose_wish(hand)
                    state["wished_suit"] = wish
                    state["log"].append((player, f"🎯 wünscht {wish}", None, wish))
                    quip_after_action(state, player, "wish")
        else:
            state["log"].append((player, "🂠 kann nicht ziehen (leer).", None, None))
    else:
        def score(c):
            if c[0] == "7": return 0
            if c[0] == "8": return 1
            if c[0] == "J": return 3
            return 2
        playable.sort(key=score)
        chosen = playable[0]
        play_card(state, player, chosen)
        if state["game_over"]:
            return
        quip_after_action(state, player, "play")
        if chosen[0] == "J" and not state["game_over"]:
            wish = bot_choose_wish(hand)
            state["wished_suit"] = wish
            state["log"].append((player, f"🎯 wünscht {wish}", None, wish))
            quip_after_action(state, player, "wish")

    if state["skip_next"] and not state["game_over"]:
        nxt = PLAYERS[next_player_index(state["current"])]
        state["log"].append(("System", f"⏭️ {nxt} wird übersprungen.", None, None))
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

    # Spieler-Panels (eigene Felder mit Hintergrundfarben)
    pc1, pc2, pc3 = st.columns(3)
    for col, p in zip((pc1, pc2, pc3), PLAYERS):
        with col:
            bg = PLAYER_BG[p]
            bd = PLAYER_BORDER[p]
            st.markdown(
                f"""
                <div style="
                  border:2px solid {bd};
                  background:{bg};
                  border-radius:14px;
                  padding:10px 12px;">
                  <div style="font-weight:700;margin-bottom:6px">{p}</div>
                  <div>Karten: <b>{len(state['hands'][p])}</b></div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()

    def run_spieler_bis_du(state):
        safety = 0
        while not state["game_over"] and PLAYERS[state["current"]] != "Du" and safety < 200:
            bot_turn(state, PLAYERS[state["current"]])
            safety += 1

    # Wunsch-Auswahl nach deinem Buben
    if state.get("awaiting_wish"):
        st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
        wish_cols = st.columns(4)
        for i, s in enumerate(SUITS):
            if wish_cols[i].button(emoji_suit(s), key=f"wish_{s}"):
                state["wished_suit"] = s
                state["log"].append(("Du", f"🎯 wünscht {s}", None, s))
                quip_after_action(state, "Du", "wish")
                state["awaiting_wish"] = False
                advance_turn(state)
                run_spieler_bis_du(state)
                RERUN()
        st.stop()

    run_spieler_bis_du(state)

    # Deine Karten
    st.markdown(
        f"""
        <div style="
          border:2px solid {PLAYER_BORDER['Du']};
          background:{PLAYER_BG['Du']};
          border-radius:14px;
          padding:10px 12px;
          margin-bottom:8px;">
          <div style="font-weight:700;margin-bottom:6px">🧑 Deine Karten</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    hand = state["hands"]["Du"]
    top = state["discards"][-1]

    # Draw-Pflicht nach 7 (wenn nicht stapelbar)
    if PLAYERS[state["current"]] == "Du" and state["pending_draw"] > 0:
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in hand)
        if not can_stack:
            if st.button(f"😬 {state['pending_draw']} Karten ziehen", type="primary", key="btn_force_draw"):
                draw_cards(state, "Du", state["pending_draw"])
                state["log"].append(("Du", f"😬 zieht {state['pending_draw']} Karten.", None, None))
                quip_after_action(state, "Du", "draw")
                state["pending_draw"] = 0
                advance_turn(state)
                run_spieler_bis_du(state)
                RERUN()

    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]
    unplayable = [c for c in hand if c not in playable]

    # Kartengitter mit stabilen Keys
    grid = st.columns(8)
    for idx, c in enumerate(playable):
        with grid[idx % 8]:
            st.markdown(card_html(c), unsafe_allow_html=True)
            if st.button(f"legen · {card_str(c)}", key=f"play_{c[0]}_{c[1]}_{idx}"):
                play_card(state, "Du", c)
                if state["game_over"]:
                    RERUN()
                quip_after_action(state, "Du", "play")
                if c[0] == "J" and not state["game_over"]:
                    state["awaiting_wish"] = True
                    RERUN()
                if state["skip_next"] and not state["game_over"]:
                    nxt = PLAYERS[next_player_index(state["current"])]
                    state["log"].append(("System", f"⏭️ {nxt} wird übersprungen.", None, None))
                    quip_after_action(state, "Du", "skip")
                    advance_turn(state)
                    state["skip_next"] = False
                if not state["game_over"]:
                    advance_turn(state)
                    run_spieler_bis_du(state)
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
            state["log"].append(("Du", "🂠 zieht 1 Karte.", None, None))
            quip_after_action(state, "Du", "draw")
        else:
            state["log"].append(("System", "🂠 Ziehstapel leer.", None, None))
        advance_turn(state)
        run_spieler_bis_du(state)
        RERUN()

with right:
    st.subheader("🗒️ Spielverlauf (neueste oben)")
    # Neueste oben
    for speaker, line, c, wished in reversed(state["log"][-180:]):
        bg = PLAYER_BG.get(speaker, "#fff")
        bd = PLAYER_BORDER.get(speaker, "#ccc")
        speaker_tag = "" if speaker == "System" else f"<strong>{speaker}:</strong> "
        extra = suit_badge_html(wished) if wished in SUITS else ""
        st.markdown(
            f"""
            <div style="
                border:2px solid {bd};
                border-radius:12px;
                padding:8px 10px;
                margin-bottom:8px;
                background:{bg};
                ">
                {speaker_tag}{line}{extra}
            </div>
            """,
            unsafe_allow_html=True
        )
        if c:
            st.markdown(card_html(c), unsafe_allow_html=True)

    # Spielende + Animationen
    if state["game_over"]:
        if state["winner"] == "Du":
            st.success(f"🏁 Spielende! **{state['winner']}** hat gewonnen. 🎉")
            try:
                st.balloons()
            except Exception:
                pass
        else:
            st.error(f"🏁 Spielende! **{state['winner']}** hat gewonnen. 😢")
            try:
                st.snow()
            except Exception:
                pass
        st.stop()
