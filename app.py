import os
from flask import Flask
from flask import request, render_template, redirect, flash
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
if not app.secret_key:
    raise RuntimeError("Configure a CHAVE SECRETA no arquivo .env")

#Usuario Temporario
USUARIO_TESTE_ID = 1

def conectar_banco():
#ABRE A CONEXAO COM MYSQL USANDO O ARQUIVO .ENV
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route("/")
def inicio():
    return "<h1>Bem-Vindo ao Sistema de Reserva de Sala do Senac</h1>"

@app.route("/salas")
def listar_salas():
    conexao = None
    cursor = None
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
                SELECT id_sala, nome, capacidade, tipo,
                descricao, ativa
                FROM sala
                ORDER BY id_sala
                """)
        salas = cursor.fetchall()
        return render_template("salas.html", salas=salas)
    except Error:
        app.logger.exception("Falha ao consultar salas")
        return render_template('erro.html', mensagem="Não foi possivel consultar as salas"), 500
    finally:
        if cursor: cursor.close()
        if conexao and conexao.is_connected(): conexao.close()

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
        ).time()
        hora_fim = datetime.strptime(
            request.form["hora_fim"], "%H:%M"
        ).time()
        finalidade = request.form["finalidade"].strip()

    except (KeyError, ValueError):
        flash("Dados Inválidos.", "danger")
        return redirect("/reservar")

    if hora_inicio >= hora_fim:
        flash("Horário final é inválido", "danger")
        return redirect ("/reservar")

    if data_reserva < date.today():
        flash("A data não pode estar no passado.", "danger")
        return redirect("/reservar")

    if not finalidade or len(finalidade) > 200:
        flash("Informe uma finalidade válida.", "danger")
        return redirect("/reservar")

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        #Verifica se a sala existe e está na ativa
        cursor.execute("""
            SELECT id_sala FROM sala
            WHERE id_sala = %s AND ativa = 1
            """,(id_sala,))

        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Sala indisponivel.", "danger")
            return redirect("/reservar")

        #Verifica conflito de horário
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM reserva
            WHERE id_sala = %s
                AND data_reserva = %s
                AND status = 'Confirmada'
                AND hora_inicio < %s
                AND hora_fim > %s
            """, (
                id_sala, data_reserva, hora_fim, hora_inicio))

        if cursor.fetchone()["total"] > 0:
            conexao.rollback()
            flash("Sala já reservada nesse horário.","danger")
            return redirect("/reservar")
        
        #Gravar a reserva
        cursor.execute("""
            INSERT INTO reserva
            (id_usuario, id_sala, data_reserva,
            hora_inicio, hora_fim, finalidade, status)
            VALUES
            (%s, %s , %s , %s , %s , %s , %s)""",(
            USUARIO_TESTE_ID, id_sala, data_reserva,
            hora_inicio, hora_fim, finalidade, "CONFIRMADA"
        ))
        conexao.commit()

        flash("Reserva realizada com sucesso!", "success")
        return redirect("/reservar")

    except Error:
        if conexao.in_transaction:
            conexao.rollback()
        app.logger.exception("Erro ao salvar a reserva")
        flash("Erro ao cadastrar a reserva", "danger")
        return redirect("/reservar")

    finally:
        cursor.close()
        conexao.close()

if __name__ == "__main__":
    app.run(debug=True)