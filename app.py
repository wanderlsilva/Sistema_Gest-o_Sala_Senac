import os
from flask import Flask, render_template
from flask import request, render_template, redirect, flash
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

def conectar_banco():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route("/")
def inicio():
    return "<h1>Bem-Vindo ao Senac Reserva</h1>"

@app.route("/salas")
def listar_salas():
    conexao = conectar_banco()

    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
            SELECT id_sala, nome, capacidade, tipo,
            descricao, ativa
            FROM sala
            ORDER BY id_sala
            """)

    salas = cursor.fetchall()
    cursor.close()
    conexao.close()

    return render_template("salas.html", salas=salas)

USUARIO_TESTE_ID = 1

@app.route("/reservar", methods=["GET", "POST"])
def reservar():
    if request.method == "GET":
        return render_template("reservar.html")

    try:
        id_sala = int(request.form["id_sala"])
        data_reserva = date.fromisoformat(
            request.form["data_reserva"]
        )
        hora_inicio = datetime.strptime(
            request.form["hora_inicio"], "%H:%M"
        ).time
        hora_fim = datetime.strptime(
            request.form["hora_fim"], "%H:%M"
        ).time
        finalidade = request.form["finalidade"].strip()
    except (KeyError, ValueError):
        flash("Dados Inválidos.", "danger")

        if hora_inicio >= hora_fim:
            flash("Horário final é inválido", "danger")
            return redirect ("/reservar")

        if data_reserva < date.today():
            flash("A data não pode estar no passado.", "danger")
            return redirect("/reservar")

        if not finalidade or len(finalidade) > 200:
            flash("Informe uma finalidade válida.", "danger")
            return redirect("/reservar")

        

if __name__ == "__main__":
    app.run(debug=True)