import os
from flask import Flask
from flask import (request, render_template, redirect, flash, url_for, session)
from datetime import date, datetime
from mysql.connector import Error
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import timedelta

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
@login_obrigatorio
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

    if request.method == "GET":
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        try:
            cursor.execute(""" SELECT id_sala, nome
                            FROM sala
                            WHERE ativa = 1
                            ORDER BY nome""")
            salas = cursor.fetchall()
        finally:
            cursor.close()
            conexao.close()
        return render_template("reservar.html", salas=salas)
    
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
                SELECT id_usuario, nome, email, senha, id_perfil
                FROM usuario
                WHERE email = %s
                AND ativo = 1""", (email,))

        usuario = cursor.fetchone()

        if not usuario or not check_password_hash(
            usuario["senha"], senha
        ):
            flash("E-mail ou senha inválidos.", "danger")
            return redirect(url_for("login"))

        session.clear()

        session["id_usuario"] = usuario["id_usuario"]
        session["nome"] = usuario["nome"]
        session["id_perfil"] = usuario["id_perfil"]

        flash("Login realizado com sucesso!", "success")
        return redirect(url_for("dashboard"))
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

@app.route("/minhas_reservas")
@login_obrigatorio
def minhas_reservas():
    id_usuario = session["id_usuario"]
    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("""
                SELECT r.id_reserva, s.nome AS nome_sala,
                r.data_reserva, r.hora_inicio, r.hora_fim,
                r.finalidade, r.status 
                FROM reserva AS r
                INNER JOIN sala AS s ON r.id_sala = s.id_sala
                WHERE r.id_usuario = %s
                ORDER BY 
                r.data_reserva DESC,
                r.hora_inicio DESC""", (id_usuario,))

        reservas = cursor.fetchall()
        return render_template("minhas_reservas.html", reservas=reservas)
    
    except Exception:
        app.logger.exception("Erro ao consultar reservas")
        flash("Não foi possivel consultar suas reservas.", "danger")
        return redirect(url_for("minhas_reservas"))
    
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()

@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    return render_template("dashboard.html")

@app.route("/reservas/<int:id_reserva>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_reserva(id_reserva):
    id_usuario = session["id_usuario"]
    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        conexao.start_transaction()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("""
                SELECT
                id_reserva, id_usuario, id_sala, data_reserva,
                hora_inicio, hora_fim, finalidade, status
                FROM reserva
                WHERE id_reserva = %s
                AND id_usuario = %s
                AND status = 'Confirmada'
                """,(id_reserva, id_usuario))
        reserva = cursor.fetchone()

        if reserva is None:
            flash("Reserva não encontrada ou sem permissão.", "danger")
            return redirect( url_for("minhas_reservas"))
        
        cursor.execute("""
                SELECT id_sala, nome
                FROM sala
                WHERE ativa = 1
                ORDER BY nome""")
        salas = cursor.fetchall()

        if request.method == "GET":
            reserva["hora_inicio"] = formatar_hora(reserva["hora_inicio"])
            reserva["hora_fim"] = formatar_hora(reserva["hora_fim"])

            return render_template("editar_reserva.html", reserva=reserva, salas=salas)

        id_sala = request.form.get("id_sala", type=int)
        data_reserva = request.form.get("data_reserva", "")
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fim = request.form.get("hora_fim", "")
        finalidade = request.form.get("finalidade", "").strip()

        if not all([
            id_sala,
            data_reserva,
            hora_inicio,
            hora_fim,
            finalidade
        ]):
            flash("Preencha todos os campos.", "warning")
            return redirect(request.url)
        try:
            data_obj = date.fromisoformat(data_reserva)
            inicio_ojb = datetime.strptime(hora_inicio, "%H:%M").time()
            fim_obj = datetime.strptime(hora_fim, "%H:%M").time()
        except ValueError:
            flash("Data ou horário inválido.", "danger")
            return redirect(request.url)
        if data_obj < date.today():
            flash("Não é permitido reservar datas passadas.", "warning")
            return redirect(request.url)
        if inicio_ojb >= fim_obj:
            flash("A hora inicial deve ser menor que a final.", "warning")
            return redirect(request.url)

        cursor.execute("""
                    SELECT id_sala
                    FROM sala
                    WHERE id_sala = %s
                    AND ativa = 1
                    FOR UPDATE""", (id_sala,))

        sala = cursor.fetchone()
        if sala is None:
            flash("A sala selecionada está indisponível.", "danger")
            return redirect(request.url)

        cursor.execute("""
                SELECT COUNT(*) AS total
                FROM reserva
                WHERE id_sala = %s
                AND data_reserva = %s
                AND status = 'Confirmada'
                AND hora_inicio < %s
                AND hora_fim > %s
                AND id_reserva <> %s""",
                (
                    id_sala,
                    data_reserva,
                    hora_fim,
                    hora_inicio,
                    id_reserva
                ))
        resultado = cursor.fetchone()
        if resultado["total"] > 0:
            flash("Já existe uma reserva nesse horário.", "danger")
            return redirect(request.url)

        cursor.execute("""
            UPDATE reserva
            SET
                id_sala = %s,
                data_reserva = %s,
                hora_inicio = %s,
                hora_fim = %s,
                finalidade = %s
                WHERE id_reserva = %s
                AND id_usuario = %s
                AND status = 'Confirmada'""",
                (
                    id_sala,
                    data_reserva,
                    hora_inicio,
                    hora_fim,
                    finalidade,
                    id_reserva,
                    id_usuario
                ))
        conexao.commit()
        flash("Reserva atualizada com sucesso!","success")
        return redirect(url_for("minhas_reservas"))

    except Exception as erro:
        if conexao is not None:
            conexao.rollback()

        app.logger.exception("Erro ao editar reserva")
        flash("Não foi possivel atualizar a reserva.", "danger")
        return redirect(url_for("minhas_reservas"))
        
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()

def formatar_hora(valor):
    if isinstance(valor, timedelta):
        total_segundos = int(valor.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60

        return f"{horas:02d}:{minutos:02d}"
    return str(valor)[:5] 

@app.route("/reservas/<int:id_reserva>/cancelar", methods=["POST"])
@login_obrigatorio
def cancelar_reserva(id_reserva):
    id_usuario = session["id_usuario"]

    conexao = None
    cursor = None

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
                UPDATE reserva
                SET status = 'Cancelada'
                WHERE id_reserva = %s
                    AND id_usuario = %s
                    AND status = 'Confirmada'
                    """, (id_reserva, id_usuario))
        if cursor.rowcount == 0:
            conexao.rollback()

            flash("Reserva não encontrada", "warning")

            return redirect( url_for("minhas_reservas"))

        conexao.commit()

        flash("Reserva cancelada com sucesso!", "success")
        return redirect( url_for("minhas_reservas"))

    except Exception:
        if conexao is not None:
            conexao.rollback()
            app.logger.exception("Erro ao cancelar a reserva")
            flash("Não foi possivel cancelar a reserva", "danger")
            return redirect( url_for("minhas_reservas"))
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()
            
if __name__ == "__main__":
    app.run(debug=os.getenv('FLASK_DEBUG') == '1')