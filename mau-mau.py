import random
import time
import html
import streamlit as st

# -------------- Rerun-Wrapper (kompatibel) -----------------
def RERUN():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# -------------- Game Config --------------------------------
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]
PLAYERS = ["Du", "Spieler 1", "Spieler 2"]
START_CARDS = 5

# Spielerfarben + Bilder (Pfad ggf. anpassen)
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
PLAYER_IMG = {
    "Du": None,  # eigenes Bild weglassen/ergänzen
    "Spieler 1": "/mnt/data/spieler.png",
    "Spieler 2": "/mnt/data/spielerin.png",
}

# -------------- Darstellung --------------------------------
def emoji_suit(s):
    return {"♥": "♥️", "♦": "♦️", "♠": "♠", "♣": "♣"}[s]

def suit_color(s):
    return "#d00" if s in ("♥", "♦") else "#111"

def suit_badge_html(s):
    col = suit_color(s)
    return f"""
    <span style="
      display:inline-block;border:2px solid {col};color:{col};
      padding:2px 10px;border-radius:10px;font-weight:800;
      font-size:1.05rem;margin-left:8px;background:#fff;user-select:none;">
      {emoji_suit(s)}
    </span>
    """

def card_str(card):
    r, s = card
    return f"{r}{s}"

def card_html(card, big=False):
    r, s = card
    col = suit_color(s)
    pad = "10px 14px" if not big else "14px 18px"
    fs = "1.15rem" if not big else "1.35rem"
    brd = "3px" if not big else "4px"
    return f"""
    <div style="
        display:inline-block;padding:{pad};margin:6px 6px 10px 0;
        border:{brd} solid {col};border-radius:14px;font-weight:900;
        font-size:{fs};letter-spacing:.2px;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        color:{col};background:#fff;box-shadow:0 2px 4px rgba(0,0,0,.08);user-select:none;">
        {html.escape(r)}{emoji_suit(s)}
    </div>
    """

def can_play(card, top_card, wished_suit):
    r, s = card
    if wished_suit:
        return r == "J" or s == wished_suit
    return r == "J" or r == top_card[0] or s == top_card[1]

def new_deck():
    return [(r, s) for s in SUITS for r in RANKS]

# -------------- State-Helpers --------------------------------
def init_session():
    st.session_state.initialized = True
    st.session_state.state = {}
    start_game(st.session_state.state)

def start_game(state):
    deck = new_deck()
    random.shuffle(deck)
    hands = {p: [] for p in PLAYERS}
    for _ in range(START_CARDS):
        for p in PLAYERS:
            hands[p].append(deck.pop())
    top = deck.pop()
    while top[0] == "J":
        deck.insert(0, top); random.shuffle(deck); top = deck.pop()
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
        # Log: kurze Einträge tuples (speaker, msg, card_or_None, wished_or_None) – Anzeige escapt!
        log=[("System", f"Start: {card_str(top)}", top, None)],
        awaiting_wish=False,
        # Mini-Animations-Cache: player -> {"card":tuple|None, "quip":str|None, "ts":float}
        last_action={p: {"card": None, "quip": None, "ts": 0.0} for p in PLAYERS},
    ))

# -------------- Engine -----------------------------------------------------
def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        if len(state["discards"]) <= 1: return
        top = state["discards"][-1]
        pool = state["discards"][:-1]
        random.shuffle(pool)
        state["draw_pile"] = pool
        state["discards"] = [top]
        state["log"].append(("System", "Ziehstapel gemischt", None, None))

def draw_cards(state, player, n):
    for _ in range(n):
        reshuffle_if_needed(state)
        if not state["draw_pile"]: break
        state["hands"][player].append(state["draw_pile"].pop())

def next_player_index(i): return (i + 1) % len(PLAYERS)

