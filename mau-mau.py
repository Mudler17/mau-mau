import random
import time
import html
import os
import streamlit as st

# ---------- Rerun-Wrapper ----------
def RERUN():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ---------- Spielkonfiguration ----------
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]
PLAYERS = ["Du", "Spieler 1", "Spieler 2"]
START_CARDS = 5

# Farben & Bilder (Bilder: gleicher Ordner wie diese Datei)
PLAYER_BG = {"Du":"#e7f0ff","Spieler 1":"#e8f7ee","Spieler 2":"#fff7d6","System":"#f2f2f2"}
PLAYER_BORDER = {"Du":"#6aa0ff","Spieler 1":"#45c08b","Spieler 2":"#e5c300","System":"#e0e0e0"}
PLAYER_IMG = {"Du":None, "Spieler 1":"spieler.png", "Spieler 2":"spielerin.png"}

# ---------- Darstellung ----------
def emoji_suit(s): return {"♥":"♥️","♦":"♦️","♠":"♠","♣":"♣"}[s]
def suit_color(s): return "#d00" if s in ("♥","♦") else "#111"
def card_str(card): r,s=card; return f"{r}{s}"

def card_html(card, size="md"):
    r,s = card
    col = suit_color(s)
    pads = {"sm":"6px 10px","md":"10px 14px","lg":"14px 18px","xl":"22px 28px"}
    fonts = {"sm":"1.0rem","md":"1.15rem","lg":"1.35rem","xl":"1.8rem"}
    brds = {"sm":"2px","md":"3px","lg":"4px","xl":"5px"}
    return f"""
    <div style="
      display:inline-block;padding:{pads[size]};margin:6px 6px 10px 0;
      border:{brds[size]} solid {col};border-radius:16px;font-weight:900;
      font-size:{fonts[size]};letter-spacing:.2px;
      font-family: ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;
      color:{col};background:#fff;box-shadow:0 2px 5px rgba(0,0,0,.1);user-select:none;">
      {html.escape(r)}{emoji_suit(s)}
    </div>
    """

def suit_badge_html(s):
    col=suit_color(s)
    return f"<span style='border:2px solid {col};color:{col};padding:1px 8px;border-radius:10px;font-weight:800;background:#fff;margin-left:6px'>{emoji_suit(s)}</span>"

# ---------- State-Setup ----------
def init_session():
    st.session_state.initialized=True
    st.session_state.state={}
    start_game(st.session_state.state)

def new_deck(): return [(r,s) for s in SUITS for r in RANKS]

def start_game(state):
    deck=new_deck(); random.shuffle(deck)
    hands={p:[] for p in PLAYERS}
    for _ in range(START_CARDS):
        for p in PLAYERS: hands[p].append(deck.pop())
    top=deck.pop()
    while top[0]=="J":
        deck.insert(0,top); random.shuffle(deck); top=deck.pop()
    state.update(dict(
        hands=hands, draw_pile=deck, discards=[top],
        current=0, wished_suit=None, pending_draw=0, skip_next=False,
        winner=None, game_over=False,
        # kurzer Log: (speaker, msg, card_or_None, wished_or_None)
        log=[("System", f"Start {card_str(top)}", top, None)],
        awaiting_wish=False,
        last_action={p: {"card":None,"quip":None,"ts":0.0} for p in PLAYERS},
        step_pause=0.7,       # sichtbare Pause zwischen Zügen
        pause_until=0.0       # Timestamp bis wann pausiert wird
    ))

# ---------- Engine ----------
def reshuffle_if_needed(state):
    if not state["draw_pile"]:
        if len(state["discards"])<=1: return
        top=state["discards"][-1]; pool=state["discards"][:-1]
        random.shuffle(pool); state["draw_pile"]=pool; state["discards"]=[top]
        state["log"].append(("System","Ziehstapel gemischt",None,None))

def draw_cards(state, player, n):
    for _ in range(n):
        reshuffle_if_needed(state)
        if not state["draw_pile"]: break
        state["hands"][player].append(state["draw_pile"].pop())

