# Plano de Desenvolvimento — CRTL-Lab

## 1. Objetivo do plano

Este documento define a sequência de desenvolvimento do CRTL-Lab, priorizando primeiro a construção de uma versão mínima funcional e, posteriormente, a integração dos módulos.

A estratégia é evitar tentar desenvolver todos os componentes simultaneamente.

A ordem recomendada é:

```text
Uma câmera USB PS3 Eye
  ↓
Captura única de frames
  ↓
Modelo contínuo de segurança + modelo de acesso controlável
  ↓
Decisão de segurança independente do dashboard
  ↓
MQTT + atalho local de teclado
  ↓
Raspberry Pi
  ↓
Sensores + alertas
  ↓
Banco de dados
  ↓
Dashboard
  ↓
Testes e apresentação
```

---

# 2. Fase 0 — Organização do projeto

## Objetivos

- Criar o repositório Git.
- Definir a estrutura de diretórios.
- Definir os responsáveis por cada módulo.
- Criar ambiente virtual Python.
- Documentar decisões técnicas.

## Tarefas

- [ ] Criar repositório Git.
- [ ] Criar `README.md`.
- [ ] Criar `PLANO_DESENVOLVIMENTO.md`.
- [ ] Criar `.gitignore`.
- [ ] Criar ambiente virtual.
- [ ] Criar `requirements.txt`.
- [ ] Definir padrão de nomes e organização do código.

## Resultado esperado

Projeto inicial organizado e pronto para receber os módulos.

---

# 3. Fase 1 — Integrar a PS3 Eye

## Objetivo

Capturar vídeo de uma única câmera USB PS3 Eye ligada ao Raspberry Pi. Essa câmera será compartilhada pelos dois modelos; não será usado stream IP de celular devido à latência e aos travamentos relatados.

## Fluxo

```text
PS3 Eye (USB)
    ↓
Raspberry Pi → OpenCV → frame compartilhado
                       ├── modelo de segurança (sempre ativo)
                       └── modelo de acesso (ativável/desativável)
```

## Tarefas

- [ ] Conectar a PS3 Eye ao Raspberry Pi e confirmar o índice do dispositivo.
- [ ] Abrir o stream usando OpenCV.
- [ ] Testar captura contínua e estabilidade no hardware real.
- [ ] Medir latência, FPS e uso de CPU/RAM.

## Critério de conclusão

O Raspberry deve ler frames da PS3 Eye sem rede ou smartphone no caminho de vídeo.

Este é o primeiro marco importante do projeto.

---

# 4. Fase 2 — Compartilhar a câmera entre dois modelos

## Objetivo

Executar dois modelos de IA sobre o mesmo frame capturado, evitando abrir duas câmeras ou capturar o vídeo duas vezes.

## Estados de execução

| Modelo | Estado esperado | Responsabilidade |
|---|---|---|
| Segurança | Sempre habilitado enquanto a visão estiver em execução | Detectar fumaça e fogo; manter geração de emergência ativa |
| Acesso | Desabilitado por padrão; carregado sob demanda e habilitável/desabilitável durante a execução | Detectar pessoa e avaliar EPIs para o acesso ao laboratório |

O atalho `A` no terminal alterna o modelo de acesso. O dashboard envia a mesma solicitação pelo tópico MQTT `ctrlab/central/commands` (API `CentralMQTTListener.set_access_model_enabled`); nenhuma ação do dashboard pode parar o modelo de segurança.

## Tarefas

- [x] Capturar um único frame e compartilhar entre detectores de segurança e acesso.
- [x] Manter a inferência de segurança contínua.
- [x] Permitir habilitar/desabilitar a inferência de acesso em execução.
- [x] Reservar comandos MQTT e atalho de teclado para controlar o modelo de acesso.
- [ ] Confirmar sincronização, desempenho e estabilidade na PS3 Eye real.

## Critério de conclusão

