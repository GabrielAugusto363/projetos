# PDF Tools

Site em Flask para comprimir, dividir, juntar e converter PDFs (PDF ↔ Word).

## Estrutura do projeto

```
pdf-tools/
│
├── app.py                 # backend Flask (todas as rotas da API)
├── requirements.txt        # dependências Python
├── README.md
│
├── templates/
│   └── index.html          # página principal
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
├── uploads/                 # arquivos temporários enviados (esvaziada automaticamente)
└── outputs/                 # arquivos gerados para download
```

## 1. Requisitos do sistema

Além do Python, duas funcionalidades dependem de programas externos instalados no sistema operacional (não são bibliotecas Python):

| Funcionalidade | Depende de |
|---|---|
| Comprimir PDF | **Ghostscript** |
| Word → PDF | **LibreOffice** |
| Juntar / Dividir PDF | Só Python (pypdf) |
| PDF → Word | Só Python (pdf2docx) |

### Instalar Ghostscript
- Windows: baixe em https://ghostscript.com/releases/gsdnld.html
- Mac: `brew install ghostscript`
- Linux: `sudo apt install ghostscript`

### Instalar LibreOffice
- Windows/Mac: baixe em https://www.libreoffice.org/download
- Linux: `sudo apt install libreoffice`

> Se você não for usar "Comprimir" ou "Word → PDF" agora, pode pular a instalação desses dois — as demais funções do site funcionam sem eles.

## 2. Configurar o ambiente (no PyCharm)

1. Abra a pasta `pdf-tools` no PyCharm como novo projeto.
2. No PyCharm, crie um ambiente virtual: `File > Settings > Project > Python Interpreter > Add Interpreter > Venv`.
3. Abra o terminal integrado do PyCharm e rode:

```
pip install -r requirements.txt
```

## 3. Rodar o site

No terminal do PyCharm:

```
python app.py
```

Depois acesse **http://127.0.0.1:5000** no navegador.

## 4. Como funciona

- O `app.py` serve o `index.html` e expõe 5 rotas de API (`/api/juntar`, `/api/dividir`, `/api/comprimir`, `/api/pdf-para-word`, `/api/word-para-pdf`).
- O JavaScript (`script.js`) envia os arquivos via `fetch()` para essas rotas e baixa automaticamente o resultado.
- Arquivos enviados ficam em `uploads/` só durante o processamento e são apagados logo depois.
- Arquivos gerados ficam em `outputs/` até o download.

## Próximos passos possíveis
- Adicionar limite de tamanho de arquivo mais visível no front-end
- Adicionar barra de progresso real (upload grande)
- Fazer deploy (Render, Railway, PythonAnywhere, etc.)
