import os
from flask import Flask, render_template
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
            SELECT id_sala, nome, capacidade,
            tipo, descricao, ativa
            FROM sala
            ORDER BY id_sala
            """)

    salas = cursor.fetchall()
    cursor.close()
    conexao.close()

    return render_template("salas.html", salas=salas)


if __name__ == "__main__":
    app.run(debug=True)