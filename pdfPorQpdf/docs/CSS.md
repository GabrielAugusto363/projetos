## Parte do CSS

O estilo da aplicação foi implementado em `style.css` para dar uma aparência visual limpa, moderna e funcional ao site. A estrutura de design foi pensada para manter o foco nas ferramentas de PDF, com um layout simples, fácil de usar e responsivo.

### 1. Reset e base visual

No início do arquivo, foi aplicado um reset geral com:

- `box-sizing: border-box`
- `margin: 0`
- `padding: 0`
- definição da fonte principal como `Segoe UI`, Arial, sans-serif

Esse reset garante consistência visual entre navegadores e evita espaçamentos inconsistentes no layout.

A base do corpo da página foi definida com:

- fundo claro em tons cinza
- cor do texto escura
- sem estilos muito carregados para manter a legibilidade

---

### 2. Cabeçalho

O `header` foi estilizado com um degradê em vermelho e azul, criando um visual mais chamativo e institucional. Ele possui:

- alinhamento central do texto
- espaçamento interno maior
- cor branca para contraste
- destaque visual para o nome do site

O título principal `h1` foi ajustado com tamanho maior para dar destaque à marca da aplicação.

---

### 3. Navegação em abas

A classe `.abas` foi configurada como um container flexível, com:

- disposição horizontal
- quebra de linha quando necessário
- centralização dos botões
- espaçamento entre os itens

Os botões de aba `.aba-btn` receberam:

- fundo cinza claro
- borda arredondada
- texto escuro
- cursor de clique
- transição suave ao passar o mouse

Quando a aba está ativa, a classe `.aba-btn.ativo` muda para:

- fundo vermelho escuro
- texto branco
- destaque visual maior

Esse estilo foi importante para reforçar a navegação entre as ferramentas e indicar qual funcionalidade está selecionada.

---

### 4. Conteúdo principal

O `main` foi centralizado com largura máxima e espaçamento lateral, criando uma área de conteúdo visualmente organizada. Foi usado um `max-width` para impedir que o layout se espalhe demais em telas largas.

As seções de conteúdo `.aba-conteudo` foram estilizadas com:

- fundo branco
- borda arredondada
- sombra suave
- padding interno
- exibição controlada pelo JavaScript

Quando a classe `.ativo` é aplicada, a seção passa a mostrar o conteúdo. Sem essa classe, a seção permanece oculta.

Os títulos das abas `h2` receberam uma cor azul escura para manter uma padronização visual.

---

### 5. Formulários e campos de entrada

Os formulários foram configurados em coluna, com espaçamento uniforme entre os elementos. Isso garante uma organização clara dos campos de upload, select e botões.

Os campos de input receberam:

- borda destacada
- fundo quase branco
- arredondamento
- área de interação visualmente limpa

O select também foi estilizado com borda e padding para manter consistência com os outros campos.

O botão de envio `button[type="submit"]` foi estilizado em vermelho, com:

- texto branco
- borda arredondada
- hover em vermelho mais escuro
- cursor clicável

Quando o botão está desabilitado, o estilo muda para cinza, indicando que a operação está em andamento.

---

### 6. Status do processamento

A área `.status` foi configurada para exibir mensagens de retorno do sistema, como:

- sucesso
- erro
- carregamento

Essas classes possuem cores diferentes:

- `.status.sucesso` em verde
- `.status.erro` em vermelho
- `.status.carregando` em cinza escuro

Isso melhora a experiência do usuário, porque ele consegue identificar visualmente se a operação foi concluída com sucesso ou se ocorreu um problema.

---

### 7. Rodapé

O footer foi estilizado com:

- texto centralizado
- cor cinza
- tamanho menor
- espaçamento confortável

Esse acabamento ajuda a fechar a página de forma visualmente equilibrada.

---

### 8. Conclusão

O CSS foi responsável por deixar a interface do projeto organizada, profissional e fácil de usar. O uso de cores, espaçamentos, sombras e navegação em abas contribui para uma experiência visual clara, permitindo que as funcionalidades de PDF fiquem acessíveis e intuitivas para o usuário.

Se quiser, posso fazer também:
- uma versão mais técnica do CSS
- uma versão mais curta para relatório
- uma explicação de cada classe do arquivo
- um texto pronto para documentação do projeto