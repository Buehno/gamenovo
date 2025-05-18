from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# Armazena todas as salas e estado dos jogos
rooms = {}

# Ordem das cartas em força
CARD_ORDER = {"2": 1, "3": 2, "J": 3, "Q": 4, "K": 5, "A": 6}

@app.route("/")
def index():
    return redirect(url_for("lobby"))

@app.route("/lobby")
def lobby():
    return render_template("lobby.html")

@app.route("/room/<room_id>")
def room(room_id):
    if room_id not in rooms:
        return "Sala não existe", 404
    return render_template("sala.html", room_id=room_id)

@app.route("/create_or_join", methods=["POST"])
def create_or_join():
    username = request.form.get("username")
    amount = request.form.get("amount")
    room_id = request.form.get("room_id")

    if not username or not amount:
        return "Nome e valor da aposta são obrigatórios", 400

    amount = int(amount)
    if amount <= 0:
        return "Aposta deve ser positiva", 400

    # Criar sala nova
    if not room_id:
        room_id = str(uuid.uuid4())[:8]
        rooms[room_id] = {
            "players": {
                1: {"username": username, "money": amount, "card": None},
                2: None
            },
            "bet": amount,
            "turns": 0,
            "round_result": None,
            "game_over": False
        }
        return redirect(url_for("room", room_id=room_id))

    # Entrar em sala existente
    if room_id not in rooms:
        return "Sala não existe", 404

    room = rooms[room_id]
    if room["players"][2] is not None:
        return "Sala cheia", 400

    room["players"][2] = {"username": username, "money": amount, "card": None}

    # Atualiza aposta para ser igual para ambos (mínimo entre os dois)
    min_bet = min(room["bet"], amount)
    room["bet"] = min_bet
    room["players"][1]["money"] = max(room["players"][1]["money"], min_bet)
    room["players"][2]["money"] = max(room["players"][2]["money"], min_bet)

    return redirect(url_for("room", room_id=room_id))

@app.route("/state/<room_id>")
def state(room_id):
    if room_id not in rooms:
        return jsonify({"error": "Sala não existe"}), 404
    room = rooms[room_id]
    return jsonify(room)

@app.route("/play_card/<room_id>", methods=["POST"])
def play_card(room_id):
    if room_id not in rooms:
        return jsonify({"error": "Sala não existe"}), 404

    data = request.json
    player_num = data.get("player_num")
    card = data.get("card")

    if player_num not in [1, 2]:
        return jsonify({"error": "Jogador inválido"}), 400
    if card not in CARD_ORDER:
        return jsonify({"error": "Carta inválida"}), 400

    room = rooms[room_id]
    if room["game_over"]:
        return jsonify({"error": "Jogo finalizado"}), 400

    player = room["players"].get(player_num)
    if player is None:
        return jsonify({"error": "Jogador não está na sala"}), 400

    # Salvar carta jogada
    player["card"] = card

    # Verificar se ambos jogaram para decidir rodada
    p1 = room["players"][1]
    p2 = room["players"][2]
    if p1 is None or p2 is None:
        return jsonify({"error": "Esperando outro jogador"}), 400

    if p1["card"] is not None and p2["card"] is not None:
        # Decidir vencedor
        c1 = CARD_ORDER[p1["card"]]
        c2 = CARD_ORDER[p2["card"]]
        if c1 > c2:
            winner = 1
            loser = 2
        elif c2 > c1:
            winner = 2
            loser = 1
        else:
            winner = None  # empate

        if winner:
            bet = room["bet"]
            room["players"][winner]["money"] += bet
            room["players"][loser]["money"] -= bet

            # Reset cartas
            p1["card"] = None
            p2["card"] = None

            room["round_result"] = {
                "winner": winner,
                "winner_name": room["players"][winner]["username"],
                "loser": loser,
                "loser_name": room["players"][loser]["username"],
                "winner_card": room["players"][winner]["card"],
                "loser_card": room["players"][loser]["card"],
                "bet": bet,
            }

            # Verificar falência
            if room["players"][loser]["money"] <= 0:
                room["game_over"] = True
                room["round_result"]["game_over"] = True
                room["round_result"]["loser_bankrupt"] = True
            else:
                room["round_result"]["game_over"] = False

            return jsonify({"result": room["round_result"], "state": room})

        else:
            # empate - reset cartas
            p1["card"] = None
            p2["card"] = None
            room["round_result"] = {"winner": None, "message": "Empate, rodada anulada"}
            return jsonify({"result": room["round_result"], "state": room})

    return jsonify({"message": "Carta registrada. Esperando outro jogador", "state": room})


if __name__ == "__main__":
    app.run(debug=True)
