# Plano de Desenvolvimento — CRTL-Lab

## 1. Objetivo do plano

Este documento define a sequência de desenvolvimento do CRTL-Lab, priorizando primeiro a construção de uma versão mínima funcional e, posteriormente, a integração dos módulos.

A estratégia é evitar tentar desenvolver todos os componentes simultaneamente.

A ordem recomendada é:

```text
Câmera
  ↓
OpenCV
  ↓
Detecção com IA
  ↓
Lógica de segurança
  ↓
Comunicação
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

# 3. Fase 1 — Testar a primeira câmera

## Objetivo

Fazer um smartphone transmitir vídeo para a rede e permitir que o Raspberry Pi e a interface gráfica acessem o stream.

## Fluxo

```text
Smartphone
    ↓
Rede Wi-Fi
    ├── Raspberry Pi → OpenCV DNN e inferência
    └── Computador → visualização na interface
```

## Tarefas

- [ ] Escolher aplicativo para transformar o smartphone em câmera IP.
- [ ] Conectar os smartphones, o Raspberry e o computador à mesma rede.
- [ ] Obter URL do stream.
- [ ] Abrir o stream usando OpenCV.
- [ ] Exibir o vídeo.
- [ ] Testar estabilidade da transmissão.
- [ ] Medir aproximadamente a latência.

## Critério de conclusão

O Raspberry deve conseguir capturar frames para inferência e o computador deve conseguir exibir o stream na interface.

Este é o primeiro marco importante do projeto.

---

# 4. Fase 2 — Adicionar a segunda câmera

## Objetivo

Permitir que o sistema receba simultaneamente as duas câmeras.

## Câmera 1

Responsável pelo:

```text
Controle de acesso
+
Verificação de EPI
```

## Câmera 2

Responsável pelo:

```text
Monitoramento ambiental
+
Fumaça/incêndio
```

## Tarefas

- [ ] Configurar segundo smartphone.
- [ ] Criar `entry_camera.py`.
- [ ] Criar `lab_camera.py`.
- [ ] Testar os dois streams simultaneamente.
- [ ] Verificar consumo de CPU/RAM.
- [ ] Definir resolução adequada.

## Critério de conclusão

As duas câmeras devem funcionar no Raspberry, com inferência limitada por intervalo e resolução para respeitar os recursos do Pi.

---

# 5. Fase 3 — Primeiro teste com YOLO

## Objetivo

Validar a inteligência artificial no Raspberry antes de criar o modelo personalizado.

## Fluxo

```text
Smartphone / stream IP
  ↓
OpenCV
  ↓
YOLOv8 ONNX pelo OpenCV DNN (CPU no Raspberry)
  ↓
Pessoa detectada
```

## Tarefas

- [ ] Exportar um modelo YOLOv8 pequeno para ONNX em uma máquina de desenvolvimento.
- [ ] Copiar o ONNX para o Raspberry.
- [ ] Executar inferência no Raspberry com OpenCV DNN.
- [ ] Detectar pessoas.
- [ ] Exibir bounding boxes.
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

Criar o módulo responsável pela segunda câmera.

## Fluxo

```text
Câmera 2
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

Criar no computador uma interface visual para apresentação e monitoramento. A interface não deve executar modelos nem lógica de inferência.

## Elementos sugeridos

```text
┌─────────────────────────────────────────┐
│             CRTL-Lab                     │
├──────────────────┬──────────────────────┤
│ Câmera Entrada   │ Câmera Laboratório   │
│                  │                      │
│                  │                      │
├──────────────────┼──────────────────────┤
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

- [ ] Criar servidor web.
- [ ] Mostrar estado atual.
- [ ] Mostrar câmeras.
- [ ] Mostrar sensores.
- [ ] Mostrar EPI.
- [ ] Mostrar eventos.
- [ ] Criar indicadores visuais.
- [ ] Criar página de histórico.

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
✓ Câmera 1
✓ Câmera 2
✓ OpenCV
✓ YOLO
✓ Detecção de pessoa
✓ Verificação básica de EPI
✓ Detecção de fumaça/fogo
✓ Raspberry Pi
✓ Comunicação
✓ Alarme
```

## Prioridade 2 — Muito recomendado

```text
✓ Sensores ambientais
✓ Banco de dados
✓ Dashboard
✓ Histórico
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
Smartphone
    ↓
Raspberry Pi (OpenCV DNN + YOLO ONNX)
    ↓
Análise de EPI / fogo / fumaça
    ↓
Decisão e alarme locais
    ↓
MQTT → interface gráfica no computador
```

Depois:

```text
Smartphones → Raspberry Pi → IA + sensores → decisão/alarme locais
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