Cada ciclo deve capturar um frame da PS3 Eye e executar sempre o modelo de segurança. O ONNX de acesso deve ser carregado e executado somente enquanto habilitado, e removido da memória ao desativá-lo.

---

# 5. Fase 3 — Primeiro teste com YOLO

## Objetivo

Validar a inteligência artificial no Raspberry antes de criar o modelo personalizado.

## Fluxo

```text
PS3 Eye (uma captura)
  ↓
Frame compartilhado
  ├── YOLO segurança (ONNX/OpenCV DNN, CPU)
  └── YOLO acesso (ONNX/OpenCV DNN, CPU, sob demanda)
```

## Tarefas

- [ ] Exportar modelos YOLOv8 ONNX separados para segurança (`smoke`, `fire`) e acesso (`person` e classes de EPI).
- [ ] Copiar os modelos ONNX para o Raspberry.
- [x] Executar inferência de segurança em todos os ciclos.
- [x] Executar inferência de acesso apenas quando habilitada.
- [ ] Medir FPS.
- [ ] Medir uso de CPU/RAM no Raspberry.

## Critério de conclusão

O Raspberry deve detectar classes em frames da câmera sem depender do computador para inferência.

## Observação

Ultralytics é usado somente na máquina de desenvolvimento para exportação; no Raspberry a inferência usa OpenCV DNN e ONNX, sem PyTorch.

O processamento embarcado requer um ONNX YOLOv8 com as classes adequadas; o modelo COCO genérico não reconhece EPIs, fumaça ou fogo.

---

# 6. Fase 4 — Módulo de EPI

## Objetivo

Criar o primeiro módulo específico do projeto.

## Classes inicialmente planejadas

```text
person
lab_coat
safety_glasses
closed_shoes
tied_hair
```

## Estratégia

Primeiro utilizar um modelo pré-treinado para validar o pipeline.

Depois criar/adaptar um dataset próprio e realizar fine-tuning.

## Tarefas

- [ ] Definir exatamente quais EPIs serão avaliados.
- [ ] Pesquisar datasets existentes.
- [ ] Capturar imagens próprias.
- [ ] Fazer anotação das imagens.
- [ ] Dividir dataset em treinamento/validação/teste.
- [ ] Treinar/fazer fine-tuning do modelo.
- [ ] Avaliar precisão.
- [ ] Testar diferentes iluminações.
- [ ] Testar diferentes distâncias.
- [ ] Testar diferentes pessoas.
- [ ] Testar falsos positivos e falsos negativos.

## Importante

O modelo não deve simplesmente produzir:

```text
"óculos detectado"
```

O sistema precisa transformar a detecção em uma decisão:

```text
Óculos = SIM
Jaleco = SIM
Calçado fechado = NÃO

→ ACESSO NEGADO
→ Motivo: calçado inadequado
```

---

# 7. Fase 5 — Motor de decisão de EPI

## Objetivo

Separar a inteligência artificial da lógica de segurança.

## Arquitetura

```text
YOLO
 ↓
Detecções
 ↓
PPE Evaluator
 ↓
Decisão
```

## Exemplo

```python
detections = {
    "lab_coat": True,
    "safety_glasses": True,
    "closed_shoes": False,
    "tied_hair": True
}
```

Resultado:

```python
{
    "authorized": False,
    "missing": ["closed_shoes"]
}
```

## Tarefas

- [ ] Criar `ppe.py`.
- [ ] Criar `decision.py`.
- [ ] Definir regras.
- [ ] Criar estados `NORMAL` e `ALERTA`.
- [ ] Criar mensagens de justificativa.
- [ ] Testar cada combinação de EPI.

---

# 8. Fase 6 — Detecção de fumaça e incêndio

## Objetivo

Criar/validar o modelo contínuo de segurança, que usa a PS3 Eye compartilhada.

## Fluxo

```text
PS3 Eye (frame compartilhado)
   ↓
YOLO / modelo de visão
   ↓
Fumaça ou fogo
   ↓
Motor de decisão
   ↓
EMERGÊNCIA
```