def can_play(card, top_card, wished_suit):
    r,s=card
    if wished_suit: return r=="J" or s==wished_suit
    return r=="J" or r==top_card[0] or s==top_card[1]

def end_if_winner(state, player):
    if len(state["hands"][player])==0:
        state["winner"]=player; state["game_over"]=True; return True
    return False

def quip(action):
    return random.choice({
        "play":["Taktische Eleganz.","Nur Statistik.","Kalkuliert. Irgendwie.","Elegant wie ein Presslufthammer 😎"],
        "draw":["Sammelkartenmodus.","Ich liebe Überraschungen 🎁","Nur eine — was soll schiefgehen?"],
        "skip":["Nur kurz raus.","Kein Timing, ehrlich."],
        "wish":["Ich wünsche mir … genau das.","Wunsch frei, Realität folgt."],
    }[action])

def mark_last_action(state, player, card=None, q=None):
    state["last_action"][player]={"card":card,"quip":q,"ts":time.time()}
    state["pause_until"]=time.time()+state["step_pause"]

def play_card(state, player, card):
    state["hands"][player].remove(card)
    state["discards"].append(card)
    state["wished_suit"]=None
    state["log"].append((player, f"legt {card_str(card)}", card, None))
    if card[0]=="7": state["pending_draw"]+=2
    elif card[0]=="8": state["skip_next"]=True
    if end_if_winner(state, player): return

def enforce_pending_draw(state):
    cur=PLAYERS[state["current"]]
    if state["pending_draw"]>0:
        top=state["discards"][-1]
        can_stack=any((c[0]=="7") and can_play(c,top,state["wished_suit"]) for c in state["hands"][cur])
        if not can_stack:
            draw_cards(state,cur,state["pending_draw"])
            state["log"].append((cur,f"zieht {state['pending_draw']}",None,None))
            mark_last_action(state,cur,None,quip("draw"))
            state["pending_draw"]=0
            return True
    return False

def advance_turn(state): state["current"]=(state["current"]+1)%len(PLAYERS)

def bot_choose_wish(hand):
    suit_counts={s:0 for s in SUITS}
    for r,s in hand: suit_counts[s]+=1
    return max(suit_counts.items(), key=lambda x:(x[1],random.random()))[0]

def do_one_bot_step(state):
    """Genau EINEN Schritt machen und pausieren -> Animation sichtbar."""
    if state["game_over"]: return
    player = PLAYERS[state["current"]]
    if player=="Du": return

    if enforce_pending_draw(state):
        advance_turn(state); mark_last_action(state, player, None, quip("draw")); return

    hand=state["hands"][player]; top=state["discards"][-1]
    playable=[c for c in hand if can_play(c,top,state["wished_suit"])]

    if not playable:
        reshuffle_if_needed(state)
        if state["draw_pile"]:
            drawn=state["draw_pile"].pop(); hand.append(drawn)
            state["log"].append((player,"zieht 1",None,None))
            mark_last_action(state,player,None,quip("draw"))
        else:
            state["log"].append((player,"kann nicht ziehen",None,None))
            mark_last_action(state,player,None,quip("draw"))
            advance_turn(state)
        return

    # Simple Heuristik
    def score(c):
        if c[0]=="7": return 0
        if c[0]=="8": return 1
        if c[0]=="J": return 3
        return 2
    playable.sort(key=score)
    chosen=playable[0]
    play_card(state, player, chosen)
    if state["game_over"]:
        # Animation beim Endstand
        if state["winner"]=="Du":
            try: st.balloons()
            except: pass
        else:
            try: st.snow()
            except: pass
        mark_last_action(state, player, chosen, "Matchball!")
        return
    mark_last_action(state, player, chosen, quip("play"))
    if chosen[0]=="J":
        wish=bot_choose_wish(hand)
        state["wished_suit"]=wish
        state["log"].append((player,"wünscht",None,wish))
        mark_last_action(state, player, None, quip("wish"))

    if state["skip_next"] and not state["game_over"]:
        nxt=PLAYERS[(state["current"]+1)%len(PLAYERS)]
        state["log"].append(("System",f"{nxt} aussetzen",None,None))
        mark_last_action(state, player, None, quip("skip"))
        advance_turn(state); state["skip_next"]=False
        return

    if not state["game_over"]:
        advance_turn(state)

