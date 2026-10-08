# Progresso de implementação do CTRL-Lab

## Visão geral

Este documento registra o que foi implementado até o momento no projeto, com foco na arquitetura funcional do sistema e nos módulos já desenvolvidos.

## 1. Estrutura do projeto atual

```text
CTRL-Lab/
├── app/
│   ├── __init__.py
│   └── cameras/
│       ├── __init__.py
│       ├── entry_camera.py
│       ├── lab_camera.py
│       └── multi_stream.py
│
├── central/
│   ├── __init__.py
│   ├── events.py
│   └── mqtt_listener.py
│
├── raspberry_pi/
│   ├── __init__.py
│   ├── alerts.py
│   ├── config.py
│   ├── hardware.py
│   ├── main.py
│   ├── mqtt_client.py
│   └── sensors.py
│
├── tests/
│   ├── test_central_events.py
│   ├── test_entry_camera.py
│   ├── test_lab_camera.py
│   ├── test_raspberry_core.py
│   └── test_yolo_base.py
│
├── docs/
│   ├── README.md
│   └── PROGRESSO_IMPLEMENTACAO.md
│
├── .gitignore
├── PLANO_DESENVOLVIMENTO.md
├── README.md
├── requirements.txt
└── ...
```

## 2. Implementações concluídas

### 2.1 Módulo Raspberry Pi

Foram criados os primeiros componentes da unidade embarcada:

- leitura de temperatura e umidade;
- leitura simulada de gás e fumaça;
- estados do sistema: NORMAL, WARNING, ALERT e EMERGENCY;
- controle de LEDs, buzzer e sirene via abstração de hardware;
- compatibilidade com modo mock para execução sem Raspberry real;
- comunicação base para MQTT.

Arquivos principais:

- [raspberry_pi/config.py](../raspberry_pi/config.py)
- [raspberry_pi/sensors.py](../raspberry_pi/sensors.py)
- [raspberry_pi/alerts.py](../raspberry_pi/alerts.py)
- [raspberry_pi/hardware.py](../raspberry_pi/hardware.py)
- [raspberry_pi/main.py](../raspberry_pi/main.py)
- [raspberry_pi/mqtt_client.py](../raspberry_pi/mqtt_client.py)

### 2.2 Sistema central

Foi iniciada a base da aplicação central para receber os dados do Raspberry e registrar eventos:

- armazenamento em SQLite;
- criação de eventos a partir do payload recebido;
- classificação dos eventos por tipo e estado;
- listener MQTT pronto para receber as mensagens do Raspberry.

Arquivos principais:

- [central/events.py](../central/events.py)
- [central/mqtt_listener.py](../central/mqtt_listener.py)
- [central/__init__.py](../central/__init__.py)

### 2.3 Módulo de câmeras

Foi criada a infraestrutura para aquisição de vídeo das câmeras:

- câmera de entrada do laboratório;
- câmera de monitoramento do ambiente interno;
- estrutura para múltiplos streams em paralelo;
- suporte a stream IP e câmera local.

Arquivos principais:

- [app/cameras/entry_camera.py](../app/cameras/entry_camera.py)
- [app/cameras/lab_camera.py](../app/cameras/lab_camera.py)
- [app/cameras/multi_stream.py](../app/cameras/multi_stream.py)

### 2.4 Visão computacional inicial

Foi iniciada a base para detecção em imagens com YOLO:

- wrapper para modelo YOLO;
- retorno de detecções com classe e confiança;
- separação básica do módulo de visão para futura análise de EVIs e fumaça.

Arquivos principais:

- [app/vision/yolo_base.py](../app/vision/yolo_base.py)
- [app/vision/__init__.py](../app/vision/__init__.py)

## 3. Testes implementados

O projeto já conta com testes iniciais para os módulos principais:

- teste do sistema central de eventos;
- teste da câmera de entrada;
- teste da segunda câmera;
- teste do Raspberry em estados e payloads;
- teste da base do detector YOLO.

Arquivos de teste:

- [tests/test_central_events.py](../tests/test_central_events.py)
- [tests/test_entry_camera.py](../tests/test_entry_camera.py)
- [tests/test_lab_camera.py](../tests/test_lab_camera.py)
- [tests/test_raspberry_core.py](../tests/test_raspberry_core.py)
- [tests/test_yolo_base.py](../tests/test_yolo_base.py)

## 4. Próximos passos sugeridos

1. Implementar o módulo de análise de EPI e tomada de decisão de acesso.
2. Criar a lógica de detecção visual de fumaça e incêndio.
3. Integrar o Raspberry com o sistema central em broker MQTT real.
4. Preparar a interface de dashboard para consulta de eventos.
5. Evoluir a arquitetura para câmera, IA, banco de dados e monitoramento do laboratório.

## 5. Observação

A base do projeto está organizada para dar continuidade ao desenvolvimento em etapas, seguindo a ordem definida em [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md).

