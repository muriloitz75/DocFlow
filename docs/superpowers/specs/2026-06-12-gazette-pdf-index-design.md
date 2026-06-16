# Índice Editorial do Diário Oficial

## Objetivo

Exibir o índice da conversão do Diário Oficial com a mesma linguagem visual do PDF de referência: título centralizado, hierarquia por recuo e cor, líderes pontilhados e número da página alinhado à direita.

## Estrutura

O backend preserva o texto das páginas identificadas como índice e o transforma em linhas estruturadas. Cada linha contém texto, página, nível hierárquico, papel visual e, quando houver correspondência, o identificador da norma detectada no corpo do PDF.

O frontend renderiza as linhas como um índice editorial contínuo. Linhas de secretaria usam azul e nível 0; categorias usam vermelho e nível 1; documentos usam verde e nível 2. O texto e a página são separados por um líder pontilhado flexível. Linhas associadas a normas são botões clicáveis que mantêm o fluxo existente de extração e visualização.

## Compatibilidade

Quando o PDF não oferecer um índice utilizável, a interface gera linhas equivalentes a partir das normas detectadas. O cache mantém os dados estruturados para restauração e extração. A apresentação reduz tipografia e recuos em telas estreitas sem perder página ou ação.

## Verificação

Testes unitários cobrem parsing, hierarquia, associação com normas e resposta da API. A interface é verificada no navegador com dados representativos da imagem de referência.
