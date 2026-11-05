import os
import shutil
import uuid
import socket
import threading
import time
import csv
import io
import zipfile
import traceback
import sqlite3
from datetime import datetime, timedelta
from functools import lru_cache, wraps

import pikepdf
import pymupdf
from flask import (
    Flask, request, render_template, render_template_string,
    send_file, jsonify, session, redirect, url_for, g, has_request_context,
)
from pdf2docx import Converter
from pypdf import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or uuid.uuid4().hex
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# ---------------------------------------------------------------------
# PASTA DE LOGS - fica isolada do resto do projeto, só com dados de log.
# Tudo (acessos e sessões de visitantes) vive no mesmo banco SQLite
# dentro dela, em tabelas separadas.
# ---------------------------------------------------------------------
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_LOGS = os.path.join(LOG_DIR, "acessos.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

LIMITE_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
app.config["MAX_CONTENT_LENGTH"] = LIMITE_UPLOAD_MB * 1024 * 1024

EXTENSOES_PDF = {"pdf"}


def extensao_valida(nome_arquivo, extensoes_permitidas):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in extensoes_permitidas


def parse_paginas_selecionadas(texto_paginas, total_paginas):
    """Converte uma seleção como '1-5, 3, 10, 50' em uma lista de páginas.
    Se o texto estiver vazio, retorna todas as páginas do PDF."""
    texto = (texto_paginas or "").strip()
    if not texto:
        return list(range(1, total_paginas + 1))

    paginas = []
    for item in texto.split(","):
        parte = item.strip()
        if not parte:
            continue

        if "-" in parte:
            try:
                inicio_texto, fim_texto = [p.strip() for p in parte.split("-", 1)]
                inicio = int(inicio_texto)
                fim = int(fim_texto)
            except ValueError as exc:
                raise ValueError(f"Intervalo inválido: '{parte}'. Use exemplos como '1-5' ou '10-15'.") from exc
            if inicio > fim:
                raise ValueError(f"Intervalo inválido: '{parte}'. O início precisa ser menor ou igual ao fim.")
            paginas.extend(range(inicio, fim + 1))
        else:
            try:
                paginas.append(int(parte))
            except ValueError as exc:
                raise ValueError(f"Página inválida: '{parte}'. Use números como 1, 3, 10 ou intervalos como 1-5.") from exc

    paginas = sorted(set(paginas))
    invalidas = [pagina for pagina in paginas if pagina < 1 or pagina > total_paginas]
    if invalidas:
        raise ValueError(
            f"Páginas fora do intervalo do PDF: {invalidas[:5]} "
            f"(o documento tem {total_paginas} página(s))."
        )

    return paginas


def conectar_db():
    conexao = sqlite3.connect(DB_LOGS, timeout=30)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA busy_timeout = 30000")
    return conexao


def iniciar_db():
    with conectar_db() as conexao:
        conexao.execute("PRAGMA journal_mode = WAL")
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS acessos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT NOT NULL,
                ip TEXT NOT NULL,
                hostname TEXT DEFAULT '',
                metodo TEXT NOT NULL,
                rota TEXT NOT NULL,
                qtd_arquivos INTEGER NOT NULL DEFAULT 0,
                nomes_arquivos TEXT DEFAULT '',
                duracao_ms REAL DEFAULT 0,
                visitor_id TEXT DEFAULT ''
            )
        """)

        # migração leve: adiciona colunas que possam faltar em bancos
        # de versões anteriores do app
        colunas = [linha["name"] for linha in conexao.execute("PRAGMA table_info(acessos)")]
        if "nomes_arquivos" not in colunas:
            conexao.execute("ALTER TABLE acessos ADD COLUMN nomes_arquivos TEXT DEFAULT ''")
        if "hostname" not in colunas:
            conexao.execute("ALTER TABLE acessos ADD COLUMN hostname TEXT DEFAULT ''")
        if "duracao_ms" not in colunas:
            conexao.execute("ALTER TABLE acessos ADD COLUMN duracao_ms REAL DEFAULT 0")
        if "visitor_id" not in colunas:
            conexao.execute("ALTER TABLE acessos ADD COLUMN visitor_id TEXT DEFAULT ''")

        # ---------------------------------------------------------
        # SESSÕES DE VISITANTES - controla quem entrou/saiu do site
        # e quem está online agora, via um cookie de visitante que
        # é atualizado por "heartbeats" enviados pelo navegador
        # ---------------------------------------------------------
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                ip TEXT NOT NULL,
                hostname TEXT DEFAULT '',
                entrada TEXT NOT NULL,
                ultima_atividade TEXT NOT NULL,
                saida TEXT
            )
        """)

        col_sessoes = [linha["name"] for linha in conexao.execute("PRAGMA table_info(sessoes)")]
        if "hostname" not in col_sessoes:
            conexao.execute("ALTER TABLE sessoes ADD COLUMN hostname TEXT DEFAULT ''")

        # ---------------------------------------------------------
        # ERROS - registra falhas (500, exceções nas rotas de API,
        # etc.) com o local, a mensagem e uma sugestão de resolução
        # ---------------------------------------------------------
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS erros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT NOT NULL,
                ip TEXT NOT NULL,
                hostname TEXT DEFAULT '',
                rota TEXT NOT NULL,
                metodo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                traceback TEXT DEFAULT '',
                resolucao TEXT DEFAULT ''
            )
        """)


iniciar_db()

# considera o visitante "offline" se não mandar heartbeat por mais desse
# tempo (o front-end manda um a cada 60s, então 150s dá uma folga)
TIMEOUT_ONLINE_SEGUNDOS = 150


# ---------------------------------------------------------------------
# LIMPEZA DE SAÍDAS - os arquivos gerados em OUTPUT_DIR não eram apagados
# após o download, então acumulavam e enchiam o disco. Aqui removemos os
# arquivos/pastas mais antigos que IDADE_MAX_OUTPUTS, de forma periódica.
# ---------------------------------------------------------------------
ULTIMA_LIMPEZA_OUTPUTS = 0.0          # epoch da última limpeza
INTERVALO_LIMPEZA_OUTPUTS = 300       # roda no máx. a cada 5 min
IDADE_MAX_OUTPUTS = 60 * 60           # apaga o que tiver mais de 1 hora


def limpar_outputs_antigos():
    """Remove de OUTPUT_DIR arquivos e pastas com mais de IDADE_MAX_OUTPUTS.
    Ignora arquivos ocultos (ex.: .gitkeep) para não apagar placeholders."""
    agora = time.time()
    try:
        nomes = os.listdir(OUTPUT_DIR)
    except OSError:
        return
    for nome in nomes:
        if nome.startswith("."):
            continue
        caminho = os.path.join(OUTPUT_DIR, nome)
        try:
            if agora - os.path.getmtime(caminho) > IDADE_MAX_OUTPUTS:
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho, ignore_errors=True)
                else:
                    os.remove(caminho)
        except OSError:
            pass


def limpar_uploads_antigos():
    """Remove uploads abandonados após uma interrupção do processamento."""
    agora = time.time()
    try:
        nomes = os.listdir(UPLOAD_DIR)
    except OSError:
        return
    for nome in nomes:
        if nome.startswith("."):
            continue
        caminho = os.path.join(UPLOAD_DIR, nome)
        try:
            if agora - os.path.getmtime(caminho) > IDADE_MAX_OUTPUTS:
                if os.path.isdir(caminho):
                    shutil.rmtree(caminho, ignore_errors=True)
                else:
                    os.remove(caminho)
        except OSError:
            pass


@app.before_request
def marcar_inicio():
    """Marca o horário de início da requisição para medir o desempenho e
    dispara a limpeza periódica das saídas (anti acúmulo de disco)."""
    g.inicio = time.perf_counter()

    global ULTIMA_LIMPEZA_OUTPUTS
    if time.time() - ULTIMA_LIMPEZA_OUTPUTS > INTERVALO_LIMPEZA_OUTPUTS:
        ULTIMA_LIMPEZA_OUTPUTS = time.time()
        try:
            limpar_outputs_antigos()
            limpar_uploads_antigos()
        except Exception:
            pass


def obter_ip_real():
    """Pega o IP real do visitante, mesmo se o site estiver atrás de
    um proxy/reverse proxy (ex: Nginx, Cloudflare)."""
    encaminhado = request.headers.get("X-Forwarded-For")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.remote_addr


@lru_cache(maxsize=1024)
def obter_hostname(ip):
    """Resolve o nome da máquina a partir do IP (rede fechada/prefeitura).
    Roda com timeout: se a resolução demorar (rede sem DNS reverso), devolve
    o próprio IP em vez de travar a requisição por até 5s."""
    if not ip:
        return ip
    resultado = {"nome": ip}

    def resolver():
        try:
            resultado["nome"] = socket.gethostbyaddr(ip)[0] or ip
        except Exception:
            resultado["nome"] = ip

    th = threading.Thread(target=resolver, daemon=True)
    th.start()
    th.join(timeout=1.5)  # nunca espera mais que 1.5s por requisição
    return resultado["nome"]


def sugerir_resolucao(tipo, mensagem):
    """Tenta dar uma dica de como resolver o erro com base no tipo e
    na mensagem. É uma heurística simples, não substitui o traceback."""
    texto = f"{tipo} {mensagem}".lower()
    if "dll" in texto or "module not found" in texto or "importerror" in texto:
        return ("Falta uma biblioteca/dependência do sistema. Se for DLL do Windows, "
                "instale o Visual C++ Redistributable (vc_redist.x64.exe) e reinicie. "
                "Se for 'No module named', rode: pip install -r requirements.txt")
    if "no module named" in texto:
        return "Dependência do Python ausente. Rode: pip install -r requirements.txt"
    if "permission" in texto or "permissionerror" in texto:
        return ("Permissão negada. Verifique as permissões de escrita das pastas "
                "uploads/, outputs/ e logs/ no servidor.")
    if "timeout" in texto:
        return ("Tempo de resposta esgotado. Verifique a rede/localização do servidor "
                "ou aumente o limite de tempo das requisições.")
    if "pdfreaderror" in texto or "corrupt" in texto or "senha" in texto or "password" in texto:
        return ("O PDF enviado pode estar corrompido ou protegido por senha. Peça ao "
                "usuário um arquivo válido, sem senha e não corrompido.")
    if "memoryerror" in texto or "memory" in texto:
        return ("Memória insuficiente para processar o arquivo. Tente um arquivo menor "
                "ou libere recursos do servidor.")
    if "max content length" in texto or "413" in texto:
        return (f"A operação excede o limite de {LIMITE_UPLOAD_MB} MB (MAX_CONTENT_LENGTH). Peça um arquivo "
                "menor ou aumente o limite no app.py.")
    if "encrypt" in texto or "pikepdf" in texto or "qpdf" in texto:
        return ("Falha ao abrir o PDF (possivelmente criptografado). Verifique se o "
                "arquivo não está protegido e se o pikepdf está instalado corretamente.")
    return ("Verifique o traceback completo acima e os logs do servidor. Se o erro "
            "persistir, anote o tipo/mensagem e reporte.")


def registrar_erro(excecao, rota=None, metodo=None):
    """Grava um erro na tabela 'erros' com tipo, mensagem, traceback e
    uma sugestão de resolução. Funciona tanto dentro quanto fora de uma
    requisição HTTP."""
    if has_request_context():
        ip = obter_ip_real()
        hostname = obter_hostname(ip)
        rota = rota or request.path
        metodo = metodo or request.method
    else:
        ip = "—"
        hostname = "—"
        rota = rota or "—"
        metodo = metodo or "—"
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tipo = type(excecao).__name__
    mensagem = str(excecao)
    traceback_text = traceback.format_exc()
    resolucao = sugerir_resolucao(tipo, mensagem)
    with conectar_db() as conexao:
        conexao.execute(
            "INSERT INTO erros (data_hora, ip, hostname, rota, metodo, tipo, mensagem, traceback, resolucao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data_hora, ip, hostname, rota, metodo, tipo, mensagem, traceback_text, resolucao),
        )


@app.before_request
def registrar_acesso():
    # não loga arquivos estáticos, heartbeats ou rotas do painel administrativo
    if (request.path.startswith("/static/")
            or request.path.startswith("/api/heartbeat")
            or request.path.startswith("/admin/")):
        return
    # não loga as próprias requisições do admin (quem está logado no painel)
    if session.get("logado"):
        return

    ip = obter_ip_real()

    nomes = [
        arquivo.filename
        for campo in request.files.keys()
        for arquivo in request.files.getlist(campo)
        if arquivo and arquivo.filename
    ]
    quantidade_arquivos = len(nomes)
    nomes_arquivos = ", ".join(nomes)
    hostname = obter_hostname(ip)
    visitor_id = request.cookies.get("visitor_id", "") or ""
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conectar_db() as conexao:
        cursor = conexao.execute(
            "INSERT INTO acessos (data_hora, ip, hostname, metodo, rota, qtd_arquivos, nomes_arquivos, visitor_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data_hora, ip, hostname, request.method, request.path,
             quantidade_arquivos, nomes_arquivos, visitor_id),
        )
        g.acesso_id = cursor.lastrowid


@app.after_request
def registrar_duracao(resposta):
    """Mede o tempo de resposta da requisição e grava na linha de acesso."""
    if hasattr(g, "acesso_id"):
        duracao = (time.perf_counter() - getattr(g, "inicio", time.perf_counter())) * 1000
        with conectar_db() as conexao:
            conexao.execute(
                "UPDATE acessos SET duracao_ms = ? WHERE id = ?",
                (round(duracao, 1), g.acesso_id),
            )
    return resposta


@app.errorhandler(500)
def tratar_erro(erro):
    """Captura erros não tratados (500, etc.) e registra na tabela de erros."""
    try:
        registrar_erro(erro, request.path, request.method)
    except Exception:
        pass
    if request.path.startswith("/api/"):
        return jsonify({"erro": f"Erro interno: {type(erro).__name__}: {erro}"}), 500
    return render_template_string(TEMPLATE_ERRO, erro=str(erro), tipo=type(erro).__name__), 500


@app.errorhandler(413)
def tratar_upload_excedido(erro):
    """Retorna uma resposta legível quando vários arquivos excedem o limite."""
    mensagem = f"Os arquivos enviados ultrapassam o limite de {LIMITE_UPLOAD_MB} MB por operação."
    if request.path.startswith("/api/"):
        return jsonify({"erro": mensagem}), 413
    return mensagem, 413


# ---------------------------------------------------------------------
# PRESENÇA DE VISITANTES (heartbeat) - o front-end chama /api/heartbeat
# a cada 60s enquanto a página está aberta, e /api/heartbeat/saida
# quando a aba é fechada (via navigator.sendBeacon). Isso alimenta os
# números de "online agora", "entradas" e "saídas" do painel.
# ---------------------------------------------------------------------
@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    visitor_id = request.cookies.get("visitor_id")
    eh_novo_cookie = not visitor_id
    if not visitor_id:
        visitor_id = uuid.uuid4().hex

    ip = obter_ip_real()
    hostname = obter_hostname(ip)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conectar_db() as conexao:
        sessao_aberta = conexao.execute(
            "SELECT id FROM sessoes WHERE visitor_id = ? AND saida IS NULL ORDER BY id DESC LIMIT 1",
            (visitor_id,),
        ).fetchone()

        if sessao_aberta:
            conexao.execute(
                "UPDATE sessoes SET ultima_atividade = ?, hostname = ? WHERE id = ?",
                (agora, hostname, sessao_aberta["id"]),
            )
        else:
            # não tem sessão aberta: ou é a primeira visita, ou a sessão
            # anterior expirou por timeout -> conta como uma nova "entrada"
            conexao.execute(
                "INSERT INTO sessoes (visitor_id, ip, hostname, entrada, ultima_atividade) VALUES (?, ?, ?, ?, ?)",
                (visitor_id, ip, hostname, agora, agora),
            )

    resposta = jsonify({"ok": True})
    if eh_novo_cookie:
        resposta.set_cookie(
            "visitor_id", visitor_id, max_age=60 * 60 * 24 * 365,
            httponly=True, samesite="Lax",
        )
    return resposta


@app.route("/api/heartbeat/saida", methods=["POST"])
def heartbeat_saida():
    visitor_id = request.cookies.get("visitor_id")
    if visitor_id:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conectar_db() as conexao:
            sessao_aberta = conexao.execute(
                "SELECT id FROM sessoes WHERE visitor_id = ? AND saida IS NULL ORDER BY id DESC LIMIT 1",
                (visitor_id,),
            ).fetchone()
            if sessao_aberta:
                conexao.execute(
                    "UPDATE sessoes SET saida = ? WHERE id = ?",
                    (agora, sessao_aberta["id"]),
                )
    return ("", 204)


def novo_nome(extensao):
    """Gera um nome único de arquivo para evitar conflitos entre usuários."""
    return f"{uuid.uuid4().hex}.{extensao}"


def salvar_upload(arquivo):
    if not arquivo or not arquivo.filename:
        raise ValueError("O arquivo enviado não possui um nome válido.")
    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro:
        raise ValueError("O nome do arquivo enviado não é válido.")
    caminho = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{nome_seguro}")
    arquivo.save(caminho)
    return caminho


def validar_pdf(caminho):
    """Confirma que o arquivo é um PDF legível e não está criptografado."""
    try:
        leitor = PdfReader(caminho, strict=False)
        if leitor.is_encrypted:
            raise ValueError("O PDF está protegido por senha e não pode ser processado.")
        if len(leitor.pages) == 0:
            raise ValueError("O PDF não contém páginas.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("O arquivo não é um PDF válido ou está corrompido.") from exc


# ---------------------------------------------------------------------
# ROTA PRINCIPAL - serve o site (HTML)
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    """Endpoint simples para verificar se o processo está respondendo."""
    try:
        with conectar_db() as conexao:
            conexao.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"})
    except sqlite3.Error:
        return jsonify({"status": "erro"}), 503


# ---------------------------------------------------------------------
# PAINEL DE LOGS (protegido por login de usuário e senha, via sessão)
# Ex: http://seusite.com/admin/logs
# Filtros opcionais: ?ip=1.2.3.4  |  ?rota=/api/comprimir
# ---------------------------------------------------------------------
USUARIO_ADM = os.environ.get("USUARIO_ADM", "ADM")
SENHA_ADM = os.environ.get("SENHA_ADM", "2008")


def login_obrigatorio(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if not session.get("logado"):
            return redirect(url_for("login", proximo=request.path))
        return funcao(*args, **kwargs)
    return decorada


TEMPLATE_LOGIN = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Login - Painel</title>
<style>
    body { font-family: Arial, Helvetica, sans-serif; background: #0f1117; color: #e6e6e6;
           margin: 0; height: 100vh; display: flex; align-items: center; justify-content: center; }
    form { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 10px; padding: 28px;
           width: 260px; display: flex; flex-direction: column; gap: 12px; }
    h1 { font-size: 18px; margin: 0 0 8px; text-align: center; }
    input { background: #0f1117; border: 1px solid #2a2d3a; color: #e6e6e6; padding: 8px 10px; border-radius: 6px; }
    button { background: #3b6df0; border: none; color: white; padding: 10px; border-radius: 6px; cursor: pointer; font-weight: bold; }
    .erro { color: #e05252; font-size: 13px; text-align: center; margin: 0; }
</style>
</head>
<body>
    <form method="post">
        <h1>Painel de logs</h1>
        {% if erro %}<p class="erro">{{ erro }}</p>{% endif %}
        <input type="text" name="usuario" placeholder="Usuário" autocomplete="username" required>
        <input type="password" name="senha" placeholder="Senha" autocomplete="current-password" required>
        <button type="submit">Entrar</button>
    </form>
</body>
</html>"""


