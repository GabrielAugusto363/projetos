import os
import uuid
import subprocess
import shutil

from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename

from pypdf import PdfReader, PdfWriter
from pdf2docx import Converter
import pikepdf

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB por requisição


def novo_nome(extensao):
    """Gera um nome único de arquivo para evitar conflitos entre usuários."""
    return f"{uuid.uuid4().hex}.{extensao}"


def salvar_upload(arquivo):
    nome_seguro = secure_filename(arquivo.filename)
    caminho = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{nome_seguro}")
    arquivo.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# ROTA PRINCIPAL - serve o site (HTML)
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------
# JUNTAR PDFs
# ---------------------------------------------------------------------
@app.route("/api/juntar", methods=["POST"])
def juntar_pdfs():
    arquivos = request.files.getlist("arquivos")

    if len(arquivos) < 2:
        return jsonify({"erro": "Envie pelo menos 2 arquivos PDF."}), 400

    writer = PdfWriter()
    caminhos_temporarios = []

    try:
        for arquivo in arquivos:
            caminho = salvar_upload(arquivo)
            caminhos_temporarios.append(caminho)
            reader = PdfReader(caminho)
            for pagina in reader.pages:
                writer.add_page(pagina)

        nome_saida = novo_nome("pdf")
        caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

        with open(caminho_saida, "wb") as f:
            writer.write(f)

        return send_file(caminho_saida, as_attachment=True, download_name="juntado.pdf")

    except Exception as e:
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

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo PDF."}), 400

    caminho_entrada = salvar_upload(arquivo)
    pasta_temp = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
    os.makedirs(pasta_temp, exist_ok=True)

    try:
        reader = PdfReader(caminho_entrada)

        for i, pagina in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(pagina)
            caminho_pagina = os.path.join(pasta_temp, f"pagina_{i + 1}.pdf")
            with open(caminho_pagina, "wb") as f:
                writer.write(f)

        caminho_zip_base = os.path.join(OUTPUT_DIR, uuid.uuid4().hex)
        caminho_zip = shutil.make_archive(caminho_zip_base, "zip", pasta_temp)

        return send_file(caminho_zip, as_attachment=True, download_name="paginas_divididas.zip")

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)
        shutil.rmtree(pasta_temp, ignore_errors=True)


# ---------------------------------------------------------------------
# COMPRIMIR PDF (usa pikepdf, que por baixo usa a biblioteca QPDF)
# ---------------------------------------------------------------------
@app.route("/api/comprimir", methods=["POST"])
def comprimir_pdf():
    arquivo = request.files.get("arquivo")

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo PDF."}), 400

    caminho_entrada = salvar_upload(arquivo)
    nome_saida = novo_nome("pdf")
    caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

    try:
        tamanho_antes = os.path.getsize(caminho_entrada)

        with pikepdf.open(caminho_entrada) as pdf:
            pdf.save(
                caminho_saida,
                compress_streams=True,          # compacta os streams de conteúdo
                object_stream_mode=pikepdf.ObjectStreamMode.generate,  # agrupa objetos
                linearize=True,                 # otimiza para leitura/abertura rápida
            )

        tamanho_depois = os.path.getsize(caminho_saida)
        reducao = round((1 - tamanho_depois / tamanho_antes) * 100, 1)

        resposta = send_file(caminho_saida, as_attachment=True, download_name="comprimido.pdf")
        resposta.headers["X-Reducao-Percentual"] = str(reducao)
        return resposta

    except Exception as e:
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

    caminho_entrada = salvar_upload(arquivo)
    nome_saida = novo_nome("docx")
    caminho_saida = os.path.join(OUTPUT_DIR, nome_saida)

    try:
        conversor = Converter(caminho_entrada)
        conversor.convert(caminho_saida)
        conversor.close()

        return send_file(caminho_saida, as_attachment=True, download_name="convertido.docx")

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)


# ---------------------------------------------------------------------
# CONVERTER WORD -> PDF (usa LibreOffice em modo headless)
# ---------------------------------------------------------------------
@app.route("/api/word-para-pdf", methods=["POST"])
def word_para_pdf():
    arquivo = request.files.get("arquivo")

    if not arquivo:
        return jsonify({"erro": "Envie um arquivo Word (.docx)."}), 400

    caminho_entrada = salvar_upload(arquivo)

    comando = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", OUTPUT_DIR,
        caminho_entrada,
    ]

    try:
        subprocess.run(comando, check=True, timeout=60)

        nome_base = os.path.splitext(os.path.basename(caminho_entrada))[0]
        caminho_saida = os.path.join(OUTPUT_DIR, f"{nome_base}.pdf")

        return send_file(caminho_saida, as_attachment=True, download_name="convertido.pdf")

    except FileNotFoundError:
        return jsonify({
            "erro": "LibreOffice não está instalado no servidor. "
                    "Instale-o para usar essa conversão (veja o README)."
        }), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"erro": f"Falha ao converter: {e}"}), 500

    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)


if __name__ == "__main__":
    app.run(debug=True)
