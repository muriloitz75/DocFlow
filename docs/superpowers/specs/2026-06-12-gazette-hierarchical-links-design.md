# Links Hierárquicos do Índice do Diário Oficial

## Objetivo

Ampliar a criação de links no índice do Diário Oficial para usar a hierarquia editorial do próprio PDF. A linha de categoria, normalmente exibida em vermelho, fornece contexto para a linha de documento subordinada, normalmente exibida em verde. O link de extração é aplicado somente à linha do documento.

## Regra de associação

O parser mantém o último título de categoria encontrado no mesmo grupo hierárquico. Ao processar uma linha de documento, a aplicação forma uma referência de busca com o texto da categoria e o texto detalhado do documento.

Exemplos:

- `INSTRUÇÃO NORMATIVA` + `Nº 001 DE 16 DE JUNHO DE 2021 - SEFAZGO` identifica a Instrução Normativa nº 001.
- `RESOLUÇÃO` + `RESOLUÇÃO / C.M.S. 03/2021 - DO CONSELHO MUNICIPAL DE SAÚDE` identifica a Resolução 03/2021.
- `AVISO DE CONCORRÊNCIA` + `CONCORRÊNCIA PÚBLICA Nº 003/2021` identifica a concorrência pública correspondente.
- `AVISO DE RETIFICAÇÃO/ERRATA` + uma linha iniciada por `ERRATA` identifica a errata pelo título textual, ainda que não exista número normativo.

A associação deixa de depender exclusivamente da lista fixa de tipos normativos. Categorias e documentos não cadastrados previamente podem receber link quando houver correspondência textual suficiente com um título encontrado no corpo do Diário.

## Detecção no corpo

Além das normas reconhecidas pela expressão regular atual, o scanner coleta candidatos de documentos a partir das linhas detalhadas do índice. Para cada candidato, procura no corpo do PDF um cabeçalho compatível, desconsiderando diferenças de caixa, acentuação, pontuação e espaçamento.

Quando houver número, a correspondência exige o número e termos distintivos do tipo ou título. Quando não houver número, como em algumas erratas e avisos, a correspondência exige uma sequência textual distintiva do documento para reduzir falsos positivos.

O candidato encontrado recebe identificador, página inicial e página final, integrando o mesmo fluxo de extração já usado pelas normas cadastradas. Se nenhuma correspondência segura for encontrada, a linha permanece visível, mas não clicável.

## Hierarquia e escopo

Uma categoria fornece contexto apenas às linhas de documento seguintes até a próxima categoria ou seção. A linha de seção, normalmente azul, reinicia o contexto anterior. Categorias não recebem ação de extração.

O vínculo atual por tipo e número continua funcionando como alternativa para índices sem hierarquia clara ou para documentos já reconhecidos diretamente pelo scanner. A associação hierárquica complementa esse comportamento e não altera o formato da resposta consumida pelo frontend: linhas clicáveis continuam recebendo `norm_id`.

## Tratamento de ambiguidades

Se mais de um trecho do corpo corresponder ao mesmo candidato, a aplicação prioriza a ocorrência cuja página esteja mais próxima da página indicada no índice. Sem uma correspondência suficientemente distintiva, nenhum link é criado.

Entradas repetidas são mantidas no índice, mas podem apontar para o mesmo documento extraível quando representam a mesma publicação.

## Testes

Os testes automatizados devem cobrir:

- herança do tipo da categoria para uma linha que contém apenas número e data;
- associação de tipos já cadastrados, como Instrução Normativa e Resolução;
- associação de tipos não cadastrados, como Concorrência Pública;
- associação textual de Errata sem número;
- encerramento do contexto ao encontrar nova categoria ou seção;
- manutenção de linha não clicável quando não houver correspondência segura;
- preservação do vínculo atual por tipo e número;
- resposta da API com `norm_id` somente na linha verde detalhada.