def quip(action):
    jokes = {
        "play": [
            "Dezent wie ein Presslufthammer 😎",
            "Taktische Eleganz.",
            "Nur Statistik.",
            "Kalkuliert. Irgendwie.",
        ],
        "draw": [
            "Sammelkartenmodus aktiviert.",
            "Ich liebe Überraschungen 🎁",
            "Nur eine — was soll schon schiefgehen?",
        ],
        "skip": [
            "Nur kurz raus, versprochen.",
            "Kein Timing… wirklich nicht.",
        ],
        "wish": [
            "Ich wünsche mir … genau das.",
            "Wunsch frei, Realität folgt.",
        ],
    }
    return random.choice(jokes[action])

def mark_last_action(state, player, card=None, q=None):
    state["last_action"][player] = {"card": card, "quip": q, "ts": time.time()}

def end_if_winner(state, player):
    if len(state["hands"][player]) == 0:
        state["winner"] = player
        state["game_over"] = True
        return True
    return False

def play_card(state, player, card):
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["wished_suit"] = None
    state["log"].append((player, f"legt {card_str(card)}", card, None))
    if card[0] == "7":
        state["pending_draw"] += 2
    elif card[0] == "8":
        state["skip_next"] = True
    # Ende checken
    if end_if_winner(state, player): return

def enforce_pending_draw(state):
    cur = PLAYERS[state["current"]]
    if state["pending_draw"] > 0:
        top = state["discards"][-1]
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"])
                        for c in state["hands"][cur])
        if not can_stack:
            draw_cards(state, cur, state["pending_draw"])
            msg = f"zieht {state['pending_draw']}"
            state["log"].append((cur, msg, None, None))
            mark_last_action(state, cur, None, quip("draw"))
            state["pending_draw"] = 0
            return True
    return False

def advance_turn(state): state["current"] = next_player_index(state["current"])

def bot_choose_wish(hand):
    suit_counts = {s: 0 for s in SUITS}
    for r, s in hand: suit_counts[s] += 1
    return max(suit_counts.items(), key=lambda x: (x[1], random.random()))[0]

def bot_turn(state, player):
    if state["game_over"]: return
    if enforce_pending_draw(state):
        advance_turn(state); return
    hand = state["hands"][player]
    top = state["discards"][-1]
    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]

    if not playable:
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn = state["draw_pile"].pop()
            hand.append(drawn)
            state["log"].append((player, "zieht 1", None, None))
            mark_last_action(state, player, None, quip("draw"))
            if can_play(drawn, top, state["wished_suit"]):
                play_card(state, player, drawn)
                if state["game_over"]: return
                mark_last_action(state, player, drawn, quip("play"))
                if drawn[0] == "J" and not state["game_over"]:
                    wish = bot_choose_wish(hand)
                    state["wished_suit"] = wish
                    state["log"].append((player, "wünscht", None, wish))
                    mark_last_action(state, player, None, quip("wish"))
        else:
            state["log"].append((player, "kann nicht ziehen", None, None))
    else:
        def score(c):
            if c[0] == "7": return 0
            if c[0] == "8": return 1
            if c[0] == "J": return 3
            return 2
        playable.sort(key=score)
        chosen = playable[0]
        play_card(state, player, chosen)
        if state["game_over"]: return
        mark_last_action(state, player, chosen, quip("play"))
        if chosen[0] == "J" and not state["game_over"]:
            wish = bot_choose_wish(hand)
            state["wished_suit"] = wish
            state["log"].append((player, "wünscht", None, wish))
            mark_last_action(state, player, None, quip("wish"))

    if state["skip_next"] and not state["game_over"]:
        nxt = PLAYERS[next_player_index(state["current"])]
        state["log"].append(("System", f"{nxt} aussetzen", None, None))
        mark_last_action(state, player, None, quip("skip"))
        advance_turn(state)
        state["skip_next"] = False

    if not state["game_over"]:
        advance_turn(state)

# -------------- UI --------------------------------------------------------
st.set_page_config(page_title="Mau-Mau (32 Karten)", page_icon="🃏", layout="wide")
st.title("🃏 Mau-Mau · 32 Karten (Skat) — 2 Spieler + Du")

if "initialized" not in st.session_state:
    init_session()
state = st.session_state.state

left, right = st.columns([5, 3], gap="large")

