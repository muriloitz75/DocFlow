# Instruções de Deploy e Integração Contínua (Railway)

Este guia explica como funciona o deploy do **DocFlow** no Railway e como atualizar o ambiente de produção a partir das branches de desenvolvimento (como `flow_one`).

---

## 🔍 Como funciona a integração Git ➡️ Railway

Por padrão, o Railway está integrado ao seu repositório do GitHub e monitora a branch principal (geralmente `master` ou `main`) para realizar o deploy de produção.

* **Se você der `git push` na branch atual (`flow_one`):** As alterações serão enviadas apenas para a branch `flow_one` no GitHub. O Railway **não** atualizará a produção automaticamente (a menos que esteja configurado especificamente para isso, ou que gere um deploy de *Preview* temporário).
* **Para atualizar a produção:** Você deve mesclar (merge) as alterações da sua branch de desenvolvimento na branch de produção monitorada pelo Railway.

---

## 🚀 Métodos para Atualizar a Produção

Abaixo estão as duas formas de gerenciar e atualizar seu ambiente ativo no Railway.

### Método 1: Fluxo Recomendado (Git Merge)

Este é o método padrão de mercado. Você desenvolve em uma branch separada (ex: `flow_one`), testa localmente e, quando estiver tudo pronto, mescla as alterações na branch de produção (`master` ou `main`).

Execute os seguintes comandos no terminal:

```powershell
# 1. Certifique-se de salvar e commitar tudo na sua branch de desenvolvimento
git checkout flow_one
git add .
git commit -m "feat: minhas alterações prontas para produção"
git push origin flow_one

# 2. Mude para a branch de produção (geralmente master ou main)
git checkout master

# 3. Atualize a branch de produção local com o servidor
git pull origin master

# 4. Mescle as alterações da sua branch de desenvolvimento
git merge flow_one

# 5. Envie as alterações para o GitHub (isso disparará o deploy automático no Railway)
git push origin master

# 6. (Opcional) Volte para a sua branch de desenvolvimento para continuar trabalhando
git checkout flow_one
```

---

### Método 2: Alterar a Branch de Produção no Railway

Se você prefere que o Railway passe a monitorar a branch `flow_one` (ou qualquer outra branch de desenvolvimento) diretamente como a branch de produção:

1. Acesse o painel do [Railway](https://railway.app/).
2. Abra o projeto do **DocFlow**.
3. Selecione o serviço correspondente ao seu backend/aplicação.
4. Vá na aba **Settings** (Configurações) no menu superior.
5. Role até a seção **Deploy** e localize o campo **Deployment Branch**.
6. Altere o valor da branch para `flow_one` (ou a branch desejada).
7. Salve as configurações.

---

## ⚙️ Otimizações e Limites de Produção (Railway)

Para garantir que a aplicação rode de forma estável sob as limitações de recursos (RAM e CPU compartilhada) do Railway, foram aplicados os seguintes ajustes arquiteturais:

### 1. Tempo Limite e Controle de Memória (Gunicorn)
A plataforma Railway pode ignorar o `Procfile` se utilizar build automático via Nixpacks. Para forçar as configurações de produção, o arquivo `gunicorn.conf.py` foi criado na raiz do projeto, contendo:
* **Timeout de 300 segundos**: Evita que o Gunicorn derrube o worker prematuramente durante o processamento de PDFs extensos.
* **1 Worker ativo**: Otimiza a memória RAM do container (geralmente limitada a 512 MB no plano básico), prevenindo erros de *Out of Memory (OOM)*.

### 2. Otimização Inteligente para PDFs
* **PDFs com ≤ 15 páginas**: O processamento detalhado por página via `pdfplumber` é mantido para garantir máxima precisão no alinhamento de tabelas e formatos especiais.
* **PDFs com > 15 páginas**: Para evitar o consumo massivo de CPU e estouros de memória, a aplicação pula a verificação detalhada e usa a extração rápida com `pdfminer.six` direto, reduzindo o tempo de conversão pela metade sem perda de conteúdo.

### 3. Bypass do Magika (ONNX Runtime)
A biblioteca `magika` (usada pelo `markitdown` original) tenta adivinhar o tipo do arquivo usando Inteligência Artificial. No entanto, o motor ONNX Runtime entra em conflito de threads (*deadlock*) em ambientes de containers Linux limitados, travando as requisições. 
Como o DocFlow já valida a extensão do arquivo na entrada, o Magika foi **completamente desativado** por padrão, tornando a validação e conversão 100% seguras e mais rápidas.

---

## 🛠️ Comandos Git Úteis

Para verificar o status do seu repositório a qualquer momento:

* Ver em qual branch você está e se há arquivos modificados:
  ```powershell
  git status
  ```
* Listar todas as branches locais e remotas:
  ```powershell
  git branch -a
  ```
* Ver os repositórios remotos configurados:
  ```powershell
  git remote -v
  ```
