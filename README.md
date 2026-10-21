# 🚀 Smart PC Cleaner PRO (v2.0) — Otimizador Inteligente do Windows

Ferramenta local e inteligente desenvolvida em Python para Windows que opera **100% offline, sem necessidade de chaves de API ou IA externa**.

Utiliza um **motor semântico baseado em regras, sinônimos, lematização e tolerância a erros de digitação (Fuzzy Matching)** para interpretar comandos em linguagem natural. A edição PRO inclui interface visual avançada, monitoramento residente, e otimizações de nível profundo no SO e componentes do Windows.

---

## ⚡ Recursos Principais & Edição PRO

1. **[NOVO] Intermediador em Tempo Real (Resource Watchdog & Shield)**:
   * Monitora em segundo plano a utilização de **Memória RAM, Rede e Espaço em Disco**.
   * Quando o consumo de RAM atinge o limite configurado (ex: > 80%), executa mitigação instantânea via `EmptyWorkingSet`, liberando recursos de processos em background.
   * **Notificações Toast Nativas do Windows**: Informa exatamente quantos MBs e recursos foram recuperados em tempo real.
   * **Ícone na Bandeja do Windows (System Tray)**: Permite pausar/retomar, forçar otimização de RAM e liberar rede com 1 clique.

2. **Alta Performance e Otimizações Win32 de Baixo Nível**:
   * **Processamento de Diretórios Ultrarrápido**: Utiliza mapeamento via `os.scandir` e `shutil.rmtree` ao invés de iteradores de lista padrão, mitigando chamadas de disco (I/O) exaustivas durante a limpeza de caches (Chrome, Edge, Firefox, Temp, etc).
   * **Otimização Inteligente de RAM**: Filtra PIDs críticos do Sistema em tempo de execução, garantindo que as chamadas da API do Windows não gerem logs de Acesso Negado e priorizem apenas processos passíveis de compactação (Working Set Trim).

3. **[NOVO] Instalador Oficial no Windows (1-Clique)**:
   * Scripts automatizados `instalar.bat` e `desinstalar.bat`.
   * Cria atalhos na **Área de Trabalho** e no **Menu Iniciar**.
   * Registra o intermediador silencioso na inicialização do Windows (`Startup`), provendo proteção contínua sem peso.

4. **Experiência de Terminal Premium (CLI)**:
   * Utiliza as bibliotecas `rich` e `prompt_toolkit` para renderizar painéis coloridos, tabelas dinâmicas de consumo de espaço/memória, barras de progresso reais e **Auto-completar Inteligente** em todos os comandos no terminal.

5. **Recursos Corporativos e Manutenção de Sistema**:
   * **Liberação e Aceleração de Rede**: Desobstrui tabelas DNS, NetBIOS e buffers de rota sob demanda, e conta com script nativo para *Network Reset* profundo.
   * **Pontos de Restauração**: Criação segura de pontos de restauração via PowerShell (WMI).
   * **Limpeza de Componentes (WinSxS / DISM)**: Limpeza profunda da loja de componentes de sistema operacional nativo.
   * **Agendamento no Windows**: Configura limpeza programada invisível no Agendador de Tarefas do Windows (Task Scheduler).

6. **Procedimentos de Limpeza em 3 Níveis Automáticos**:
   * **Nível 1 (Básico / Rápido - 1/3)**: Lixeira, `%TEMP%`, flush DNS e otimização de RAM para o usuário ativo.
   * **Nível 2 (Intermediário / Performance - 2/3)**: Nível 1 + Temporários do Windows, Crash Dumps, Prefetch e liberação profunda de RAM Global.
   * **Nível 3 (Profundo / Manutenção Avançada - 3/3)**: Nível 2 + Logs de Eventos de Sistema (`wevtutil`), Cache do Windows Update, Limpeza DISM WinSxS e Caches de Desenvolvedor (npm/pip) + Ponto de Restauração prévio.

---

## 🖥️ Como Instalar e Executar

### 🌟 Instalação Completa na Máquina (Recomendado)
* Dê dois cliques em **`instalar.bat`** presente no projeto.
* O instalador irá:
  1. Instalar todas as dependências automaticamente do `requirements.txt`.
  2. Criar os atalhos na sua **Área de Trabalho** e no **Menu Iniciar**.
  3. Configurar o **Intermediador em Tempo Real** para iniciar junto com o Windows com o pequeno escudo na bandeja de ícones.

### Modo Portátil (Via Terminal)
```powershell
# Caminho Exemplo 
cd "d:\Cursos\Python\prog\smart-pc-cleaner"

# Modo CLI Interativo (com Auto-completar inteligente de IA Semântica)
python main.py

# Iniciar apenas o Intermediador / Guardião em Segundo Plano
python main.py --daemon

# Inserção de Comandos Diretos
python main.py "liberar rede e limpar ram"
python main.py "nivel 2"
```

---

## 🛠️ Personalização Rápida (`config.json`)

O motor do Smart PC Cleaner aceita regras de limpeza personalizadas. Basta editar o arquivo `config.json`:

```json
{
  "id": "minha_pasta_customizada",
  "name": "Cache do Meu App",
  "keywords": ["meuapp", "cache custom"],
  "action_type": "delete_dir_content",
  "path": "%APPDATA%\\MeuApp\\Cache",
  "requires_admin": false,
  "enabled": true
}
```

E para comandos shell/CLI customizados, como a limpeza de containers em desenvolvimento:

```json
{
  "id": "limpar_docker",
  "name": "Limpar Containers e Imagens Órfãs do Docker",
{{ ... }}
}
```

---

## 🧪 Suíte de Testes Automatizados e Eficiência

Para rodar a verificação de sanidade local e benchmarking rápido das funções de SO e da engine semântica:
```bash
python test_suite.py
```

---
#   L i m p a W i n x