TEMPLATE_ERRO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Erro interno</title>
<style>
    body { font-family: Arial, Helvetica, sans-serif; background: #0f1117; color: #e6e6e6; margin: 0; padding: 32px; }
    h1 { font-size: 20px; color: #e05252; }
    .box { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 16px; margin-top: 16px; }
    code { color: #7be3a0; }
    p { font-size: 14px; }
</style>
</head>
<body>
    <h1>Ocorreu um erro no servidor</h1>
    <p>O erro foi registrado no painel de logs (tabela de erros), com sugestão de resolução.</p>
    <div class="box"><code>{{ tipo }}:</code> {{ erro }}</div>
    <p><a href="/admin/logs" style="color:#9aa0ab;">Ver painel de logs</a></p>
</body>
</html>"""


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    # se já está logado, não mostra o formulário de novo: vai direto pro painel
    if session.get("logado"):
        return redirect(url_for("ver_logs"))

    erro = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")

        if USUARIO_ADM and SENHA_ADM and usuario == USUARIO_ADM and senha == SENHA_ADM:
            session["logado"] = True
            proximo = request.args.get("proximo") or url_for("ver_logs")
            return redirect(proximo)

        erro = "Usuário ou senha incorretos."

    return render_template_string(TEMPLATE_LOGIN, erro=erro)


@app.route("/admin/logout")
def logout():
    session.pop("logado", None)
    return redirect(url_for("login"))


@app.route("/admin/limpar", methods=["POST"])
@login_obrigatorio
def limpar_logs():
    """Apaga todos os registros (acessos, visitantes e erros)."""
    with conectar_db() as conexao:
        conexao.execute("DELETE FROM acessos")
        conexao.execute("DELETE FROM sessoes")
        conexao.execute("DELETE FROM erros")
    return redirect(url_for("ver_logs"))


@app.route("/admin/limpar-acessos", methods=["POST"])
@login_obrigatorio
def limpar_acessos():
    """Apaga apenas as requisições (mantém visitantes e erros)."""
    with conectar_db() as conexao:
        conexao.execute("DELETE FROM acessos")
    return redirect(url_for("ver_logs"))


def _csv_bytes(tabela):
    """Gera o conteúdo CSV de uma tabela (com cabeçalho), em UTF-8 pra
    abrir certo no Excel em português."""
    with conectar_db() as conexao:
        colunas = [linha["name"] for linha in conexao.execute(f"PRAGMA table_info({tabela})")]
        filtro = " WHERE rota NOT LIKE '/admin/%'" if tabela == "acessos" else ""
        linhas = conexao.execute(f"SELECT * FROM {tabela}{filtro}").fetchall()
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(colunas)
    for linha in linhas:
        escritor.writerow([linha[coluna] for coluna in colunas])
    return buffer.getvalue().encode("utf-8-sig")


def _resumo_csv_bytes():
    """Gera um CSV de resumo: uma linha GERAL com os totais e uma linha
    por dia (entradas, saídas, requisições, arquivos, erros, tempo médio)."""
    with conectar_db() as conexao:
        filtro_acessos = " WHERE rota NOT LIKE '/admin/%'"
        total_acessos = conexao.execute(f"SELECT COUNT(*) FROM acessos{filtro_acessos}").fetchone()[0]
        ips_unicos = conexao.execute(f"SELECT COUNT(DISTINCT ip) FROM acessos{filtro_acessos}").fetchone()[0]
        total_arquivos = conexao.execute(
            f"SELECT COALESCE(SUM(qtd_arquivos),0) FROM acessos{filtro_acessos}"
        ).fetchone()[0]
        media_duracao = conexao.execute(
            f"SELECT COALESCE(ROUND(AVG(duracao_ms),1),0) FROM acessos{filtro_acessos}"
        ).fetchone()[0]
        entradas = conexao.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0]
        saidas = conexao.execute("SELECT COUNT(*) FROM sessoes WHERE saida IS NOT NULL").fetchone()[0]
        total_erros = conexao.execute("SELECT COUNT(*) FROM erros").fetchone()[0]

        dias = {}
        def padrao():
            return {"requisicoes": 0, "arquivos": 0, "media_ms": 0, "entradas": 0, "saidas": 0, "erros": 0}
        for r in conexao.execute(
            "SELECT substr(data_hora,1,10) as dia, COUNT(*) as req, "
            "COALESCE(SUM(qtd_arquivos),0) as arq, COALESCE(ROUND(AVG(duracao_ms),1),0) as mm "
            "FROM acessos WHERE rota NOT LIKE '/admin/%' GROUP BY dia"
        ).fetchall():
            d = padrao(); d["requisicoes"] = r["req"]; d["arquivos"] = r["arq"]; d["media_ms"] = r["mm"]
            dias[r["dia"]] = d
        for dia, c in conexao.execute("SELECT substr(entrada,1,10), COUNT(*) FROM sessoes GROUP BY 1").fetchall():
            dias.setdefault(dia, padrao())["entradas"] = c
        for dia, c in conexao.execute("SELECT substr(saida,1,10), COUNT(*) FROM sessoes WHERE saida IS NOT NULL GROUP BY 1").fetchall():
            dias.setdefault(dia, padrao())["saidas"] = c
        for dia, c in conexao.execute("SELECT substr(data_hora,1,10), COUNT(*) FROM erros GROUP BY 1").fetchall():
            dias.setdefault(dia, padrao())["erros"] = c
        dias_ord = sorted(dias.items())

    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["periodo", "entradas", "saidas", "requisicoes", "arquivos", "erros", "tempo_medio_ms", "ips_unicos", "total_arquivos"])
    escritor.writerow(["GERAL", entradas, saidas, total_acessos, total_arquivos, total_erros, media_duracao, ips_unicos, total_arquivos])
    for dia, d in dias_ord:
        escritor.writerow([dia, d["entradas"], d["saidas"], d["requisicoes"], d["arquivos"], d["erros"], d["media_ms"], "", ""])
    return buffer.getvalue().encode("utf-8-sig")


@app.route("/admin/exportar")
@login_obrigatorio
def exportar_logs():
    """Exporta tudo (acessos, visitantes e erros) em um ZIP com CSVs."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zip_:
        for tabela in ("acessos", "sessoes", "erros"):
            zip_.writestr(f"{tabela}.csv", _csv_bytes(tabela))
        zip_.writestr("resumo.csv", _resumo_csv_bytes())
    memoria.seek(0)
    return send_file(
        memoria,
        as_attachment=True,
        download_name="logs_backup.zip",
        mimetype="application/zip",
    )


TEMPLATE_LOGS = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Log de acessos</title>
<style>
    body { font-family: Arial, Helvetica, sans-serif; background: #0f1117; color: #e6e6e6; margin: 0; padding: 24px; }
    h1 { font-size: 20px; margin-bottom: 4px; display: inline-block; }
    .topo { display: flex; align-items: baseline; justify-content: space-between; }
    .sair { color: #9aa0ab; font-size: 13px; text-decoration: none; }
    .sair:hover { color: #e6e6e6; }
    .resumo { display: flex; gap: 16px; margin: 16px 0 24px; flex-wrap: wrap; }
    .card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 12px 18px; min-width: 140px; }
    .card span { display: block; font-size: 12px; color: #9aa0ab; }
    .card b { font-size: 22px; }
    form { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
    input { background: #1a1d27; border: 1px solid #2a2d3a; color: #e6e6e6; padding: 6px 10px; border-radius: 6px; }
    button { background: #3b6df0; border: none; color: white; padding: 6px 14px; border-radius: 6px; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #23262f; }
    th { color: #9aa0ab; font-weight: normal; position: sticky; top: 0; background: #0f1117; }
    tr:hover { background: #171a22; }
    .badge { background: #22262f; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
    .info-recarga { font-size: 12px; color: #9aa0ab; margin: -8px 0 16px; }
</style>
</head>
<body>
    <div class="topo">
        <h1>Log de acessos do site</h1>
        <a class="sair" href="{{ url_for('logout') }}">Sair</a>
    </div>
    <p class="info-recarga">Atualiza sozinho a cada {{ intervalo_segundos }} segundos.</p>

    <div class="resumo">
        <div class="card"><span>Total de requisições</span><b>{{ total }}</b></div>
        <div class="card"><span>IPs únicos</span><b>{{ ips_unicos }}</b></div>
        <div class="card"><span>Arquivos recebidos (total)</span><b>{{ total_arquivos }}</b></div>
        <div class="card"><span>Pessoas online agora</span><b>{{ online_agora }}</b></div>
        <div class="card"><span>Entradas hoje</span><b>{{ entradas_hoje }}</b></div>
        <div class="card"><span>Saídas hoje</span><b>{{ saidas_hoje }}</b></div>
        <div class="card"><span>Tempo médio de resposta</span><b>{{ media_duracao }} ms</b></div>
        <div class="card" style="border-color:#5a2d2d;"><span>Erros registrados</span><b style="color:#e05252;">{{ erros_total }}</b></div>
    </div>

    <form method="get">
        <input type="text" name="ip" placeholder="Filtrar por IP" value="{{ filtro_ip or '' }}">
        <input type="text" name="rota" placeholder="Filtrar por rota (ex: /api/comprimir)" value="{{ filtro_rota or '' }}">
        <input type="number" name="intervalo" placeholder="Recarregar a cada (segundos)" value="{{ intervalo_segundos }}" min="10" style="width: 220px;">
        <button type="submit">Filtrar</button>
    </form>

    <form method="post" action="/admin/limpar"
          onsubmit="return confirm('Apagar TODOS os logs (acessos, visitantes e erros)?');"
          style="margin-bottom: 20px;">
        <button type="submit"
                style="background:#5a2d2d; border:none; color:white; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:bold;">
            Limpar todos os logs
        </button>
    </form>

    <form method="post" action="/admin/limpar-acessos"
          onsubmit="return confirm('Apagar apenas as requisições (manter visitantes e erros)?');"
          style="margin-bottom: 20px;">
        <button type="submit"
                style="background:#3a3d4a; border:none; color:white; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:bold;">
            Limpar requisições
        </button>
    </form>

    <a href="/admin/exportar" download
       style="display:inline-block; background:#1f4d2e; color:#7be3a0; padding:8px 16px; border-radius:6px; text-decoration:none; font-weight:bold; margin-bottom:20px;">
        Exportar tudo (ZIP / CSV)
    </a>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Requisições</h2>
    <table>
        <tr>
            <th>Data/Hora</th>
            <th>IP</th>
            <th>Máquina (host)</th>
            <th>Método</th>
            <th>Rota</th>
            <th>Qtd.</th>
            <th>Arquivos enviados</th>
            <th>Tempo (ms)</th>
        </tr>
        {% for linha in registros %}
        <tr>
            <td>{{ linha["data_hora"] }}</td>
            <td>{{ linha["ip"] }}</td>
            <td title="{{ linha['hostname'] }}">{{ linha["hostname"] or "—" }}</td>
            <td>{{ linha["metodo"] }}</td>
            <td>{{ linha["rota"] }}</td>
            <td>{% if linha["qtd_arquivos"] %}<span class="badge">{{ linha["qtd_arquivos"] }}</span>{% endif %}</td>
            <td title="{{ linha['nomes_arquivos'] }}">{{ linha["nomes_arquivos"] or "" }}</td>
            <td>{% if linha["duracao_ms"] %}{{ linha["duracao_ms"] }}{% else %}—{% endif %}</td>
        </tr>
        {% endfor %}
    </table>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Visitantes (entradas / saídas)</h2>
    <table>
        <tr>
            <th>Visitante</th>
            <th>IP</th>
            <th>Máquina (host)</th>
            <th>Entrada</th>
            <th>Última atividade</th>
            <th>Saída</th>
            <th>Status</th>
            <th>O que fez</th>
        </tr>
        {% for sessao in sessoes %}
        <tr>
            <td>{{ sessao["visitor_id"][:8] }}</td>
            <td>{{ sessao["ip"] }}</td>
            <td title="{{ sessao['hostname'] }}">{{ sessao["hostname"] or "—" }}</td>
            <td>{{ sessao["entrada"] }}</td>
            <td>{{ sessao["ultima_atividade"] }}</td>
            <td>{{ sessao["saida"] or "—" }}</td>
            <td>
                {% if sessao["online"] %}<span class="badge" style="background:#1f4d2e;color:#7be3a0;">online</span>
                {% elif sessao["saida"] %}<span class="badge">saiu</span>
                {% else %}<span class="badge">inativo</span>{% endif %}
            </td>
            <td>
                {% set acoes = acoes_por_visitor.get(sessao["visitor_id"]) %}
                {% if acoes and acoes[0] > 0 %}
                    <span class="badge">{{ acoes[0] }}</span> ação(ões): {{ acoes[1] }}
                {% else %}
                    <span class="badge" style="background:#3a2d22;color:#e0a052;">abriu e saiu sem ações</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Resumo por dia</h2>
    <table>
        <tr>
            <th>Data</th>
            <th>Entradas</th>
            <th>Saídas</th>
            <th>Requisições</th>
            <th>Arquivos</th>
            <th>Erros</th>
            <th>Tempo médio (ms)</th>
        </tr>
        {% for dia in resumo_dias %}
        <tr>
            <td>{{ dia["dia"] }}</td>
            <td>{{ dia["entradas"] }}</td>
            <td>{{ dia["saidas"] }}</td>
            <td>{{ dia["requisicoes"] }}</td>
            <td>{{ dia["arquivos"] }}</td>
            <td>{% if dia["erros"] %}<span class="badge" style="background:#5a2d2d;color:#e05252;">{{ dia["erros"] }}</span>{% else %}0{% endif %}</td>
            <td>{% if dia["media_ms"] %}{{ dia["media_ms"] }}{% else %}—{% endif %}</td>
        </tr>
        {% endfor %}
    </table>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Desempenho por rota (tempo de resposta)</h2>
    <p class="info-recarga">Barras = tempo <b>médio</b> por rota.
       <span style="color:#3b6df0;">azul</span> &lt; 200ms ·
       <span style="color:#e0a052;">amarelo</span> 200–500ms ·
       <span style="color:#e05252;">vermelho</span> &gt; 500ms (lento).
       Pico (máx) mostra o pior caso.</p>
    <table>
        <tr>
            <th>Rota</th>
            <th>Reqs</th>
            <th>Médio (ms)</th>
            <th>Máx (ms)</th>
            <th style="width:40%;">Gráfico</th>
        </tr>
        {% for d in desempenho_rotas %}
        <tr>
            <td>{{ d["rota"] }}</td>
            <td>{{ d["total"] }}</td>
            <td>{% if d["media"] %}{{ d["media"] }}{% else %}—{% endif %}</td>
            <td>{% if d["maximo"] %}{{ d["maximo"] }}{% else %}—{% endif %}</td>
            <td>
                <div style="background:#22262f;border-radius:4px;height:14px;width:100%;">
                    <div style="height:14px;border-radius:4px;width:{{ (d['media'] / max_media * 100) if max_media else 0 }}%;background:{% if d['media'] >= 500 %}#e05252{% elif d['media'] >= 200 %}#e0a052{% else %}#3b6df0{% endif %};"></div>
                </div>
            </td>
        </tr>
        {% endfor %}
    </table>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Arquivos enviados (por data/hora)</h2>
    <table>
        <tr>
            <th>Data/Hora</th>
            <th>IP</th>
            <th>Máquina (host)</th>
            <th>Rota</th>
            <th>Arquivos</th>
        </tr>
        {% for arq in arquivos_log %}
        <tr>
            <td>{{ arq["data_hora"] }}</td>
            <td>{{ arq["ip"] }}</td>
            <td title="{{ arq['hostname'] }}">{{ arq["hostname"] or "—" }}</td>
            <td>{{ arq["rota"] }}</td>
            <td title="{{ arq['nomes_arquivos'] }}">{{ arq["nomes_arquivos"] or "" }}</td>
        </tr>
        {% endfor %}
    </table>

    <h2 style="font-size:16px; margin: 24px 0 10px;">Erros (com sugestão de resolução)</h2>
    <table>
        <tr>
            <th>Data/Hora</th>
            <th>IP</th>
            <th>Máquina</th>
            <th>Rota</th>
            <th>Tipo</th>
            <th>Mensagem</th>
            <th>Como resolver</th>
        </tr>
        {% for erro in erros_log %}
        <tr>
            <td>{{ erro["data_hora"] }}</td>
            <td>{{ erro["ip"] }}</td>
            <td title="{{ erro['hostname'] }}">{{ erro["hostname"] or "—" }}</td>
            <td>{{ erro["rota"] }}</td>
            <td><span class="badge" style="background:#5a2d2d;color:#e05252;">{{ erro["tipo"] }}</span></td>
            <td title="{{ erro['mensagem'] }}">{{ erro["mensagem"][:120] }}</td>
            <td>
                {{ erro["resolucao"] }}
                <details>
                    <summary style="cursor:pointer;color:#9aa0ab;">Ver traceback</summary>
                    <pre style="white-space:pre-wrap;font-size:11px;color:#9aa0ab;">{{ erro["traceback"] }}</pre>
                </details>
            </td>
        </tr>
        {% endfor %}
    </table>

    <script>
        // recarrega a página sozinha, mantendo os filtros que já estão na URL
        setTimeout(() => window.location.reload(), {{ intervalo_segundos }} * 1000);
    </script>
</body>
</html>"""



@app.route("/admin/logs")
@login_obrigatorio
def ver_logs():
    filtro_ip = request.args.get("ip", "").strip()
    filtro_rota = request.args.get("rota", "").strip()

    try:
        intervalo_segundos = int(request.args.get("intervalo", 120))
    except ValueError:
        intervalo_segundos = 120
    intervalo_segundos = max(intervalo_segundos, 10)  # nunca menor que 10s, pra não martelar o servidor

    condicoes = []
    parametros = []
    condicoes.append("rota NOT LIKE '/admin/%'")
    if filtro_ip:
        condicoes.append("ip LIKE ?")
        parametros.append(f"%{filtro_ip}%")
    if filtro_rota:
        condicoes.append("rota LIKE ?")
        parametros.append(f"%{filtro_rota}%")

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    agora = datetime.now()
    limite_online = (agora - timedelta(seconds=TIMEOUT_ONLINE_SEGUNDOS)).strftime("%Y-%m-%d %H:%M:%S")
    hoje = agora.strftime("%Y-%m-%d")

    with conectar_db() as conexao:
        registros = conexao.execute(
            f"SELECT * FROM acessos {where} ORDER BY id DESC LIMIT 500", parametros
        ).fetchall()

        total = conexao.execute(f"SELECT COUNT(*) FROM acessos {where}", parametros).fetchone()[0]
        ips_unicos = conexao.execute(f"SELECT COUNT(DISTINCT ip) FROM acessos {where}", parametros).fetchone()[0]
        total_arquivos = conexao.execute(
            f"SELECT COALESCE(SUM(qtd_arquivos), 0) FROM acessos {where}", parametros
        ).fetchone()[0]
        media_duracao = conexao.execute(
            f"SELECT COALESCE(ROUND(AVG(duracao_ms), 1), 0) FROM acessos {where}", parametros
        ).fetchone()[0]

        # desempenho por rota: média e pico de tempo de resposta (grafico de barras)
        desempenho_rotas = [
            dict(r)
            for r in conexao.execute(
                f"SELECT rota, COUNT(*) as total, "
                f"COALESCE(ROUND(AVG(duracao_ms), 1), 0) as media, "
                f"COALESCE(ROUND(MAX(duracao_ms), 1), 0) as maximo "
                f"FROM acessos {where} GROUP BY rota ORDER BY media DESC"
            ).fetchall()
        ]
        max_media = max((d["media"] for d in desempenho_rotas), default=0) or 1

        online_agora = conexao.execute(
            "SELECT COUNT(*) FROM sessoes WHERE saida IS NULL AND ultima_atividade >= ?",
            (limite_online,),
        ).fetchone()[0]
        entradas_hoje = conexao.execute(
            "SELECT COUNT(*) FROM sessoes WHERE substr(entrada, 1, 10) = ?", (hoje,)
        ).fetchone()[0]
        saidas_hoje = conexao.execute(
            "SELECT COUNT(*) FROM sessoes WHERE substr(saida, 1, 10) = ?", (hoje,)
        ).fetchone()[0]

        sessoes_brutas = conexao.execute(
            "SELECT * FROM sessoes ORDER BY id DESC LIMIT 200"
        ).fetchall()

        # arquivos enviados (respeita o filtro de IP/rota, se houver)
        arquivos_where = "WHERE qtd_arquivos > 0"
        arquivos_parametros = []
        if condicoes:
            arquivos_where += " AND " + " AND ".join(condicoes)
            arquivos_parametros = parametros
        arquivos_log = conexao.execute(
            f"SELECT data_hora, ip, hostname, rota, nomes_arquivos FROM acessos "
            f"{arquivos_where} ORDER BY id DESC LIMIT 300",
            arquivos_parametros,
        ).fetchall()

        # erros (mesmo filtro de IP/rota, pois a tabela também tem essas colunas)
        erros_total = conexao.execute(
            f"SELECT COUNT(*) FROM erros {where}", parametros
        ).fetchone()[0]
        erros_log = conexao.execute(
            f"SELECT * FROM erros {where} ORDER BY id DESC LIMIT 200", parametros
        ).fetchall()

        # resumo agrupado por dia (entradas/saídas/requisições/arquivos/erros/tempo)
        def dia_padrao():
            return {"requisicoes": 0, "arquivos": 0, "media_ms": 0,
                    "entradas": 0, "saidas": 0, "erros": 0}

        dias = {}
        for r in conexao.execute(
            "SELECT substr(data_hora,1,10) as dia, COUNT(*) as req, "
            "COALESCE(SUM(qtd_arquivos),0) as arq, COALESCE(ROUND(AVG(duracao_ms),1),0) as mm "
            "FROM acessos WHERE rota NOT LIKE '/admin/%' GROUP BY dia"
        ).fetchall():
            d = dia_padrao()
            d["requisicoes"] = r["req"]
            d["arquivos"] = r["arq"]
            d["media_ms"] = r["mm"]
            dias[r["dia"]] = d
        for dia, c in conexao.execute(
            "SELECT substr(entrada,1,10), COUNT(*) FROM sessoes GROUP BY 1"
        ).fetchall():
            dias.setdefault(dia, dia_padrao())["entradas"] = c
        for dia, c in conexao.execute(
            "SELECT substr(saida,1,10), COUNT(*) FROM sessoes WHERE saida IS NOT NULL GROUP BY 1"
        ).fetchall():
            dias.setdefault(dia, dia_padrao())["saidas"] = c
        for dia, c in conexao.execute(
            "SELECT substr(data_hora,1,10), COUNT(*) FROM erros GROUP BY 1"
        ).fetchall():
            dias.setdefault(dia, dia_padrao())["erros"] = c
        resumo_dias = [dict(d, dia=dia) for dia, d in sorted(dias.items(), reverse=True)[:30]]

        # o que cada visitante fez (ações = requisições registradas com o visitor_id)
        acoes_por_visitor = {}
        for r in conexao.execute(
            "SELECT visitor_id, COUNT(*) as n, GROUP_CONCAT(rota) as rotas FROM acessos "
            "WHERE visitor_id != '' AND rota NOT LIKE '/admin/%' GROUP BY visitor_id"
        ).fetchall():
            acoes_por_visitor[r["visitor_id"]] = (r["n"], r["rotas"])

    sessoes = [
        {**dict(s), "online": s["saida"] is None and s["ultima_atividade"] >= limite_online}
        for s in sessoes_brutas
    ]

    return render_template_string(
        TEMPLATE_LOGS,
        registros=registros,
        total=total,
        ips_unicos=ips_unicos,
        total_arquivos=total_arquivos,
        media_duracao=media_duracao,
        desempenho_rotas=desempenho_rotas,
        max_media=max_media,
        online_agora=online_agora,
        entradas_hoje=entradas_hoje,
        saidas_hoje=saidas_hoje,
        erros_total=erros_total,
        sessoes=sessoes,
        resumo_dias=resumo_dias,
        arquivos_log=arquivos_log,
        erros_log=erros_log,
        acoes_por_visitor=acoes_por_visitor,
        filtro_ip=filtro_ip,
        filtro_rota=filtro_rota,
        intervalo_segundos=intervalo_segundos,
    )


# ---------------------------------------------------------------------
# JUNTAR PDFs
# ---------------------------------------------------------------------
@app.route("/api/juntar", methods=["POST"])
def juntar_pdfs():
    arquivos = request.files.getlist("arquivos")

    if len(arquivos) < 2:
        return jsonify({"erro": "Envie pelo menos 2 arquivos PDF."}), 400

    if not all(extensao_valida(a.filename, EXTENSOES_PDF) for a in arquivos):
        return jsonify({"erro": "Só são aceitos arquivos .pdf."}), 400

    writer = PdfWriter()
    caminhos_temporarios = []

    try:
        for arquivo in arquivos:
            caminho = salvar_upload(arquivo)
            caminhos_temporarios.append(caminho)
            validar_pdf(caminho)
            reader = PdfReader(caminho)
            for pagina in reader.pages:
                writer.add_page(pagina)

        nome_saida = novo_nome("pdf")
        caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

        with open(caminho_saida, "wb") as f:
            writer.write(f)

        return send_file(caminho_saida, as_attachment=True, download_name="juntado.pdf")

    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        registrar_erro(e, request.path, request.method)
        return jsonify({"erro": str(e)}), 500

    finally:
        for caminho in caminhos_temporarios:
            if os.path.exists(caminho):
                os.remove(caminho)


# ---------------------------------------------------------------------
# DIVIDIR PDF (retorna um .zip com uma página por arquivo)
# ---------------------------------------------------------------------
@app.route("/api/dividir", methods=["POST"])
def dividir_pdf():
    arquivo = request.files.get("arquivo")
    paginas_texto = request.form.get("paginas", "")

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo PDF."}), 400

    if not extensao_valida(arquivo.filename, EXTENSOES_PDF):
        return jsonify({"erro": "Só são aceitos arquivos .pdf."}), 400

    caminho_entrada = salvar_upload(arquivo)
    pasta_temp = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
    os.makedirs(pasta_temp, exist_ok=True)

    try:
        validar_pdf(caminho_entrada)
        reader = PdfReader(caminho_entrada)
        paginas_selecionadas = parse_paginas_selecionadas(paginas_texto, len(reader.pages))

        for numero_pagina in paginas_selecionadas:
            writer = PdfWriter()
            writer.add_page(reader.pages[numero_pagina - 1])
            caminho_pagina = os.path.join(pasta_temp, f"pagina_{numero_pagina}.pdf")
            with open(caminho_pagina, "wb") as f:
                writer.write(f)

        caminho_zip_base = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
        caminho_zip = shutil.make_archive(caminho_zip_base, "zip", pasta_temp)

        return send_file(caminho_zip, as_attachment=True, download_name="Divisão.zip")
    
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        registrar_erro(e, request.path, request.method)
        return jsonify({"erro": str(e)}), 500
    
    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)
        shutil.rmtree(pasta_temp, ignore_errors=True)


# ---------------------------------------------------------------------
# COMPRIMIR PDF (to usando o pymudP)
# ---------------------------------------------------------------------
@app.route("/api/comprimir", methods=["POST"])
def comprimir_pdf():
    arquivo = request.files.get("arquivo")
    nivel_compressao = request.form.get("nivel_compressao", "padrao")

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo PDF."}), 400

    if not extensao_valida(arquivo.filename, EXTENSOES_PDF):
        return jsonify({"erro": "Só são aceitos arquivos .pdf."}), 400

    caminho_entrada = salvar_upload(arquivo)
    nome_saida = novo_nome("pdf")
    caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

    try:
        tamanho_antes = os.path.getsize(caminho_entrada)

        if tamanho_antes == 0:
            return jsonify({"erro": "O arquivo enviado está vazio."}), 400
        validar_pdf(caminho_entrada)

        if nivel_compressao in {"25", "50"}:
            fator_qualidade = int(nivel_compressao)
            escala = 0.55 if fator_qualidade == 50 else 0.75
            qualidade_jpeg = 45 if fator_qualidade == 50 else 65
            documento = pymupdf.open(caminho_entrada)
            documento_saida = pymupdf.open()
            try:
                for pagina in documento:
                    matriz = pymupdf.Matrix(1.5 * escala, 1.5 * escala)
                    pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
                    imagem = pixmap.tobytes("jpeg", jpg_quality=qualidade_jpeg)
                    nova_pagina = documento_saida.new_page(
                        width=pagina.rect.width,
                        height=pagina.rect.height,
                    )
                    nova_pagina.insert_image(nova_pagina.rect, stream=imagem)
                documento_saida.save(caminho_saida, garbage=4, deflate=True)
            finally:
                documento_saida.close()
                documento.close()
        else:
            with pikepdf.open(caminho_entrada) as pdf:
                pdf.save(
                    caminho_saida,
                    compress_streams=True,
                    recompress_flate=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )

        tamanho_depois = os.path.getsize(caminho_saida)
        reducao = round((1 - tamanho_depois / tamanho_antes) * 100, 1)

        resposta = send_file(caminho_saida, as_attachment=True, download_name="comprimido.pdf")
        resposta.headers["X-Reducao-Percentual"] = str(reducao)
        return resposta

    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        registrar_erro(e, request.path, request.method)
        return jsonify({"erro": f"Falha ao comprimir: {e}"}), 500

    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)


# ---------------------------------------------------------------------
# CONVERTER PDF -> WORD
# ---------------------------------------------------------------------
@app.route("/api/pdf-para-word", methods=["POST"])
def pdf_para_word():
    arquivo = request.files.get("arquivo")

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo PDF."}), 400

    if not extensao_valida(arquivo.filename, EXTENSOES_PDF):
        return jsonify({"erro": "Só são aceitos arquivos .pdf."}), 400

    caminho_entrada = salvar_upload(arquivo)
    nome_saida = novo_nome("docx")
    caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

    try:
        validar_pdf(caminho_entrada)
        conversor = Converter(caminho_entrada)
        conversor.convert(caminho_saida)
        conversor.close()

        return send_file(caminho_saida, as_attachment=True, download_name="convertido.docx")

    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        registrar_erro(e, request.path, request.method)
        return jsonify({"erro": str(e)}), 500

    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
#JPG para PDF
# ---------------------------------------------------------------------
# antes da rota, se ainda não existir
EXTENSOES_JPG = {"jpg", "jpeg","png"}

@app.route("/api/jpg-para-pdf", methods=["POST"])
def jpg_para_pdf():
    arquivos = request.files.getlist("arquivos")

    if not arquivos:
        return jsonify({"erro": "Envie pelo menos um arquivo JPG."}), 400

    if not all(extensao_valida(a.filename, EXTENSOES_JPG) for a in arquivos):
        return jsonify({"erro": "Só são aceitos arquivos .jpeg, .jpg ou .png."}), 400

    caminhos = []
    try:
        for arquivo in arquivos:
            caminho_entrada = salvar_upload(arquivo)
            caminhos.append(caminho_entrada)

        nome_saida = novo_nome("pdf")
        caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

        documento = pymupdf.open()

        for caminho in caminhos:
            imagem = pymupdf.open(caminho)
            if imagem.page_count == 0:
                imagem.close()
                continue

            pagina = documento.new_page(
                width=imagem[0].rect.width,
                height=imagem[0].rect.height
            )
            pagina.insert_image(pagina.rect, filename=caminho)
            imagem.close()

        documento.save(caminho_saida)
        documento.close()

        return send_file(caminho_saida, as_attachment=True, download_name="convertido.pdf")

    except Exception as e:
        registrar_erro(e, request.path, request.method)
        return jsonify({"erro": str(e)}), 500

    finally:
        for caminho in caminhos:
            if os.path.exists(caminho):
                os.remove(caminho)
    


if __name__ == "__main__":
    modo_debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=modo_debug)
    