## Tarefas

- [ ] Pesquisar dataset de fumaça/incêndio.
- [ ] Testar modelos existentes.
- [ ] Definir classes.
- [ ] Avaliar falsos positivos.
- [ ] Testar diferentes condições de iluminação.
- [ ] Testar vídeos reais.
- [ ] Integrar ao motor de decisão.

## Critério de conclusão

Uma detecção confiável deve gerar um evento de emergência no software.

---

# 9. Fase 7 — Sensores no Raspberry Pi

## Objetivo

Adicionar informações físicas ao sistema.

## Possíveis sensores

```text
Temperatura
Umidade
Gás
Partículas/fumaça
```

## Tarefas

- [ ] Montar sensores.
- [ ] Testar cada sensor individualmente.
- [ ] Criar código de leitura.
- [ ] Validar valores.
- [ ] Criar módulos separados.
- [ ] Definir limites de alerta.
- [ ] Testar situações simuladas.

## Estrutura

```text
raspberry/
├── sensors/
│   ├── temperature.py
│   ├── gas.py
│   └── smoke.py
```

---

# 10. Fase 8 — Comunicação Raspberry ↔ Interface gráfica

## Objetivo

Fazer os dois sistemas trocarem informações.

## Tecnologia recomendada

**MQTT**

O MQTT é adequado porque permite comunicação leve entre dispositivos.

## Exemplo de tópicos

### Raspberry → computador de interface

```text
ctrlab/raspberry/status
ctrlab/raspberry/alerts
```

### Computador → Raspberry

```text
ctrlab/central/commands
```

O broker MQTT pode rodar no Raspberry. O computador recebe eventos e status; as decisões de visão e os alertas físicos não dependem dele.

Comando para o atalho do dashboard controlar somente a análise de acesso:

```json
{"command":"set_access_model","enabled":true}
```

Enviar `enabled: false` desativa a análise de acesso. O modelo de segurança não possui comando de desligamento. O Raspberry publica o estado efetivo em `vision.access.enabled` no tópico de status.

## Exemplo de fluxo

```text
Sensor de gás
      ↓
Raspberry Pi
      ↑
 Câmeras IP + IA
      ↓
MQTT
      ↓
Computador (interface e histórico)
```

## Critério de conclusão

Uma informação enviada pelo Raspberry deve chegar ao notebook e um comando enviado pelo notebook deve produzir uma ação no Raspberry.

---

# 11. Fase 9 — Sistema de estados

## Objetivo

Centralizar as decisões do sistema.

Estados:

```text
NORMAL
ALERTA
EMERGÊNCIA
```

## Exemplo

```text
NORMAL
  │
  ├── EPI inadequado → ALERTA
  │
  └── Fogo → EMERGÊNCIA
```

## Regras

### NORMAL

Nenhum problema detectado.

### ALERTA

Problema relacionado ao uso de EPI ou condição que requer atenção.

### EMERGÊNCIA

Situação potencialmente perigosa:

- Fogo.
- Fumaça significativa.
- Gás acima do limite.
- Condição crítica de temperatura.

## Regra importante

Eventos críticos não devem depender apenas de uma pontuação.

Por exemplo:

```text
Fogo detectado
```

deve gerar diretamente:

```text
EMERGÊNCIA
```

---

# 12. Fase 10 — Dispositivos de alerta

## Objetivo

Transformar decisões do software em ações físicas.

## Possíveis dispositivos

- LED verde → sistema normal.
- LED amarelo → alerta.
- LED vermelho → emergência.
- Buzzer → alerta sonoro.
- Sirene → emergência.

## Fluxo

```text
Estado
  ↓
MQTT
  ↓
Raspberry Pi
  ↓
GPIO
  ↓
Atuador
```

## Tarefas

- [ ] Controlar LED.
- [ ] Controlar buzzer.
- [ ] Controlar sirene.
- [ ] Criar função de desligamento/reset.
- [ ] Testar estados.

---

