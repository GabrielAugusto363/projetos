# Deploy

Esta página descreve como publicar a aplicação em ambiente de produção, garantindo que o sistema funcione corretamente fora do ambiente de desenvolvimento.

## 1. Requisitos para deploy

Antes de publicar a aplicação, verifique se o servidor atende aos seguintes requisitos:

- Python 3.10 ou superior
- pip atualizado
- ambiente virtual configurado
- acesso às pastas de upload e temporários
- permissões de leitura e escrita na pasta do projeto
- servidor web ou serviço de execução em produção

## 2. Preparação do ambiente

No servidor, crie um ambiente virtual e instale as dependências:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Se o projeto não tiver `requirements.txt`, instale as bibliotecas necessárias manualmente:

```bash
pip install flask pikepdf PyMuPDF pdf2docx PyPDF2
```

## 3. Estrutura importante no servidor

A aplicação precisa de acesso às pastas abaixo:

```text
pdfPorQpdf/
├── app.py
├── static/
├── templates/
├── uploads/
├── temp/
├── logs/
├── requirements.txt
└── ...
```

Essas pastas devem ter permissões adequadas para:
- leitura do código;
- gravação dos uploads;
- geração de arquivos temporários;
- armazenamento de logs.

## 4. Configuração de variáveis de ambiente

Em produção, é recomendável configurar valores como:

```env
SECRET_KEY=sua_chave_secreta
UPLOAD_FOLDER=uploads
TEMP_FOLDER=temp
DEBUG=False
```

Se o projeto não usa `.env`, essas configurações podem ser definidas no próprio servidor ou no ambiente de execução.

## 5. Executar a aplicação em produção

O comando `flask run` não é recomendado para produção em ambiente real. O ideal é usar um servidor WSGI, como Gunicorn.

Exemplo:

```bash
pip install gunicorn
gunicorn app:app
```

Se a aplicação estiver configurada com o nome `app` pela variável Flask, ela será executada corretamente.

## 6. Exemplo de execução em Windows

No Windows, a execução pode ser feita assim:

```bash
venv\Scripts\activate
set FLASK_APP=app.py
set FLASK_ENV=production
gunicorn app:app
```

Ou, se preferir executar diretamente pela aplicação:

```bash
python app.py
```

Importante: essa opção é aceitável apenas para testes locais ou ambientes simples. Em produção, prefira um servidor WSGI.

## 7. Configuração de portas

A aplicação deve ficar acessível em uma porta configurada, como:

```bash
http://localhost:5000
```

Ou em um servidor proxy com domínio e SSL configurados.

## 8. Segurança no deploy

Antes de disponibilizar a aplicação, verifique:

- uso de `DEBUG=False`
- proteção contra uploads maliciosos
- controle de tamanho de arquivo
- permissões corretas nas pastas
- logs de erro ativos
- backend executando em processo seguro

## 9. Logs e monitoramento

Em produção, é importante armazenar mensagens de erro e atividades do sistema para facilitar manutenção. A aplicação deve registrar:

- erros de processamento
- falhas de upload
- arquivos corrompidos
- conversões sem sucesso
- problemas de permissão

## 10. Verificação final

Depois do deploy, teste:

- carregamento da página inicial;
- upload de PDF;
- processamento de junção/divisão/compressão;
- download do arquivo gerado;
- funcionamento em mais de um navegador;
- retorno de erros sem quebrar a aplicação.

## 11. Solução rápida de problemas

Se o deploy falhar, verifique:

- se a versão do Python está correta;
- se as dependências foram instaladas;
- se o ambiente virtual está ativo;
- se as pastas de upload e temporários possuem permissão;
- se a porta do serviço está livre;
- se há erros no log da aplicação.

## 12. Observações finais

Para ambiente de produção, o ideal é:

- usar um servidor WSGI;
- habilitar logs;
- configurar backups;
- proteger arquivos temporários;
- validar todos os uploads antes de processá-los;
- manter as dependências atualizadas.

Com essa configuração, a aplicação fica mais estável, segura e pronta para uso em produção.