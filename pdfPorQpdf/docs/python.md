## Versão técnica da lógica do `app.py`

A aplicação foi implementada em Flask e centraliza a lógica de processamento de PDFs em um único arquivo principal, `app.py`. A estrutura da API é organizada em rotas dedicadas para cada funcionalidade, como junção, divisão, compressão e conversão para Word. O código também conta com funções auxiliares para validação de arquivos, armazenamento temporário, logging de erros e geração dos arquivos de saída.

### 1. Configuração inicial e dependências

No início do arquivo, são importadas as bibliotecas necessárias para:

- manipulação de arquivos e diretórios;
- envio de arquivos via HTTP;
- criação de logs e monitoramento;
- processamento de PDFs com bibliotecas especializadas.

As principais dependências são:

- Flask, para criação da aplicação web;
- os, uuid, shutil e tempfile, para gerenciamento de arquivos temporários;
- pikepdf, para compactação e otimização de documentos PDF;
- PyMuPDF, para renderização e reconstrução de páginas;
- pdf2docx, para conversão de PDF para DOCX;
- PyPDF2 / PdfReader, para leitura e validação dos arquivos.

A configuração da aplicação inclui o diretório de uploads, o diretório de saída e parâmetros de controle de extensão e tamanho permitido para os arquivos.

---

### 2. Funções auxiliares

O arquivo contém funções utilitárias para reduzir repetição e centralizar a lógica comum entre as rotas. Entre elas, destacam-se:

- `salvar_upload`: grava o arquivo enviado pelo cliente em um diretório temporário;
- `extensao_valida`: valida a extensão do arquivo;
- `validar_pdf`: verifica se o documento é realmente um PDF válido;
- `novo_nome`: gera um nome único para o arquivo de saída;
- `registrar_erro`: grava detalhes de exceções e informações relevantes no log;
- `registrar_acesso`: registra os acessos e atividades da aplicação;
- `registrar_duracao`: mede o tempo de processamento de cada requisição.

Essas funções ajudam a manter o código mais organizado, facilitando a manutenção e a depuração.

---

### 3. Tratamento de upload e processamento

Cada rota da aplicação recebe arquivos por meio de `request.files` e realiza verificações antes de iniciar o processamento. As validações incluem:

- presença do arquivo;
- extensão permitida;
- integridade do documento;
- tamanho do arquivo;
- formato válido do PDF.

Depois da validação, o arquivo é salvo em um diretório temporário e processado conforme a rota solicitada. Ao final, o resultado é enviado ao cliente por meio de `send_file`, e os arquivos temporários são removidos para evitar acúmulo de dados.

O fluxo geral segue esse padrão:

1. receber arquivo;
2. validar extensão;
3. validar o documento PDF;
4. processar o arquivo;
5. gerar a saída;
6. retornar o arquivo para download;
7. limpar arquivos temporários.

---

### 4. Rota de junção de PDFs

A funcionalidade de união de PDFs foi implementada em uma rota específica. Ela recebe vários arquivos, verifica se todos são válidos e cria um novo documento com a sequência das páginas informada.

A lógica principal envolve:

- leitura de cada PDF com `PdfReader`;
- extração das páginas;
- criação de um objeto `PdfWriter`;
- inserção das páginas no novo documento;
- salvamento do PDF final;
- retorno do arquivo para download.

Essa abordagem permite combinar múltiplos documentos em um único arquivo de forma automatizada e eficiente.

---

### 5. Rota de divisão de PDFs

A divisão do PDF também foi desenvolvida como uma rota independente. A aplicação aceita parâmetros como:

- intervalo de páginas;
- páginas específicas;
- divisão total do documento.

A lógica de processamento inclui:

- validação do arquivo de entrada;
- leitura das páginas do PDF;
- identificação do intervalo ou das páginas selecionadas;
- criação de páginas ou arquivos separados;
- empacotamento em ZIP, quando necessário;
- envio dos arquivos gerados para download.

A biblioteca `PyPDF2` é usada para leitura, seleção e escrita das páginas resultantes. O uso de ZIP facilita o download de múltiplos arquivos em um único pacote.

---

### 6. Rota de compressão de PDFs

A compressão de PDFs é uma das funcionalidades mais complexas do projeto. A aplicação recebe um documento e aplica uma estratégia conforme o nível de compressão escolhido.

#### Modo padrão

Quando o valor selecionado não é 25 ou 50, o sistema usa `pikepdf` com parâmetros como:

- `compress_streams=True`
- `recompress_flate=True`
- `object_stream_mode=pikepdf.ObjectStreamMode.generate`

Esse método reduz o tamanho do arquivo sem alterar profundamente a estrutura do documento, preservando melhor a qualidade visual.

#### Modo com redução de qualidade

Quando o valor de compressão é 25 ou 50, a aplicação usa `PyMuPDF` para:

- abrir cada página do PDF;
- aplicar uma matriz de transformação;
- renderizar a página em um pixmap;
- converter para JPEG com qualidade configurada;
- criar uma nova página no documento resultante;
- salvar o PDF compactado.

Esse método é mais agressivo e reduz o tamanho do arquivo com perda de qualidade visual, principalmente em imagens e gráficos.

A aplicação também calcula a porcentagem de redução comparando os tamanhos antes e depois do processamento:

- `tamanho_antes`
- `tamanho_depois`
- `reducao = 1 - tamanho_depois / tamanho_antes`

Esse cálculo é retornado ao usuário para que ele saiba o percentual de compressão obtido.

---

### 7. Rota de conversão de PDF para Word

A conversão de PDF para DOCX foi implementada com a biblioteca `pdf2docx`. A rota recebe o documento em PDF, valida o arquivo e executa a conversão por meio dos métodos:

- `Converter(caminho_entrada)`
- `conversor.convert(caminho_saida)`
- `conversor.close()`

O resultado é um arquivo DOCX editável, que pode ser baixado pelo usuário. Essa funcionalidade permite transformar conteúdo em PDF em um formato mais adequado para edição e manipulação em ambientes como o Microsoft Word.

---

### 8. Tratamento de erros e robustez

A aplicação inclui mecanismos para lidar com falhas e entradas inválidas. Os principais casos cobertos incluem:

- arquivos vazios;
- arquivos corrompidos;
- PDFs inválidos;
- erros durante a conversão;
- falhas na compactação;
- exceções não tratadas.

O código utiliza blocos `try/except` e registra ocorrências em arquivos de log. Esse mecanismo aumenta a confiabilidade do sistema e facilita a análise de problemas em ambiente de produção.

---

### 9. Estrutura funcional do sistema

Em termos de arquitetura, o projeto segue um padrão simples e eficiente:

- frontend em HTML/JavaScript para interação com o usuário;
- backend em Flask para processamento;
- armazenamento temporário para uploads;
- resposta HTTP com download do resultado final;
- limpeza automática dos arquivos temporários após uso.

Essa organização torna o sistema fácil de expandir, pois cada operação funcional é separada em uma rota específica, com lógica independente e bem definida.

---

### 10. Conclusão técnica

O projeto foi implementado como uma ferramenta web para manipulação de PDFs, com foco em operações cotidianas de documentos. O arquivo `app.py` centraliza toda a lógica de processamento, validação, conversão e download. A combinação de bibliotecas nativas e especializadas permite atingir um bom equilíbrio entre funcionalidade, eficiência e simplicidade de uso.

Esse sistema é adequado para tarefas como:
- união de documentos;
- separação de páginas;
- compressão de PDFs;
- conversão para Word;
- geração de arquivos prontos para download.