# ---------- UI ----------
st.set_page_config(page_title="Mau-Mau (32 Karten)", page_icon="🃏", layout="wide")
st.title("🃏 Mau-Mau · 32 Karten (Skat) — 2 Spieler + Du")

if "initialized" not in st.session_state: init_session()
state = st.session_state.state

left, right = st.columns([5,3], gap="large")

with left:
    with st.sidebar:
        st.header("Spielkontrolle")
        if st.button("🔁 Neues Spiel", use_container_width=True):
            start_game(state); RERUN()
        st.caption("Regeln: 7=+2, 8=Aussetzen, J=Bube wünscht Farbe.")

    # --- Pause-Modus für Animation: nichts tun, nur warten & neu rendern ---
    now = time.time()
    if state.get("pause_until", 0) > now:
        time.sleep(max(0.05, state["pause_until"] - now))
        RERUN()

    # Zentrale große Ablage
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    center = st.columns([1,1,1])
    with center[1]:
        st.markdown(card_html(state["discards"][-1], size="xl"), unsafe_allow_html=True)

    # Statuszeile
    cols=st.columns(4)
    cols[0].markdown(f"<b>Aktuell:</b> {html.escape(PLAYERS[state['current']])}", unsafe_allow_html=True)
    cols[1].markdown(f"<b>Wunsch:</b> {html.escape(state['wished_suit'] or '—')}", unsafe_allow_html=True)
    cols[2].markdown(f"<b>Ziehstapel:</b> {len(state['draw_pile'])}", unsafe_allow_html=True)
    cols[3].markdown(f"<b>Abwurf:</b> {len(state['discards'])}", unsafe_allow_html=True)

    # Spieler-Panels (mit Bild) + Mini-Overlay (Karte & Spruch)
    pc = st.columns(3)
    for col, p in zip(pc, PLAYERS):
        with col:
            bg=PLAYER_BG[p]; bd=PLAYER_BORDER[p]
            with st.container():
                top_row = st.columns([1,3]) if PLAYER_IMG[p] else st.columns([1])
                if PLAYER_IMG[p]:
                    img_path = os.path.join(os.getcwd(), PLAYER_IMG[p])
                    try:
                        top_row[0].image(img_path, width=72)
                    except Exception:
                        pass
                    with top_row[1]:
                        st.markdown(f"<div style='font-weight:900;font-size:1.1rem'>{html.escape(p)}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div>Karten: <b>{len(state['hands'][p])}</b></div>", unsafe_allow_html=True)
                else:
                    with top_row[0]:
                        st.markdown(f"<div style='font-weight:900;font-size:1.1rem'>{html.escape(p)}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div>Karten: <b>{len(state['hands'][p])}</b></div>", unsafe_allow_html=True)

            # Overlay der letzten Aktion (max ~1 Sekunde sichtbar; wird durch pause_until via RERUN erzwungen)
            la = state["last_action"].get(p, {})
            if la and (now - la.get("ts", 0)) < 1.2:
                if la.get("card"):
                    st.markdown(card_html(la["card"], size="lg"), unsafe_allow_html=True)
                if la.get("quip"):
                    st.markdown(f"<div style='opacity:.9'><em>{html.escape(la['quip'])}</em></div>", unsafe_allow_html=True)

    st.divider()

    # --- Bot macht genau einen Schritt pro Render (Animation sichtbar) ---
    if not state["game_over"] and PLAYERS[state["current"]] != "Du" and not state.get("awaiting_wish"):
        do_one_bot_step(state)
        RERUN()

    # --- Dein Zug ---
    if state["game_over"]:
        pass
    elif state.get("awaiting_wish"):
        st.info("Du hast einen Buben gespielt. Wähle eine Wunschfarbe:")
        wc = st.columns(4); picked=None
        for i,s in enumerate(SUITS):
            if wc[i].button(emoji_suit(s), key=f"wish_{s}"): picked=s
        if picked:
            state["wished_suit"]=picked
            state["log"].append(("Du","wünscht",None,picked))
            mark_last_action(state,"Du",None,quip("wish"))
            advance_turn(state); RERUN()
        st.stop()
    else:
        hand = state["hands"]["Du"]; top = state["discards"][-1]

        # Pflichtziehen (7)
        if PLAYERS[state["current"]] == "Du" and state["pending_draw"]>0:
            can_stack = any((c[0]=="7") and can_play(c, top, state["wished_suit"]) for c in hand)
            if not can_stack:
                if st.button(f"😬 {state['pending_draw']} Karten ziehen", type="primary"):
                    draw_cards(state,"Du",state["pending_draw"])
                    state["log"].append(("Du",f"zieht {state['pending_draw']}",None,None))
                    mark_last_action(state,"Du",None,quip("draw"))
                    state["pending_draw"]=0
                    advance_turn(state); RERUN()

        playable=[c for c in hand if can_play(c, top, state["wished_suit"])]
        unplayable=[c for c in hand if c not in playable]

        grid = st.columns(6)
        for idx,c in enumerate(playable):
            with grid[idx%6]:
                st.markdown(card_html(c, size="md"), unsafe_allow_html=True)
                if st.button(f"🂡 Legen: {card_str(c)}", key=f"play_{c[0]}_{c[1]}_{idx}"):
                    play_card(state,"Du",c)
                    if state["game_over"]:
                        try: st.balloons()
                        except: pass
                        RERUN()
                    mark_last_action(state,"Du",c,quip("play"))
                    if c[0]=="J": state["awaiting_wish"]=True; RERUN()
                    if state["skip_next"]:
                        nxt=PLAYERS[(state["current"]+1)%len(PLAYERS)]
                        state["log"].append(("System",f"{nxt} aussetzen",None,None))
                        mark_last_action(state,"Du",None,quip("skip"))
                        advance_turn(state); state["skip_next"]=False
                    advance_turn(state); RERUN()

        if unplayable:
            st.caption("Nicht spielbar:")
            ugrid=st.columns(6)
            for idx,c in enumerate(unplayable):
                with ugrid[idx%6]:
                    st.markdown(card_html(c, size="sm"), unsafe_allow_html=True)

        draw_disabled = state["pending_draw"]>0 and PLAYERS[state["current"]]=="Du"
        if st.button("🂠 1 Karte ziehen", disabled=draw_disabled):
            reshuffle_if_needed(state)
            if state["draw_pile"]:
                drawn=state["draw_pile"].pop(); state["hands"]["Du"].append(drawn)
                state["log"].append(("Du","zieht 1",None,None))
                mark_last_action(state,"Du",None,quip("draw"))
            else:
                state["log"].append(("System","Ziehstapel leer",None,None))
            advance_turn(state); RERUN()

with right:
    st.subheader("🗒️ Verlauf (kurz · neueste oben)")
    for entry in reversed(state["log"][-140:]):
        sp,msg,c,w=("System","",None,None)
        if isinstance(entry,(list,tuple)):
            if len(entry)>=1: sp=entry[0]
            if len(entry)>=2: msg=entry[1]
            if len(entry)>=3: c=entry[2]
            if len(entry)>=4: w=entry[3]
        bg=PLAYER_BG.get(sp,"#fff"); bd=PLAYER_BORDER.get(sp,"#ccc")
        line=f"{html.escape(sp)}: {html.escape(msg)}"
        badge = suit_badge_html(w) if w in SUITS else ""
        st.markdown(
            f"<div style='border:3px solid {bd};border-radius:14px;padding:8px 10px;margin-bottom:8px;background:{bg}'>{line}{badge}</div>",
            unsafe_allow_html=True
        )

    if state["game_over"]:
        if state["winner"]=="Du":
            st.success(f"🏁 {state['winner']} gewinnt! 🎉"); 
            try: st.balloons()
            except: pass
        else:
            st.error(f"🏁 {state['winner']} gewinnt. 😢"); 
            try: st.snow()
            except: pass
        st.stop()
