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
│   ├── sensors.py
│   └── vision.py
│
├── tests/
│   ├── test_central_events.py
│   ├── test_entry_camera.py
│   ├── test_lab_camera.py
│   ├── test_raspberry_core.py
│   ├── test_raspberry_vision.py
│   ├── test_yolo_base.py
│   └── test_yolo_onnx.py
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

O Raspberry concentra a execução e as decisões de visão, além das tarefas embarcadas:

- leitura de temperatura e umidade;
- leitura simulada de gás e fumaça;
- estados do sistema: NORMAL, WARNING, ALERT e EMERGENCY;
- controle de LEDs, buzzer e sirene via abstração de hardware;
- compatibilidade com modo mock para execução sem Raspberry real;
- comunicação base para MQTT;
- inferência CPU com OpenCV DNN e YOLOv8 ONNX, sem PyTorch no Pi;
- captura das câmeras IP em thread separada para não atrasar o loop de sensores;
- publicação dos resultados visuais junto ao status MQTT;
- acionamento local de ALERTA/EMERGÊNCIA por EPI inadequado ou fogo/fumaça.

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

### 2.4 Visão computacional

O projeto agora conta com duas opções de detector:

- wrapper existente de Ultralytics, útil na máquina de desenvolvimento;
- OpenCV DNN para inferência de YOLOv8 ONNX em CPU no Raspberry;
- avaliadores de EPI e fumaça/fogo conectados ao serviço de câmeras.

O repositório não contém pesos. É necessário fornecer um ONNX YOLOv8 treinado para as classes `person`, `lab_coat`, `safety_glasses`, `closed_shoes`, `tied_hair`, `smoke` e `fire` (ou configurar a lista correspondente).

Arquivos principais:

- [app/vision/yolo_base.py](../app/vision/yolo_base.py)
- [app/vision/yolo_onnx.py](../app/vision/yolo_onnx.py)
- [raspberry_pi/vision.py](../raspberry_pi/vision.py)
- [app/vision/__init__.py](../app/vision/__init__.py)

## 3. Testes implementados

O projeto já conta com testes iniciais para os módulos principais:

- teste do sistema central de eventos;
- teste da câmera de entrada;
- teste da segunda câmera;
- teste do Raspberry em estados e payloads;
- teste da base do detector YOLO;
- teste de decodificação ONNX e execução CPU;
- teste do pipeline visual de EPI e fumaça/fogo.

Arquivos de teste:

- [tests/test_central_events.py](../tests/test_central_events.py)
- [tests/test_entry_camera.py](../tests/test_entry_camera.py)
- [tests/test_lab_camera.py](../tests/test_lab_camera.py)
- [tests/test_raspberry_core.py](../tests/test_raspberry_core.py)
- [tests/test_raspberry_vision.py](../tests/test_raspberry_vision.py)
- [tests/test_yolo_base.py](../tests/test_yolo_base.py)
- [tests/test_yolo_onnx.py](../tests/test_yolo_onnx.py)

## 4. Próximos passos sugeridos

1. Treinar/exportar e validar os pesos ONNX para as classes específicas.
2. Instalar e configurar um broker MQTT no Raspberry e validar a rede real.
3. Preparar a interface gráfica no computador para vídeo, telemetria e eventos.
4. Medir FPS/CPU/RAM no Raspberry utilizado e ajustar intervalo/resolução.

## 5. Observação

A base do projeto está organizada para dar continuidade ao desenvolvimento em etapas, seguindo a ordem definida em [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md).