with left:
    with st.sidebar:
        st.header("Spielkontrolle")
        if st.button("🔁 Neues Spiel", use_container_width=True):
            start_game(state); RERUN()
        st.caption("Regeln: 7=+2, 8=Aussetzen, J=Bube wünscht Farbe.")

    # Statuszeile groß
    cols = st.columns(4)
    cols[0].markdown(f"<div style='font-size:1.1rem'><b>Aktuell:</b> {html.escape(PLAYERS[state['current']])}</div>", unsafe_allow_html=True)
    cols[1].markdown(f"<div style='font-size:1.1rem'><b>Ablage:</b> {html.escape(card_str(state['discards'][-1]))}</div>", unsafe_allow_html=True)
    cols[2].markdown(f"<div style='font-size:1.1rem'><b>Wunsch:</b> {html.escape(state['wished_suit'] or '—')}</div>", unsafe_allow_html=True)
    cols[3].markdown(f"<div style='font-size:1.1rem'><b>Ziehstapel:</b> {len(state['draw_pile'])}</div>", unsafe_allow_html=True)

    # Spieler-Panels mit Bild + Mini-Aktion unten (zeitversetzt)
    pc = st.columns(3)
    now = time.time()
    show_secs = 1.5  # Dauer der Action-Einblendung

    for col, p in zip(pc, PLAYERS):
        with col:
            bg = PLAYER_BG[p]; bd = PLAYER_BORDER[p]
            st.markdown(
                f"<div style='border:3px solid {bd};background:{bg};border-radius:16px;padding:12px 12px;'>"
                f"<div style='display:flex;gap:10px;align-items:center;'>"
                f"{('<img src=\"file://'+PLAYER_IMG[p]+'\" style=\"width:52px;height:52px;border-radius:10px;border:2px solid '+bd+';object-fit:cover;\" />' if PLAYER_IMG[p] else '')}"
                f"<div><div style='font-weight:900;font-size:1.15rem'>{html.escape(p)}</div>"
                f"<div style='font-size:1.05rem'>Karten: <b>{len(state['hands'][p])}</b></div></div>"
                f"</div></div>",
                unsafe_allow_html=True
            )
            # Action-Overlay
            la = state["last_action"].get(p, {})
            if la and (now - la.get("ts", 0)) < show_secs:
                with st.container():
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                    if la.get("card"):
                        st.markdown(card_html(la["card"], big=True), unsafe_allow_html=True)
                    if la.get("quip"):
                        st.markdown(
                            f"<div style='font-size:1rem;opacity:.85'><em>{html.escape(la['quip'])}</em></div>",
                            unsafe_allow_html=True
                        )

    st.divider()

    def run_spieler_bis_du(state):
        safety = 0
        while not state["game_over"] and PLAYERS[state["current"]] != "Du" and safety < 200:
            bot_turn(state, PLAYERS[state["current"]])
            safety += 1
            # kurze Pause, damit Einblendung sichtbar ist
            time.sleep(0.4)

    # Wunsch nach Bube (Du)
    if state.get("awaiting_wish"):
        st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
        wish_cols = st.columns(4)
        picked = None
        for i, s in enumerate(SUITS):
            if wish_cols[i].button(emoji_suit(s), key=f"wish_{s}"):
                picked = s
        if picked:
            state["wished_suit"] = picked
            state["log"].append(("Du", "wünscht", None, picked))
            mark_last_action(state, "Du", None, quip("wish"))
            state["awaiting_wish"] = False
            advance_turn(state); run_spieler_bis_du(state); RERUN()
        st.stop()

    run_spieler_bis_du(state)

    # --- Deine Karten ------------------------------------------------------
    st.markdown(
        f"<div style='border:3px solid {PLAYER_BORDER['Du']};background:{PLAYER_BG['Du']};"
        f"border-radius:16px;padding:14px 14px;margin-bottom:10px;'>"
        f"<div style='font-weight:900;margin-bottom:8px;font-size:1.2rem'>🧑 Deine Karten</div></div>",
        unsafe_allow_html=True
    )

    hand = state["hands"]["Du"]
    top = state["discards"][-1]

    # Pflichtziehen nach 7 (wenn nicht stapelbar)
    if PLAYERS[state["current"]] == "Du" and state["pending_draw"] > 0:
        can_stack = any((c[0] == "7") and can_play(c, top, state["wished_suit"]) for c in hand)
        if not can_stack:
            if st.button(f"😬 {state['pending_draw']} Karten ziehen", type="primary", key="btn_force_draw"):
                draw_cards(state, "Du", state["pending_draw"])
                state["log"].append(("Du", f"zieht {state['pending_draw']}", None, None))
                mark_last_action(state, "Du", None, quip("draw"))
                state["pending_draw"] = 0
                advance_turn(state); run_spieler_bis_du(state); RERUN()

    playable = [c for c in hand if can_play(c, top, state["wished_suit"])]
    unplayable = [c for c in hand if c not in playable]

    grid = st.columns(6)
    for idx, c in enumerate(playable):
        with grid[idx % 6]:
            st.markdown(card_html(c), unsafe_allow_html=True)
            if st.button(f"🂡 Legen: {card_str(c)}", key=f"play_{c[0]}_{c[1]}_{idx}"):
                play_card(state, "Du", c)
                if state["game_over"]:
                    if state["winner"] == "Du":
                        try: st.balloons()
                        except: pass
                    else:
                        try: st.snow()
                        except: pass
                    RERUN()
                mark_last_action(state, "Du", c, quip("play"))
                if c[0] == "J" and not state["game_over"]:
                    state["awaiting_wish"] = True; RERUN()
                if state["skip_next"] and not state["game_over"]:
                    nxt = PLAYERS[next_player_index(state["current"])]
                    state["log"].append(("System", f"{nxt} aussetzen", None, None))
                    mark_last_action(state, "Du", None, quip("skip"))
                    advance_turn(state); state["skip_next"] = False
                if not state["game_over"]:
                    advance_turn(state); run_spieler_bis_du(state)
                RERUN()

    if unplayable:
        st.caption("Nicht spielbar:")
        ugrid = st.columns(6)
        for idx, c in enumerate(unplayable):
            with ugrid[idx % 6]:
                st.markdown(card_html(c), unsafe_allow_html=True)

    draw_disabled = state["pending_draw"] > 0 and PLAYERS[state["current"]] == "Du"
    if st.button("🂠 1 Karte ziehen", disabled=draw_disabled, key="btn_draw_one"):
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn = state["draw_pile"].pop()
            state["hands"]["Du"].append(drawn)
            state["log"].append(("Du", "zieht 1", None, None))
            mark_last_action(state, "Du", None, quip("draw"))
        else:
            state["log"].append(("System", "Ziehstapel leer", None, None))
        advance_turn(state); run_spieler_bis_du(state); RERUN()

