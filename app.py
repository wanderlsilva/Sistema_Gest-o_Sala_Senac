import os
from flask import Flask
from flask import (request, render_template, redirect, flash, url_for, session)
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from functools import wraps

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
if not app.secret_key:
    raise RuntimeError("Configure a CHAVE SECRETA no arquivo .env")

def login_obrigatorio(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if "id_usuario" not in session:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return verificar

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
@login_obrigatorio
def reservar():

    id_usuario = session["id_usuario"]

    if request.method == "GET":
        conexao = None
        cursor = None
        try:
            conexao = conectar_banco()
            cursor = conexao.cursor(dictionary=True)
            cursor.execute('SELECT id_sala, nome FROM sala WHERE ativa = 1 ORDER BY id_sala')
            salas = cursor.fetchall()
            return render_template("reservar.html", salas=salas)
        except Error:
            app.logger.exception('Falha ao carregar as salas')
            return render_template('erro.html', mensagem="Não foi possivel carregar o formulário."), 500
        finally:
            if cursor: cursor.close()
            if conexao and conexao.is_connected(): conexao.close()    

    #Lê e valida os dados enviados
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
        flash("Preencha os campos com dados válidos.", "danger")
        return redirect("/reservar")

    if hora_inicio >= hora_fim:
        flash("Horário final deve ser maior que o inicial", "danger")
        return redirect ("/reservar")

    if data_reserva < date.today():
        flash("A data não pode estar no passado.", "danger")
        return redirect("/reservar")

    if not finalidade or len(finalidade) > 200:
        flash("A finalidade deve ter entre 1 e 200 caracteres.", "danger")
        return redirect("/reservar")

    conexao = None
    cursor = None
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        conexao.start_transaction()
#Bloqueia a linha da sala durante a transação
#Todas as operações que alterem reservas seguem este código
        cursor.execute("""
            SELECT id_sala FROM sala
            WHERE id_sala = %s AND ativa = 1
            FOR UPDATE
            """,(id_sala,))
        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Sala inexistente ou inativa.", "danger")
            return redirect("/reservar")

        #Confere se o usuario temporario existe
        cursor.execute('SELECT id_usuario FROM usuario WHERE id_usuario = %s AND ativo = 1', (id_usuario,))
        if cursor.fetchone() is None:
            conexao.rollback()
            flash("Usuario de teste não cadastrado.")
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
            flash("Sala já reservada nesse horário.","warning")
            return redirect("/reservar")
        
        #Salva a reserva
        cursor.execute("""
            INSERT INTO reserva
            (id_usuario, id_sala, data_reserva,
            hora_inicio, hora_fim, finalidade, status)
            VALUES
            (%s, %s , %s , %s , %s , %s , %s)""",(
            id_usuario, id_sala, data_reserva,
            hora_inicio, hora_fim, finalidade, "Confirmada"
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

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    senha = request.form.get("senha", "")

    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("""
                SELECT id_usuario, nome, senha id_perfil
                FROM usuario
                WHERE email = %s
                AND ativo = 1""", (email,))

        usuario = cursor.fetchone()

        if not usuario or not check_password_hash(
            usuario ["senha"], senha
        ):
            flash("E-mail ou senha inválidos.", "danger")
            return redirect(url_for("login"))

        session.clear()

        session["id_usuario"] = usuario["id_usuario"]
        session["nome"] = usuario["nome"]
        session["id_perfil"] = usuario["id_perfil"]

        flash("Login realizado com sucesso!", "success")
        return redirect(url_for("reservar"))
    except:
        app.logger.exception("Erro durante o login")
        flash("Não foi possivel realizar o login.", "danger")
        return redirect(url_for("login"))

    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()

@app.route("/logout", methods=["POST"])
@login_obrigatorio
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=os.getenv('FLASK_DEBUG') == '1')