# 13. Fase 11 — Banco de dados

## Objetivo

Registrar ocorrências.

## Tecnologia

SQLite.

## Exemplos de eventos

```text
Pessoa detectada
Acesso permitido
EPI inadequado
Fumaça detectada
Fogo detectado
Gás acima do limite
Temperatura elevada
Sistema normalizado
```

## Informações sugeridas

```text
id
timestamp
tipo
descrição
nível
origem
estado
```

---

# 14. Fase 12 — Dashboard

## Objetivo

Criar no computador uma interface web para apresentação e monitoramento, acessível pelo IP na rede local. A interface não executa modelos nem lógica de inferência; troca status e comandos com o Raspberry por MQTT.

## Elementos sugeridos

```text
┌─────────────────────────────────────────┐
│             CRTL-Lab                     │
├──────────────────┬──────────────────────┤
│ Estado do sistema + conexão MQTT        │
├──────────────────┬──────────────────────┤
│ EPI              │ Ambiente             │
│ ✓ Jaleco         │ Temperatura: 25 °C   │
│ ✓ Óculos         │ Gás: Normal          │
│ ✓ Calçado        │ Fumaça: Normal       │
├──────────────────┴──────────────────────┤
│ STATUS: NORMAL                          │
├─────────────────────────────────────────┤
│ Histórico de eventos                    │
└─────────────────────────────────────────┘
```

## Tarefas

- [x] Criar servidor web HTTP acessível na rede local.
- [x] Mostrar estado atual e conexão MQTT.
- [x] Mostrar sensores ambientais e resultados dos modelos.
- [x] Adicionar controle para habilitar/desabilitar o modelo de acesso via MQTT.
- [x] Refletir no painel `vision.access.enabled` recebido no status.
- [x] Mostrar eventos recentes do SQLite.
- [x] Criar indicadores visuais responsivos.
- [x] Adicionar pré-visualização MJPEG protegida da PS3 Eye no dashboard, compartilhando a captura da inferência.
- [ ] Criar página de histórico paginada.

---

# 15. Fase 13 — Modo demonstração

## Objetivo

Garantir uma apresentação controlada na feira.

Nem sempre será possível provocar uma situação real de fumaça, fogo ou gás.

Por isso, o sistema deverá possuir um modo de simulação.

## Exemplos

```text
[Simular EPI inadequado]
[Simular fumaça]
[Simular incêndio]
[Simular gás]
[Simular temperatura alta]
[Resetar sistema]
```

## Exemplo

Ao clicar:

```text
SIMULAR INCÊNDIO
```

o dashboard deve mostrar:

```text
🔥 EMERGÊNCIA

Incêndio detectado.
Alarme acionado.
```

E o Raspberry deve receber o comando para acionar a sirene.

---

# 16. Fase 14 — Testes

## Testes de visão computacional

- [ ] Pessoa com todos os EPIs.
- [ ] Pessoa sem jaleco.
- [ ] Pessoa sem óculos.
- [ ] Pessoa com calçado inadequado.
- [ ] Pessoa com cabelo solto.
- [ ] Diferentes iluminações.
- [ ] Diferentes distâncias.
- [ ] Mais de uma pessoa.

## Testes ambientais

- [ ] Temperatura normal.
- [ ] Temperatura acima do limite.
- [ ] Sensor de gás normal.
- [ ] Simulação de gás.
- [ ] Sensor de fumaça normal.
- [ ] Simulação de fumaça.

## Testes de comunicação

- [ ] Notebook → Raspberry.
- [ ] Raspberry → Notebook.
- [ ] Perda da rede.
- [ ] Reconexão.
- [ ] Reinicialização.

## Testes de segurança

- [ ] Alarme acionado corretamente.
- [ ] Alarme desligado após normalização.
- [ ] Eventos registrados.
- [ ] Dashboard atualizado.

---

# 17. Fase 15 — Otimização

Depois que tudo estiver funcionando, otimizar.

Não otimizar prematuramente.