with right:
    st.subheader("🗒️ Spielverlauf (kurz · neueste oben)")
    # Kurzform; alles escapen -> keine <div>-Reste mehr
    MAX_SHOW = 140
    for entry in reversed(state["log"][-MAX_SHOW:]):
        sp, msg, c, w = ("System","",None,None)
        if isinstance(entry,(list,tuple)):
            if len(entry)>=1: sp = entry[0]
            if len(entry)>=2: msg = entry[1]
            if len(entry)>=3: c = entry[2]
            if len(entry)>=4: w = entry[3]
        bg = PLAYER_BG.get(sp, "#fff")
        bd = PLAYER_BORDER.get(sp, "#ccc")
        short = f"{html.escape(sp)}: {html.escape(msg)}"
        badge = suit_badge_html(w) if w in SUITS else ""
        st.markdown(
            f"<div style='border:3px solid {bd};border-radius:14px;padding:8px 10px;"
            f"margin-bottom:8px;background:{bg};font-size:1.05rem;'>{short}{badge}</div>",
            unsafe_allow_html=True
        )

    if state["game_over"]:
        if state["winner"] == "Du":
            st.success(f"🏁 Spielende! **{state['winner']}** hat gewonnen. 🎉")
            try: st.balloons()
            except Exception: pass
        else:
            st.error(f"🏁 Spielende! **{state['winner']}** hat gewonnen. 😢")
            try: st.snow()
            except Exception: pass
        st.stop()
