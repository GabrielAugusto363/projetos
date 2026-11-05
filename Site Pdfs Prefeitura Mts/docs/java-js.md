## Parte do JavaScript

O arquivo `script.js` foi responsável por controlar a interação entre a interface HTML e as rotas da API em Flask. Sua função principal foi conectar cada formulário da página com o backend, permitindo que o envio de arquivos e o download do resultado aconteçam de forma automática e dinâmica.

### 1. Troca de abas

No início do script, foi implementada a lógica para alternar as abas da interface:

- `botoesAba`
- `conteudosAba`

A cada clique em um botão com a classe `.aba-btn`, o código:

1. remove a classe `ativo` de todos os botões
2. remove a classe `ativo` de todos os conteúdos
3. marca o botão clicado como ativo
4. mostra o conteúdo correspondente pelo `data-aba`

Essa parte é essencial porque a página usa uma estrutura de abas para separar as ferramentas de PDF em um único layout.

---

### 2. Função padrão de envio de formulários

A função principal foi `enviarFormulario(formId, url, statusId, nomeArquivoPadrao)`. Ela é reutilizada para os quatro serviços:

- juntar
- dividir
- comprimir
- PDF → Word

Essa função:

- pega o formulário pelo ID
- pega a div de status
- adiciona um evento `submit`
- impede o comportamento padrão do formulário
- coleta os dados com `FormData`
- envia via `fetch` para a rota correta
- mostra mensagem de “Processando... aguarde.”
- desabilita o botão para evitar múltiplos envios
- trata respostas de sucesso e erro
- faz download automático do arquivo retornado

Se a resposta da API não for OK, o código verifica:

- se o erro é de tamanho excedido (`413`)
- ou se a API retornou uma mensagem em JSON
- ou se o erro não foi especificado

A mensagem então é exibida na área de status, com classe visual de erro.

Se a resposta for bem-sucedida, o script:

- lê o cabeçalho `Content-Disposition`
- identifica o nome do arquivo que será baixado
- cria um `Blob` com a resposta
- cria um link temporário
- dispara o download automaticamente
- remove o link depois do processo

Esse método é eficiente porque permite baixar o arquivo sem precisar abrir uma nova página ou navegar para outra rota.

---

### 3. Inicialização dos formulários

Após a criação da função, ela é chamada para cada formulário da interface:

- `form-juntar` → `/api/juntar`
- `form-dividir` → `/api/dividir`
- `form-comprimir` → `/api/comprimir`
- `form-pdf-word` → `/api/pdf-para-word`

Cada chamada define o nome padrão do arquivo de saída:

- `juntado.pdf`
- `paginas_divididas.zip`
- `comprimido.pdf`
- `convertido.docx`

Isso é importante porque o navegador precisa saber o nome do arquivo que será baixado quando a resposta chega.

---

### 4. Heartbeat do painel administrativo

Além das funcionalidades de processamento, o script também implementa um heartbeat para registrar a presença dos usuários no admin.

A função `enviarHeartbeat()` faz um `fetch` para:

- `/api/heartbeat`

Esse envio é realizado:

- imediatamente ao carregar a página
- e depois a cada 60 segundos

A intenção dessa lógica é manter o sistema atualizado sobre quem está online e quando o usuário saiu.

Também existe um evento:

- `beforeunload`

que usa `navigator.sendBeacon("/api/heartbeat/saida")` para registrar a saída do usuário ao fechar a aba ou sair da página.

Esse mecanismo é útil para a parte administrativa do sistema, permitindo monitorar acessos e manter o histórico de usuários conectados.

---

### 5. Conclusão

O JavaScript foi responsável por conectar visualmente a interface com a lógica do backend e pela automação dos fluxos de upload e download. Ele centralizou a operação de processamento dos formulários e também deu suporte ao monitoramento do painel administrativo com heartbeat. Em resumo, o script atua como camada de comunicação entre usuário e servidor.