## Possíveis otimizações

- Reduzir resolução dos streams.
- Reduzir quantidade de frames processados.
- Utilizar modelos YOLO menores.
- Ajustar `--image-size` e `--inference-interval` para a capacidade do Pi.
- Processar apenas regiões relevantes.
- Evitar inferência quando não há pessoas.
- Melhorar comunicação MQTT.
- Reduzir uso de CPU.
- Melhorar estabilidade das câmeras.

---

# 18. Fase 16 — Preparação da apresentação

## Demonstração sugerida

### Etapa 1 — Sistema normal

Mostrar:

```text
STATUS: NORMAL
```

### Etapa 2 — Pessoa entra

A câmera detecta a pessoa.

```text
Pessoa detectada
```

### Etapa 3 — Verificação de EPI

Mostrar:

```text
Jaleco       ✓
Óculos       ✓
Calçado      ✓
Cabelo       ✓

ACESSO PERMITIDO
```

### Etapa 4 — EPI inadequado

Mostrar:

```text
Óculos       ✗

ACESSO NEGADO
```

O sistema pode acionar um alerta.

### Etapa 5 — Emergência

Acionar uma simulação:

```text
FUMAÇA DETECTADA
```

O sistema muda para:

```text
EMERGÊNCIA
```

E o Raspberry aciona o alarme.

### Etapa 6 — Dashboard

Mostrar o evento sendo registrado no histórico.

---

# 19. Ordem de prioridade

Nem todas as funcionalidades possuem a mesma prioridade.

## Prioridade 1 — Obrigatório

```text
✓ Uma PS3 Eye compartilhada
✓ OpenCV
✓ YOLO
✓ Modelo de segurança sempre ativo
✓ Modelo de acesso controlável
✓ Raspberry Pi
✓ Comunicação
✓ Alarme
```

## Prioridade 2 — Muito recomendado

```text
✓ Sensores ambientais
✓ Banco de dados
✓ Dashboard web na rede local com controle do modelo de acesso
✓ Eventos recentes integrados ao dashboard
✓ Modo demonstração
```

## Prioridade 3 — Extras

```text
○ RFID/NFC
○ Tela OLED
○ Sistema de pontuação de risco
○ Notificação externa
○ Relatórios
○ Estatísticas
○ Mais tipos de sensores
```

Se houver pouco tempo, as funcionalidades da prioridade 3 devem ser descartadas antes de comprometer o funcionamento do núcleo do projeto.

---

# 20. Meta de versão mínima

A primeira versão funcional deve ser:

```text
PS3 Eye
    ↓
Raspberry Pi (OpenCV DNN + YOLO ONNX)
    ├── segurança (sempre ativa)
    └── acesso/EPI (sob demanda)
    ↓
Decisão e alarme locais
    ↓
MQTT → interface gráfica no computador
```

Depois:

```text
PS3 Eye → Raspberry Pi → dois modelos + sensores → decisão/alarme locais
                    │
                    └── MQTT → computador (interface e histórico)
```

---

# 21. Critério de conclusão do projeto

O projeto poderá ser considerado funcional quando conseguir demonstrar, de ponta a ponta:

```text
CAPTURA
   ↓
PROCESSAMENTO
   ↓
INTELIGÊNCIA ARTIFICIAL
   ↓
DECISÃO
   ↓
COMUNICAÇÃO
   ↓
AÇÃO FÍSICA
   ↓
REGISTRO
   ↓
VISUALIZAÇÃO
```

Exemplo completo:

```text
Câmera detecta fumaça
        ↓
Modelo no Raspberry identifica fumaça
        ↓
Raspberry classifica como emergência e aciona a sirene
        ↓
Evento MQTT é recebido e registrado no computador
        ↓
Interface mostra EMERGÊNCIA
```

Esse fluxo representa o principal objetivo técnico do CRTL-Lab: **integrar visão computacional, inteligência artificial, sistemas embarcados, sensores e software em uma solução única de segurança para laboratórios.**
